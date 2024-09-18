import collections
import datetime
import enum
import warnings

warnings.simplefilter(action="ignore", category=FutureWarning)
import operator

import finnhub
import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
import yfinance as yf
from plotly.subplots import make_subplots

from apikeys import ConfigKey, get_secret

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
                </style>
                """, unsafe_allow_html=True)
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
    
        # ranges must be within 2x.
        if max2 - min2 != 0:
            ratio = abs((max1 - min1) / (max2 - min2))
    
            if ratio > 2 or ratio < 0.5:
                return False
    
        # require some intersection
        if min2 > max1 or min1 > max2:
            return False
    
        # perhaps add more conditions
        return True
        
    
    def flatten_report(report):
        date_index = get_quarter_end_date(report["year"], report["quarter"])
    
        return {
            "index": date_index,
            **{
                v["concept"]: v["value"]
                for sheet in report["report"].values()
                for v in sheet
            },
        }
    
    
    finnhub_client = finnhub.Client(api_key=get_secret(ConfigKey.FINNHUB))
    SP500DATA = yf.Ticker("^GSPC")
    
    def verify_quarterly_data_irregularities(data, start_date):
        data = data[data.index >= start_date]
        if data.isna().any():
            print("DEBUG:")
            print(data.to_string())
            st.warning("Requested data contains nans")
        quarter_ends = pd.date_range(start=start_date, end=data.index[-1], freq='QE').date
        missing_quarter_ends = [date for date in quarter_ends if date not in data.index]
        if len(missing_quarter_ends) > 0:
            print("DEBUG:")
            print(data.to_string())
            st.warning(f"Requested data does not contain these monthend values: {missing_quarter_ends}")
    
    @st.cache_data
    def get_ticker_data(ticker, start_date):
        yahoo_finance_info = yf.Ticker(ticker)
        finnhub_data = finnhub_client.company_basic_financials(ticker, "all")
    
        data1 = pd.DataFrame(
            [
                flatten_report(a)
                for a in finnhub_client.financials_reported(symbol=ticker, freq="annual")[
                    "data"
                ]
            ]
        ).set_index("index")[::-1]
        data2 = pd.DataFrame(
            [
                flatten_report(a)
                for a in finnhub_client.financials_reported(
                    symbol=ticker, freq="quarterly"
                )["data"]
            ]
        ).set_index("index")[::-1]
        finnhub_reported_data = pd.concat([data1, data2]).sort_index()
        finnhub_reported_data.index = pd.to_datetime(finnhub_reported_data.index, utc=True).date
    
        hprice = yahoo_finance_info.history(period="max", auto_adjust=False)["Open"]
        hprice.index = pd.to_datetime(hprice.index).date
    
        SP500_hprice = SP500DATA.history(period="max", auto_adjust=False)["Open"]
        SP500_hprice.index = pd.to_datetime(SP500_hprice.index).date
    
        mapping = collections.defaultdict(dict)
        for k, v in finnhub_data["series"]["quarterly"].items():
            for i in v:
                mapping[i["period"]][k] = i["v"]
    
        quarterly_series = pd.DataFrame(mapping).transpose()[::-1]
        quarterly_series.index = np.vectorize(get_quarter_end_by_date)(pd.to_datetime(quarterly_series.index).date)
    
        price_to_book = quarterly_series["pb"]
        book_value = quarterly_series["bookValue"]
    
        q_mcap = (book_value.mul(price_to_book, fill_value=np.NaN) * (10**6))
        q_mcap.index = pd.to_datetime(q_mcap.index).date
    
        # so this may look stupid, multiply and divide by the same column, but this essentially is first dividing by
        # the values on the exact dates to 'normalize' the value, and then interpolate with the remaining prices as indexes.
        mcap = piecewise_op_search(
            hprice, piecewise_op_search(q_mcap, hprice, operator.truediv), operator.mul
        )
    
        num_shares = nan_default_chain(
            finnhub_reported_data,
            [
                "us-gaap_WeightedAverageNumberOfSharesOutstandingBasic",
                "WeightedAverageNumberOfSharesOutstandingBasic",
            ],
        )
    
        dividend_amount = yahoo_finance_info.dividends
        dividend_amount.index = pd.to_datetime(dividend_amount.index).date
    
        # sum dividends by quarter
    
    
        revenue = nan_default_chain(
                finnhub_reported_data,
                ["us-gaap_Revenues", "Revenues", "us-gaap_RevenueFromContractWithCustomerExcludingAssessedTax", "RevenueFromContractWithCustomerExcludingAssessedTax"],
                fill_zeros=True,
                adjust=AdjustReported.ALLYTD
        )
    
        q_ev = quarterly_series["ev"]
        q_ev = q_ev[q_ev.index >= start_date] * 1000000
    
        ev = piecewise_op_search(q_ev, mcap, operator.sub)
        ev = piecewise_op_search(mcap, ev, operator.add)
    
        return {
            "hprice": hprice,
            "num_shares": num_shares,
            "ticker_name": ticker,
            "start_date": start_date,
            "ev": ev,
            "dividend_amount": dividend_amount,
            "revenue": revenue,
            "SP500_hprice": SP500_hprice,
            "quarterly_series": quarterly_series,
            "mcap": mcap,
            "finnhub_reported_data": finnhub_reported_data,
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
    
    
    class AdjustReported(enum.Enum):
        NOTHING, ANNUALSYTD, ALLYTD = range(3)
    
    
    def nan_default_chain(data, key_list, fill_zeros=False, adjust=AdjustReported.NOTHING):
        key_list = [key for key in key_list if key in data]
        ret = pd.Series(np.nan, index=data.index)
        for key in key_list:
            ret = ret.fillna(data[key])
        match adjust:
            # todo: add interpolation
            case AdjustReported.ANNUALSYTD:
                ret = ret.rolling(4).apply(
                    lambda x: x[3] if x.index[3].month != 12 else x[3] - x[0] - x[1] - x[2]
                )
            case AdjustReported.ALLYTD:
                ret = ret.rolling(2).apply(
                    lambda x: x[1] - x[0] if x.index[1].month != 3 else x[1]
                )
            case AdjustReported.NOTHING:
                pass
        if fill_zeros:
            ret = ret.fillna(0)
        return ret
    
    
    # todo: multiple axes with https://stackoverflow.com/questions/65037641/plotly-how-to-add-multiple-y-axes
    # todo: add 'current' boxes with https://plotly.com/python/indicator/
    # todo: clear up naming and [::-1]s, make functions less leaky
    
    # graph1
    @st.cache_data
    def get_graph1(*_, start_date, hprice, ticker_name, SP500_hprice, **rest):
        price_return = (
            ((hprice / hprice[hprice.index.searchsorted(start_date)]) - 1)
        )
        SP500_return = (
            ((SP500_hprice / SP500_hprice[SP500_hprice.index.searchsorted(start_date)]) - 1)
        )
    
        graph1 = pd.concat([SP500_return, price_return], keys=["SP 500", ticker_name], axis=1)
        graph1.index = pd.to_datetime(graph1.index, utc=True).date
    
        return graph1
    
    
    # graph2
    @st.cache_data
    def get_graph2(*_, quarterly_series, mcap, ev, **rest):
        graph2 = pd.concat([ev, mcap], keys=["Enterprise Value", "Market Cap"], axis=1)
        graph2.index = pd.to_datetime(graph2.index, utc=True).date
    
        return graph2
    
    
    # graph3
    # For IBM, 10-k is missing in finnhub API, causing issues. However given finnhub is right this should be right
    @st.cache_data
    def get_graph3(*_, finnhub_reported_data, start_date, **rest):
        eps_diluted = nan_default_chain(
            finnhub_reported_data,
            [
                "us-gaap_EarningsPerShareDiluted",
                "EarningsPerShareDiluted",
                "us-gaap_EarningsPerShareBasic",
                "EarningsPerShareBasic",
            ],
            fill_zeros=True,
            adjust=AdjustReported.ALLYTD
        )
        raw = nan_default_chain(
            finnhub_reported_data,
            [
                "us-gaap_EarningsPerShareDiluted",
                "EarningsPerShareDiluted",
                "us-gaap_EarningsPerShareBasic",
                "EarningsPerShareBasic",
            ],
            fill_zeros=True,
            adjust=AdjustReported.NOTHING
        )
        print("HELLO")
        print(raw)
        verify_quarterly_data_irregularities(eps_diluted, start_date.replace(year = start_date.year - 1))
        graph3 = eps_diluted.rolling(4).sum().rename("EPS Diluted (TTM)").to_frame()
    
        return graph3
    
    
    # graph4
    @st.cache_data
    def get_graph4(*_, finnhub_reported_data, num_shares, dividend_amount, quarterly_series, start_date, **rest):
        dividend_ratios = dividend_amount.rolling(4).sum().rolling(5).apply(lambda a: (a[4] - a[0]) / a[0] * 100)
    
        graph4 = pd.concat(
            [dividend_ratios, dividend_amount],
            keys=["1 Year Dividend Growth Rate", "Dividend Amount"],
            axis=1,
        )
    
        return graph4
    
    
    # graph5
    # good
    @st.cache_data
    def get_graph5(*_, quarterly_series, mcap, start_date, **rest):
        price_to_book = quarterly_series["pb"]
        price_to_cashflow = quarterly_series["pfcfTTM"]
        price_to_sales = quarterly_series["psTTM"]
    
        verify_quarterly_data_irregularities(price_to_book, start_date)
        verify_quarterly_data_irregularities(price_to_cashflow, start_date)
        verify_quarterly_data_irregularities(price_to_sales, start_date)
    
        graph5 = pd.concat([price_to_book, price_to_cashflow, price_to_sales], keys=["Price to Book", "Price to Cashflow (TTM)", "Price to Sales (TTM)"], axis=1)
        graph5.index = pd.to_datetime(graph5.index, utc=True).date
    
        # see above
        graph5 = piecewise_op_search(graph5, mcap, lambda df1, df2: df1.div(df2, axis=0))
        graph5 = piecewise_op_search(mcap, graph5, lambda df1, df2: df2.mul(df1, axis=0))
    
        return graph5
    
    
    # graph6
    # ebit issue is issue with IBM
    @st.cache_data
    def get_graph6(*_, finnhub_reported_data, quarterly_series, ev, start_date, num_shares, **rest):
        verify_quarterly_data_irregularities(quarterly_series["ebitPerShare"], start_date)
        ebit = piecewise_op_search(
                quarterly_series["ebitPerShare"],
            num_shares,
            operator.mul,
            )
    
        ebit = ebit.rolling(4).sum()
    
        ev_ebit = piecewise_op_search(ev, ebit, operator.truediv)
        graph6 = ev_ebit.rename("EV / EBIT (TTM)").to_frame()
    
        return graph6
    
    
    # graph7
    @st.cache_data
    def get_graph7(*_, finnhub_reported_data, hprice, ticker_name, dividend_amount, start_date, num_shares, **rest):
        # todo: move into display logic?
        price_return = hprice.rename(ticker_name)[hprice.index >= start_date]
    
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
    def get_graph8(*_, finnhub_reported_data, quarterly_series, revenue, start_date, num_shares, **rest):
        revenue_ttm = revenue.rolling(4).sum()
        revenue_growth = revenue_ttm.rolling(5).apply(lambda a: a[4] - a[0])
        revenue_growth = (revenue_growth / revenue_growth[revenue_growth.index.searchsorted(start_date)]) - 1
    
        graph8 = revenue_growth.rename("Revenue Growth (YoY)").to_frame()
        return graph8
    
    
    # graph9
    @st.cache_data
    def get_graph9(*_, quarterly_series, **rest):
    
        graph9 = pd.concat(
            [
                quarterly_series["roeTTM"],
                quarterly_series["rotcTTM"],
                quarterly_series["roaTTM"],
            ],
            keys=[
                "RO Equity",
                "RO Total Capital",
                "RO Assets",
            ],
            axis=1,
        )
    
        return graph9
    
    
    # graph10
    @st.cache_data
    def get_graph10(*_, finnhub_reported_data, revenue, quarterly_series, **rest):
        revenue_ttm = revenue.rolling(4).sum()
    
        graph10 = pd.concat([revenue_ttm], keys=['Revenue (TTM)'], axis=1)
        return graph10
    
    
    # graph11
    @st.cache_data
    def get_graph11(*_, finnhub_reported_data, **rest):
        shares_outstanding_diluted = nan_default_chain(
            finnhub_reported_data,
            [
                "us-gaap_WeightedAverageNumberOfDilutedSharesOutstanding",
                "WeightedAverageNumberOfDilutedSharesOutstanding",
            ],
        )
    
        graph11 = shares_outstanding_diluted.rolling(4).mean().rename("Weighted Average Diluted Shares Outstanding (TTM)").to_frame()
    
        return graph11
    
    
    # graph12
    # sac tangible, book value and book value per share
    @st.cache_data
    def get_graph12(*_, finnhub_reported_data, quarterly_series, num_shares, **rest):
        book_value = quarterly_series["bookValue"] * 1000000
    
        book_share = piecewise_op_search(book_value, num_shares, operator.truediv)
    
        graph12 = pd.concat([book_share, book_value], keys=["BV per share", "Book Value"], axis=1)
    
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
            "title": "Market Cap, Enterprise Value",
        },
        {
            "title": "EPS: Diluted Before Extra (TTM)",
            "show_legend": False,
        },
        {
            "title": "1 Year Dividend Growth Rate, Dividend Amount",
        },
        {
            "title": "Price / Book, Price / Cash Flow (TTM), Price / Sales (TTM)",
        },
        {
            "title": "EV / EBIT (TTM)",
        },
        {
            "title": "Price Return, Total Return",
            "ypercent": True,
            "singleaxis": True,
        },
        {
            "title": "Revenue Growth (YoY)",
            "ypercent": True,
        },
        {
            "title": "Return on Equity (TTM), Return on Total Capital (TTM), Return on Assets (TTM)",
            "ypercent": True,
        },
        {
            "title": "Total Revenue (TTM)",
        },
        {
            "title": "Diluted Weighted Average Shares Outstanding (TTM)",
            "show_legend": False,
        },
        {
            "title": "Book Value / Share, Book Value",
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
           col2.dataframe(graph.iloc[-1])
           
           fig = go.Figure()
           layoutupdate = {}
           axes = []
           for col in graph:
               for i, axis in enumerate(axes):
                   if ("singleaxis" in data and data["singleaxis"]) or similar_range_to(graph[col], axis[1], axis[2]):
                       axes[i] = ([*axes[i][0], col], min(axis[1], graph[col].min()), max(axis[2], graph[col].max()))
                       break
               else:
                   axes.append(([col], graph[col].min(), graph[col].max()))
    
           for i, axis in enumerate(axes):
               label = str(i + 1) if i != 0 else ""
               for col in axis[0]:
                   fig.add_trace(go.Scatter(x=graph.index, y=graph[col], name=col,yaxis=f"y{label}"))
               layoutupdate[f"yaxis{label}"] = dict(title=', '.join(axis[0]), autoshift=True, title_standoff=10, shift=-30)
               if i != 0:
                   layoutupdate[f"yaxis{label}"]["tickmode"] = "sync"
                   layoutupdate[f"yaxis{label}"]["overlaying"] = "y"
                   layoutupdate[f"yaxis{label}"]["anchor"] = "free"
    
               if "ypercent" in data:
                   layoutupdate[f"yaxis{label}"]["tickformat"] =".2%"
    
           fig.update_layout(**layoutupdate, title=f"{ticker}: {data['title']}", hovermode="x", xaxis_title="Date", margin_l = 80 + 20 * len(axes))
    
           if "show_legend" in data:
               fig.update_layout(showlegend=data["show_legend"])
               fig.update_layout({"legend_title_text": "Legend"})
           col1.plotly_chart(fig, use_container_width=True)
    
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
