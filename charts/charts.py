import collections
import datetime
import operator

import pandas as pd
import plotly.express as px
import numpy as np
import streamlit as st

import finnhub
import yfinance as yf

from apikeys import ConfigKey, get_secret

st.title("StockCharts")

ticker_val = st.text_input("Ticker Value", value="IBM")

graphs = []

finnhub_client = finnhub.Client(api_key=get_secret(ConfigKey.FINNHUB))
SP500DATA = yf.Ticker("^GSPC")
start_date = datetime.datetime(2021, 9, 1).replace(tzinfo=datetime.timezone.utc)
yahoo_finance_info = yf.Ticker(ticker_val)

finnhub_data = finnhub_client.company_basic_financials(ticker_val, "all")


def flatten_report(report):
    return {
        "index": report["endDate"],
        **{
            v["concept"]: v["value"]
            for sheet in report["report"].values()
            for v in sheet
        },
    }


finnhub_reported_data = pd.DataFrame(
    [
        flatten_report(a)
        for a in finnhub_client.financials_reported(
            symbol=ticker_val, freq="quarterly"
        )["data"]
    ]
).set_index("index")[::-1]
finnhub_reported_data.index = pd.to_datetime(finnhub_reported_data.index, utc=True)

hprice = yahoo_finance_info.history(period="max", start=start_date)[["Open"]]

mapping = collections.defaultdict(dict)
for k, v in finnhub_data["series"]["quarterly"].items():
    for i in v:
        mapping[i["period"]][k] = i["v"]

quarterly_series = pd.DataFrame(mapping).transpose()
quarterly_series.index = pd.to_datetime(quarterly_series.index, utc=True)

price_to_book = quarterly_series["pb"]
price_to_cashflow = quarterly_series["pfcfTTM"]
price_to_sales = quarterly_series["psTTM"]
book_value = quarterly_series["bookValue"]


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


def nan_default_chain(data, key_list, name=""):
    key_list = [key for key in key_list if key in data]
    ret = data[key_list[0]]
    for key in key_list[1:]:
        ret = ret.fillna(data[key])
    return ret.rename(name)


q_mcap = (book_value.mul(price_to_book, fill_value=np.NaN) * (10**6))[::-1]
q_mcap.index = pd.to_datetime(q_mcap.index, utc=True)
q_mcap = q_mcap[q_mcap.index >= start_date]

# so this may look stupid, multiply and divide by the same column, but this essentially is first dividing by
# the values on the exact dates to 'normalize' the value, and then interpolate with the remaining prices as indexes.
mcap = piecewise_op_search(
    hprice["Open"],
    piecewise_op_search(q_mcap, hprice["Open"], operator.truediv),
    operator.mul,
)

# todo: multiple axes with https://stackoverflow.com/questions/65037641/plotly-how-to-add-multiple-y-axes
# todo: add 'current' boxes with https://plotly.com/python/indicator/
# todo: clear up naming and [::-1]s, make functions less leaky

# graph1
SP500_return = SP500DATA.history(period="max", start=start_date)[["Open"]].rename(
    columns={"Open": "SP 500"}
)
price_return = hprice.rename(columns={"Open": ticker_val})

price_return = (price_return / price_return.iloc[0]) - 1
SP500_return = (SP500_return / SP500_return.iloc[0]) - 1

graph1 = pd.concat([SP500_return, price_return], axis=1)
graph1.index = pd.to_datetime(graph1.index, utc=True)

graphs.append((graph1))


# graph2
q_ev = quarterly_series["ev"]
q_ev = q_ev[q_ev.index >= start_date][::-1] * 1000000

ev = piecewise_op_search(q_ev, mcap, operator.sub)
ev = piecewise_op_search(mcap, ev, operator.add)

graph2 = pd.concat([ev, mcap], keys=["Enterprise Value", "Market Cap"], axis=1)
graph2.index = pd.to_datetime(graph2.index, utc=True)

graphs.append((graph2))


# graph3
# note: SA seems to be using sum
eps_diluted = nan_default_chain(
    finnhub_reported_data,
    [
        "us-gaap_EarningsPerShareDiluted",
        "EarningsPerShareDiluted",
        "us-gaap_EarningsPerShareBasic",
        "EarningsPerShareBasic",
    ],
    "Earnings Per Share",
)
graph3 = eps_diluted.rolling(4).sum().to_frame()

graphs.append((graph3))


# graph4
# btw, what is dividend amount? because it's measured as a ratio, and is always increasing?
dividends = nan_default_chain(
    finnhub_reported_data,
    ["us-gaap_PaymentsOfDividendsCommonStock", "PaymentsOfDividendsCommonStock"],
    "Dividend Ratio (YoY)",
)
ttm_dividends = dividends.rolling(4).sum()
dividend_ratios = ttm_dividends.rolling(5).apply(lambda a: a[4] / a[0])

graph4 = dividend_ratios.to_frame()

graphs.append((graph4))


# graph5
graph5 = pd.concat([price_to_book, price_to_cashflow, price_to_sales], axis=1)[::-1]
graph5.index = pd.to_datetime(graph5.index, utc=True)

# see above
graph5 = piecewise_op_search(graph5, mcap, lambda df1, df2: df1.div(df2, axis=0))
graph5 = piecewise_op_search(mcap, graph5, lambda df1, df2: df2.mul(df1, axis=0))

graphs.append((graph5))


# graph6
# we cannot do ebidta reliably with reported data.

num_shares = nan_default_chain(
    finnhub_reported_data,
    [
        "us-gaap_WeightedAverageNumberOfSharesOutstandingBasic",
        "us-gaap_WeightedAverageNumberOfSharesOutstandingBasic",
    ],
)
ebit = piecewise_op_search(
    quarterly_series["ebitPerShare"][::-1].rolling(4).sum(), num_shares, operator.mul
)

ev_ebit = piecewise_op_search(ev, ebit, operator.truediv).rename("EV / EBIT (TTM)")
graph6 = ev_ebit.to_frame()

graphs.append((graph6))


# graph7

price_return = hprice.rename(columns={"Open": "Price Return"})

dividends_per_share = piecewise_op_search(
    num_shares[num_shares.index >= start_date],
    dividends[dividends.index >= start_date].cumsum(),
    lambda a, b: b / a,
)
dividends_per_share.iloc[0] = 0

total_return = piecewise_op_search(
    price_return.iloc[:, 0], dividends_per_share, operator.add
)

price_return = (price_return / price_return.iloc[0]) - 1
total_return = ((total_return / total_return.iloc[0]) - 1).rename("Total Return")

graph7 = pd.concat([price_return, total_return], axis=1)

graphs.append((graph7))


# graph8

revenue_ttm = (
    piecewise_op_search(
        quarterly_series["salesPerShare"],
        num_shares.fillna(method="ffill"),
        operator.mul,
    )[::-1]
    .rolling(4)
    .sum()
)
revenue_growth = (
    revenue_ttm.rolling(5).apply(lambda a: a[4] / a[0]).rename("Revenue Growth (YoY)")
)

graph8 = revenue_growth[revenue_growth.index > start_date].to_frame()

graphs.append((graph8))


# graph9

graph9 = pd.concat(
    [
        quarterly_series["roeTTM"],
        quarterly_series["rotcTTM"],
        quarterly_series["roaTTM"],
    ],
    axis=1,
)[::-1]
graph9 = graph9[graph9.index >= start_date]

graphs.append((graph9))


# graph10

revenue_ttm = (
    piecewise_op_search(
        quarterly_series["salesPerShare"],
        num_shares.fillna(method="ffill"),
        operator.mul,
    )[::-1]
    .rolling(4)
    .sum()
).rename("Total Revenue (TTM)")

graph10 = revenue_ttm[revenue_ttm.index > start_date].to_frame()

graphs.append((graph10))


# graph11

shares_outstanding_diluted = nan_default_chain(
    finnhub_reported_data,
    [
        "us-gaap_WeightedAverageNumberOfDilutedSharesOutstanding",
        "WeightedAverageNumberOfDilutedSharesOutstanding",
    ],
)

graph11 = shares_outstanding_diluted.rolling(4).sum().to_frame()
graph11 = graph11[graph11.index >= start_date]

graphs.append(graph11)


# graph12
# debt: maybe figure something out with ratios
# also need axes
book_share = (
    piecewise_op_search(book_value, num_shares, operator.truediv).rename("Book / Share")
    * 1000000
)
tangible_book_value = quarterly_series["tangibleBookValue"] * 1000000

graph12 = pd.concat([book_share, tangible_book_value], axis=1)[::-1]
graph12 = graph12[graph12.index >= start_date]

graphs.append((graph12))

meta_info = [
    {
        "title": "Price Return",
        "ypercent": True,
    },
    {
        "title": "Market Cap, Enterprise Value",
        "yaxis": "USD",
    },
    {
        "title": "EPS: Diluted Before Extra (TTM)",
        "show_legend": False,
    },
    {
        "title": "1 Year Dividend Growth Rate",
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
    },
    {
        "title": "Revenue Growth (YoY)",
    },
    {
        "title": "Return on Equity (TTM), Return on Total Capital (TTM), Return on Assets (TTM)",
        "ypercent": True,
    },
    {
        "title": "Total Revenue (TTM), Net Income (TTM)",
    },
    {
        "title": "Diluted Weighted Average Shares Outstanding (TTM)",
        "yaxis": "# shares",
        "show_legend": False,
    },
    {
        "title": "Book Value / Share, Tangible Book Value",
    },
]

for graph, data in zip(graphs, meta_info):
    st.dataframe(graph.iloc[-1])
    fig = px.line(graph, title=data["title"])
    fig.update_layout(xaxis_title="Date")
    if "show_legend" in data:
        fig.update_layout(showlegend=data["show_legend"])
        fig.update_layout({"legend_title_text": "Legend"})
    if "ypercent" in data:
        fig.update_layout(yaxis_tickformat=".2%")
    if "yaxis" in data:
        fig.update_layout(yaxis_title=data["yaxis"])
    else:
        fig.update_layout(yaxis_title="")
    st.plotly_chart(fig)
