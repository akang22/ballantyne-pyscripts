import collections
import datetime
import enum
import warnings

warnings.simplefilter(action="ignore", category=FutureWarning)
import operator

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from charts import finapi

class NoDividendsException(Exception):
    pass

eng_fmt = pd.io.formats.format.EngFormatter(accuracy=2, use_eng_prefix=True)
eng_fmt.ENG_PREFIXES = {
        0: "",
        3: "k",
        6: "M",
        9: "G",
        12: "T",
        15: "P",
        18: "E",
        21: "Z",
        24: "Y",
    }

def render_main():
    st.set_page_config(layout = "wide")
    st.markdown("""
                <style>
                    div[data-testid="column"]:not(:first-child) {
                        flex-grow: 0;
                        flex-basis: fit-content !important;
                    }
                    div[data-testid="column"]:first-child {
                        flex-grow: 1;
                    }
                    div[data-testid="column"]:has( div[data-testid="stButton"]) {
                        flex-grow: 0;
                        flex-basis: fit-content !important;
                    }
                    div[data-testid="stSlider"] {
                        display: none;
                    }
                </style>""", unsafe_allow_html=True)
    st.title("StockCharts")
    
    ticker_input = st.text_input("Ticker Value")
    
    def get_quarter_end_date(year, quarter):
        month = 3 * ((quarter + 3) % 4) + 3
        date_index = datetime.date(year, month, 28) + datetime.timedelta(days=4)
        return date_index - datetime.timedelta(days=date_index.day)
    
    def get_quarter_end_by_date(date):
        quarter = ((date.month + 10) // 3) % 4 + 1
        ret = get_quarter_end_date(date.year, quarter)
        return ret
    
    def similar_range_to(df, min1, max1):
        min2, max2 = df.min(), df.max()
    
        # ranges must be within 3x.
        if max2 - min2 != 0:
            ratio = abs((max1 - min1) / (max2 - min2))
    
            if ratio > 3 or ratio * 3 < 1:
                return False
    
        # require some intersection
        if min2 > max1 or min1 > max2:
            return False
    
        # perhaps add more conditions
        return True
        
    @st.cache_data
    def get_ticker_data(ticker, start_date):
        hprice = finapi.price(ticker)
        SP500_hprice = finapi.price("^GSPC")
        mcap = finapi.mcap(ticker)
        dividend_amount = finapi.dividends(ticker)
        revenue = finapi.revenue(ticker)
        q_ev = finapi.enterprise_value(ticker)

        # TODO: we should adjust to start of quarter
        ev = piecewise_op_search(q_ev, mcap, operator.sub)
        ev = piecewise_op_search(mcap, ev, operator.add)
    
        return {
            "hprice": hprice,
            "ticker": ticker,
            "start_date": start_date,
            "ev": ev,
            "dividend_amount": dividend_amount,
            "revenue": revenue,
            "SP500_hprice": SP500_hprice,
            "mcap": mcap,
        }
    
    
    # with two date-indexed series df1 and df2, return a dataframe with indices same as df1 (cutting off elements that are after df2)
    # with value op(elem, df2[elem]) (for elem in df1, df2[elem] is value in df2 with the closest date after)
    # round_final causes default to last element when values go over
    def piecewise_op_search(df1, df2, op, round_final=True):
        indices = df2.index.searchsorted(df1.index)
        if round_final and len(df2.index) in indices:
            # default to last element
            cutoff = list(indices).index(len(df2))
            indices[cutoff:] = len(df2.index) - 1
        else:
            # prevent out of bounds index
            df1 = df1[df1.index < df2.index.max()]
            indices = df2.index.searchsorted(df1.index)
        temp_df = df2.iloc[indices]
        temp_df.index = df1.index
        return op(df1, temp_df)
    
    # graph1
    @st.cache_data
    def get_graph1(*_, start_date, hprice, ticker, SP500_hprice, **rest):
        print(hprice.index.searchsorted(start_date))
        price_return = (
            ((hprice / hprice[hprice.index.searchsorted(start_date)]) - 1)
        )
        SP500_return = (
            ((SP500_hprice / SP500_hprice[SP500_hprice.index.searchsorted(start_date)]) - 1)
        )
    
        graph1 = pd.concat([SP500_return, price_return], keys=["SP 500", ticker], axis=1)
        graph1.index = pd.to_datetime(graph1.index, utc=True).date
    
        return graph1
    
    
    # graph2
    @st.cache_data
    def get_graph2(*_, mcap, ev, **rest):
        graph2 = pd.concat([ev, mcap], keys=["Enterprise Value", "Market Cap"], axis=1)
        graph2.index = pd.to_datetime(graph2.index, utc=True).date
    
        return graph2
    
    
    # graph3
    # For IBM, 10-k is missing in finnhub API, causing issues. However given finnhub is right this should be right
    @st.cache_data
    def get_graph3(*_, ticker, start_date, **rest):
        eps_diluted = finapi.eps_diluted(ticker)
        # TODO: make sure rollings are expected direction
        graph3 = eps_diluted.rolling(4).sum().rename("EPS Diluted Before Extra (TTM)").to_frame()
    
        return graph3
    
    
    # graph4
    @st.cache_data
    def get_graph4(*_, dividend_amount, start_date, **rest):
        if dividend_amount is None:
            raise NoDividendsException("No dividends found")

        dividend_ratios = dividend_amount.rolling(4).sum().rolling(5).apply(lambda a: (a[4] - a[0]) / a[0] * 100)
    
        graph4 = pd.concat(
            [dividend_ratios, dividend_amount],
            keys=["1 Year Dividend Growth Rate", "Dividend Amount"],
            axis=1,
        )
    
        return graph4
    
    
    # graph5
    @st.cache_data
    def get_graph5(*_, ticker, mcap, start_date, **rest):
        price_to_book = finapi.price_book(ticker) 
        price_to_cashflow = finapi.price_cashflow(ticker).rolling(4).mean() / 4
        price_to_sales = finapi.price_sales(ticker).rolling(4).mean() / 4
    
        graph5 = pd.concat([price_to_book, price_to_cashflow, price_to_sales], keys=["Price to Book", "Price to Cashflow (TTM)", "Price to Sales (TTM)"], axis=1)
        graph5.index = pd.to_datetime(graph5.index, utc=True).date
    
        # see above
        graph5 = piecewise_op_search(graph5, mcap, lambda df1, df2: df1.div(df2, axis=0))
        graph5 = piecewise_op_search(mcap, graph5, lambda df1, df2: df2.mul(df1, axis=0))
    
        return graph5
    
    
    # graph6
    # ebit issue is issue with IBM
    @st.cache_data
    def get_graph6(*_, ticker, ev, **rest):
        ebitda = finapi.ebitda(ticker).rolling(4).sum()
        ev_ebitda = piecewise_op_search(ev, ebitda, lambda df1, df2: df1.div(df2, axis=0))

        ebit_revenue = finapi.ebit_revenue(ticker)
        revenue = finapi.revenue(ticker)
        ebit = piecewise_op_search(ebit_revenue, revenue, lambda df1, df2: df1.mul(df2, axis=0)).rolling(4).sum()

        ev_ebit = piecewise_op_search(ev, ebit, lambda df1, df2: df1.div(df2, axis=0))
        graph6 = pd.concat([ev_ebit, ev_ebitda], keys=["EV / EBIT (TTM)", "EV / EBITDA (TTM)"], axis=1)
    
        return graph6
    
    
    # graph7
    @st.cache_data
    def get_graph7(*_, hprice, ticker, dividend_amount, start_date, **rest):
        if dividend_amount is None:
            raise NoDividendsException("No dividends found")

        # todo: move into display logic?
        price_return = hprice.rename(ticker)[hprice.index >= start_date]
    
        dividend_amount = dividend_amount[dividend_amount.index >= start_date]
    
        total_return = piecewise_op_search(price_return, dividend_amount.cumsum(), operator.add)
    
        price_return = (price_return / hprice[hprice.index.searchsorted(start_date)]) - 1
        total_return = (total_return / total_return.iloc[0]) - 1
    
        graph7 = pd.concat(
            [price_return, total_return], keys=["Price Return", "Total Return"], axis=1
        )
    
        return graph7
    
    
    # graph8
    @st.cache_data
    def get_graph8(*_, ticker, revenue, start_date, **rest):
        revenue_ttm = revenue.rolling(4).sum()
        revenue_growth = revenue_ttm.rolling(5).apply(lambda a: (a[4] / a[0]) - 1)
        
        ebitda_ttm = finapi.ebitda(ticker).rolling(4).sum()
    
        graph8 = pd.concat([revenue_growth, ebitda_ttm], keys=["Revenue Growth (YoY)", "EBITDA (TTM)"], axis=1)
        return graph8
    
    
    # graph9
    @st.cache_data
    def get_graph9(*_, ticker, **rest):
        roe = finapi.return_equity(ticker).rolling(4).sum()
        rotc = finapi.return_total_capital(ticker).rolling(4).sum()
        roa = finapi.return_assets(ticker).rolling(4).sum()
    
        graph9 = pd.concat(
            [
                roe,
                rotc,
                roa
            ],
            keys=[
                "Return on Equity (TTM)",
                "Return on Total Capital (TTM)",
                "Return on Assets (TTM)",
            ],
            axis=1,
        )
    
        return graph9
    
    
    # graph10
    @st.cache_data
    def get_graph10(*_, ticker, revenue, **rest):
        revenue_ttm = revenue.rolling(4).sum()
        net_income = finapi.net_income(ticker).rolling(4).sum()
    
        graph10 = pd.concat([revenue_ttm, net_income], keys=['Total Revenue (TTM)', 'Net Income (TTM)'], axis=1)
        return graph10
    
    
    # graph11
    @st.cache_data
    def get_graph11(*_, ticker, **rest):
        graph11 = finapi.weighted_average_shares_diluted_outstanding(ticker).rolling(4).mean().rename("Weighted Average Diluted Shares Outstanding (TTM)").to_frame()
    
        return graph11
    
    
    # graph12
    # sac tangible, book value and book value per share
    @st.cache_data
    def get_graph12(*_, **rest):
        book_share = finapi.book_value_share(ticker)
        tangible_bv = finapi.tangible_book_value(ticker)
        total_debt = finapi.total_debt(ticker)
    
        graph12 = pd.concat([book_share, tangible_bv, total_debt], keys=["BV per share", "Tangible Book Value", "Total Debt"], axis=1)

    
        return graph12
    
    
    graph_funcs = [
        get_graph1,
        get_graph2,
        get_graph3,
        get_graph4,
        get_graph5,
        get_graph6,
        get_graph7,
        get_graph8,
        get_graph9,
        get_graph10,
        get_graph11,
        get_graph12,
    ]
    
    
    meta_info = [
        {
            "title": "Price Return",
            "ypercent": True,
            "singleaxis": True,
        },
        {
            "shortform": { "Enterprise Value": "EV"}
        },
        {
            "shortform": { "EPS Diluted Before Extra (TTM)": "Diluted EPS" },
            "show_legend": False,
        },
        {
            "shortform": { "1 Year Dividend Growth Rate": "Div Growth", "Dividend Amount": "Div Amount"},
        },
        {
            "shortform": { "Price to Book": "P/Book", "Price to Cashflow (TTM)": "P/Cashflow", "Price to Sales (TTM)": "P/Sales" },
        },
        {
            "shortform": { "EV / EBIT (TTM)": "EV/EBIT", "EV / EBITDA (TTM)": "EV/EBITDA" }
        },
        {
            "ypercent": True,
            "singleaxis": True,
        },
        {
            "shortform": { "Revenue Growth (YoY)": "Revenue Growth", "EBITDA (TTM)": "EBITDA" },
            "ypercent": [True, False],
            "singleaxis": False,
        },
        {
            "shortform": { "Return on Equity (TTM)": "RoE", "Return on Total Capital (TTM)": "RoTC", "Return on Assets (TTM)": "RoA" },
            "ypercent": True
        },
        {
            "shortform": { "Total Revenue (TTM)": "Revenue", "Net Income (TTM)": "Income" }
        },
        {
            "shortform": { "Diluted Weighted Average Shares Outstanding (TTM)": "DWAS Outstanding" },
            "show_legend": False,
        },
        {
            "title": "Book Value / Share, Tangible Book Value, Total Debt",
            "shortform": { "Book Value / Share": "BV/Share", "Tangible Book Value": "Tang BV", "Total Debt": "Debt"}
        },
    ]
    
    ticker_vals = [val.strip().upper() for val in ticker_input.split(",") if val.strip() != ""]
    period = st.selectbox("Select time period", options=["1Y", "3Y", "5Y", "10Y", "Custom"], index = 1)

    start_date = datetime.date.today()
    if period == "Custom":
        start_date = st.date_input("Select start date", value = start_date.replace(year = start_date.year - 3))
    else:
        start_date = start_date.replace(year = start_date.year - int(period[:-1]))
    
    if len(ticker_vals) == 0:
        tabs = []
        st.text("Enter a stock above, or a series of stocks seperated by commas")
        return
    
    tab = st.select_slider("Step",
            options=range(len(ticker_vals)+1),
            key="tab",
            label_visibility="hidden",
        )
    ticker = ticker_vals[tab]

    cols = st.columns(len(ticker_vals))

    for ind, ticker_name in enumerate(ticker_vals):
        # late binding in python
        def set_tab(ind=ind):
            st.session_state["tab"] = ind
        cols[ind].button(ticker_name, type="primary", on_click=set_tab, disabled=ind == tab)

    try:
       ticker_data = get_ticker_data(ticker, start_date)
    except Exception as e:
       st.error(
           f"Data could not be fetched. Double check the ticker {ticker} is correct."
       )
       st.exception(e)
       return
    
    for func, data in zip(graph_funcs, meta_info):
       try:
           graph = func(**ticker_data)
           graph = graph[graph.index >= start_date]
    
           col1, col2 = st.columns(2)
           col2.text("\n")
           col2.text("\n")
           col2.text("\n")
           col2.text("\n")
           col2.text("\n")
           col2.text("\n")
           col2.dataframe(graph.iloc[[0, -1]].style.format({
               col: '{:,.2}%'.format if "ypercent" in data and (data["ypercent"] is True or data["ypercent"][i] is True) else eng_fmt
               for i, col in enumerate(graph)
               }))
           
           fig = go.Figure()
           layoutupdate = {}
           axes = []
           for col in graph:
               for i, axis in enumerate(axes):
                   if ("singleaxis" in data and not data["singleaxis"]):
                       continue
                   if ("singleaxis" in data and data["singleaxis"]) or similar_range_to(graph[col], axis[1], axis[2]):
                       axes[i] = ([*axes[i][0], col], min(axis[1], graph[col].min()), max(axis[2], graph[col].max()))
                       break
               else:
                   axes.append(([col], graph[col].min(), graph[col].max()))
    
           for i, axis in enumerate(axes):
               label = str(i + 1) if i != 0 else ""
               for col in axis[0]:
                   print((col if not ('shortform' in data and col in data['shortform']) else data['shortform'][col]))
                   fig.add_trace(go.Scatter(x=graph.index, y=graph[col], name=(col if not ('shortform' in data and col in data['shortform']) else data['shortform'][col]),yaxis=f"y{label}"))
               axis_title = ", ".join([data['shortform'][col] if ('shortform' in data and col in data['shortform']) else col for col in axis[0]])
               layoutupdate[f"yaxis{label}"] = dict(title=(', '.join(axis[0]) if len(axis[0]) == 1 else axis_title), autoshift=True, title_standoff=10, shift=-30)
               if i != 0:
                   layoutupdate[f"yaxis{label}"]["tickmode"] = "sync"
                   layoutupdate[f"yaxis{label}"]["overlaying"] = "y"
                   layoutupdate[f"yaxis{label}"]["anchor"] = "free"
    
               if "ypercent" in data and (data["ypercent"] is True or data["ypercent"][i] is True):
                   layoutupdate[f"yaxis{label}"]["tickformat"] =".2%"
    
           fig.update_layout(**layoutupdate, title=f"{ticker}: {', '.join(graph.columns) if not ('title' in data) else data['title']}", hovermode="x unified", xaxis_title="Date", margin_l = 80 + 20 * len(axes))
    
           if "show_legend" in data:
               fig.update_layout(showlegend=data["show_legend"])
               fig.update_layout({"legend_title_text": "Legend"})
           col1.plotly_chart(fig, use_container_width=True)
       except NoDividendsException as nde:
           st.warning(f"Graph could not be shown as no dividends were found for ticker {ticker}")

       except Exception as e:
           st.text(f"Graph {data['title']} could not be shown due to the following error:")
           st.exception(e)
           continue

    def next_tab():
        st.session_state["tab"] = (tab + 1) % len(ticker_vals)

    def prev_tab():
        st.session_state["tab"] = (tab + len(ticker_vals) - 1) % len(ticker_vals)

    st.button("Previous Tab", type="primary", on_click=next_tab)
    st.button("Next Tab", type="primary", on_click=next_tab)



render_main()
