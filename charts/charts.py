import collections
import datetime
import warnings

warnings.simplefilter(action='ignore', category=FutureWarning)
import operator

import finnhub
import numpy as np
import pandas as pd
import plotly.express as px
import streamlit as st
import yfinance as yf

from apikeys import ConfigKey, get_secret

st.title("StockCharts")

ticker_input = st.text_input("Ticker Value")

def flatten_report(report):
  return {'index': report['endDate'], **{v['concept']: v['value'] for sheet in report['report'].values() for v in sheet}}

finnhub_client = finnhub.Client(api_key=get_secret(ConfigKey.FINNHUB))
SP500DATA = yf.Ticker("^GSPC")

@st.cache_data
def get_ticker_data(ticker, start_date):
  yahoo_finance_info = yf.Ticker(ticker)
  finnhub_data = finnhub_client.company_basic_financials(ticker, 'all')

  data1 = pd.DataFrame([flatten_report(a) for a in finnhub_client.financials_reported(symbol=ticker, freq='annual')['data']]).set_index('index')[::-1]
  data2 = pd.DataFrame([flatten_report(a) for a in finnhub_client.financials_reported(symbol=ticker, freq='quarterly')['data']]).set_index('index')[::-1]
  finnhub_reported_data = pd.concat([data1, data2]).sort_index()
  finnhub_reported_data.index = pd.to_datetime(finnhub_reported_data.index, utc=True)

  hprice = yahoo_finance_info.history(period="max", auto_adjust=False)["Open"]
  SP500_hprice = SP500DATA.history(period="max", auto_adjust=False)["Open"]

  mapping = collections.defaultdict(dict)
  for k, v in finnhub_data['series']['quarterly'].items():
    for i in v:
      mapping[i['period']][k] = i['v']

  quarterly_series = pd.DataFrame(mapping).transpose()
  quarterly_series.index = pd.to_datetime(quarterly_series.index, utc=True)

  price_to_book = quarterly_series['pb']
  book_value = quarterly_series['bookValue']

  q_mcap = (book_value.mul(price_to_book, fill_value=np.NaN) * (10 ** 6))[::-1]
  q_mcap.index = pd.to_datetime(q_mcap.index, utc=True)
  q_mcap = q_mcap

  # so this may look stupid, multiply and divide by the same column, but this essentially is first dividing by
  # the values on the exact dates to 'normalize' the value, and then interpolate with the remaining prices as indexes.
  mcap = piecewise_op_search(hprice, piecewise_op_search(q_mcap, hprice, operator.truediv), operator.mul)

  num_shares = nan_default_chain(finnhub_reported_data, ['us-gaap_WeightedAverageNumberOfSharesOutstandingBasic', 'us-gaap_WeightedAverageNumberOfSharesOutstandingBasic'])

  q_ev = quarterly_series['ev']
  q_ev = q_ev[q_ev.index >= start_date][::-1] * 1000000

  ev = piecewise_op_search(q_ev, mcap, operator.sub)
  ev = piecewise_op_search(mcap, ev, operator.add)

  return { "hprice": hprice, "num_shares": num_shares, "ticker_name": ticker, "start_date": start_date, "ev": ev, "SP500_hprice": SP500_hprice, "quarterly_series": quarterly_series, "mcap": mcap, "finnhub_reported_data": finnhub_reported_data }


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

def nan_default_chain(data, key_list, fill_zeros=False):
  key_list = [key for key in key_list if key in data]
  ret = pd.Series(np.nan, index=data.index)
  for key in key_list:
    ret = ret.fillna(data[key])
  if fill_zeros:
    ret = ret.fillna(0)
  return ret

# todo: multiple axes with https://stackoverflow.com/questions/65037641/plotly-how-to-add-multiple-y-axes
# todo: add 'current' boxes with https://plotly.com/python/indicator/
# todo: clear up naming and [::-1]s, make functions less leaky

# graph1
@st.cache_data
def get_graph1(*_, start_date, hprice, ticker_name, SP500_hprice, **rest):
  price_return = (((hprice / hprice[hprice.index.searchsorted(start_date)]) - 1)).rename(ticker_name)
  SP500_return = (((SP500_hprice / SP500_hprice[SP500_hprice.index.searchsorted(start_date)]) - 1)).rename('SP 500')

  graph1 = pd.concat([SP500_return, price_return], axis=1)
  graph1.index = pd.to_datetime(graph1.index, utc=True)

  return graph1

# graph2
@st.cache_data
def get_graph2(*_, quarterly_series, mcap, ev, **rest):
  graph2 = pd.concat([ev, mcap], keys=['Enterprise Value', 'Market Cap'], axis=1)
  graph2.index = pd.to_datetime(graph2.index, utc=True)

  return graph2


# graph3
# multiple issues here. Firstly, data sucks (finnhub is missing 10-K sometimes, etc.)
# also, not sure how to add in 10-K values in? According to online the values are quarterly, but they seem to match the TTM values, sometimes. EPS data is just kinda off here.
@st.cache_data
def get_graph3(*_, finnhub_reported_data, **rest):
  eps_diluted = nan_default_chain(finnhub_reported_data, ['us-gaap_EarningsPerShareDiluted', 'EarningsPerShareDiluted', 'us-gaap_EarningsPerShareBasic', 'EarningsPerShareBasic'])
  graph3 = eps_diluted.rolling(4).sum().to_frame()

  return graph3

# graph4
# dividend amount is off, so is dividend growth rate (is it a ratio?)
@st.cache_data
def get_graph4(*_, finnhub_reported_data, num_shares, **rest):
  dividends = nan_default_chain(finnhub_reported_data, ['us-gaap_PaymentsOfDividendsCommonStock', 'PaymentsOfDividendsCommonStock'])
  ttm_dividends = dividends.rolling(4).sum()
  dividend_ratios = ttm_dividends.rolling(5).apply(lambda a: a[4] / a[0])

  dividend_amount = piecewise_op_search(dividends.cumsum(), num_shares, operator.truediv)

  graph4 = pd.concat([dividend_ratios, dividend_amount], keys=["1 Year Dividend Growth Rate", "Dividend Amount"], axis=1)

  dividend_ratios.to_frame()

  return graph4


# graph5
# good
@st.cache_data
def get_graph5(*_, quarterly_series, mcap, **rest):
  price_to_book = quarterly_series['pb']
  price_to_cashflow = quarterly_series['pfcfTTM']
  price_to_sales = quarterly_series['psTTM']

  graph5 = pd.concat([price_to_book, price_to_cashflow, price_to_sales], axis=1)[::-1]
  graph5.index = pd.to_datetime(graph5.index, utc=True)

  # see above
  graph5 = piecewise_op_search(graph5, mcap, lambda df1, df2: df1.div(df2, axis=0))
  graph5 = piecewise_op_search(mcap, graph5, lambda df1, df2: df2.mul(df1, axis=0))

  return graph5


# graph6
# we cannot do ebidta reliably with reported data.
# nor is ebit reliable, because ebitPerShare is negative sometimes
@st.cache_data
def get_graph6(*_, finnhub_reported_data, quarterly_series, ev, num_shares, **rest):
  num_shares = nan_default_chain(finnhub_reported_data, ['us-gaap_WeightedAverageNumberOfSharesOutstandingBasic', 'us-gaap_WeightedAverageNumberOfSharesOutstandingBasic'])
  ebit = piecewise_op_search(quarterly_series['ebitPerShare'][::-1].rolling(4).sum(), num_shares, operator.mul)

  ev_ebit = piecewise_op_search(ev, ebit, operator.truediv)
  graph6 = ev_ebit.to_frame()

  return graph6

# graph7
@st.cache_data
def get_graph7(*_, finnhub_reported_data, hprice, ticker_name, start_date, **rest):
  num_shares = nan_default_chain(finnhub_reported_data, ['us-gaap_WeightedAverageNumberOfSharesOutstandingBasic', 'us-gaap_WeightedAverageNumberOfSharesOutstandingBasic'])
  # todo: move into display logic?
  price_return = hprice.rename(ticker_name)[hprice.index >= start_date]

  dividends = nan_default_chain(finnhub_reported_data, ['us-gaap_PaymentsOfDividendsCommonStock', 'PaymentsOfDividendsCommonStock'])
  dividends_per_share = piecewise_op_search(num_shares, dividends, lambda a, b: b / a)
  dividends_per_share.iloc[0] = 0

  total_return = piecewise_op_search(price_return, dividends_per_share, operator.add)

  price_return = (price_return / hprice[hprice.index.searchsorted(start_date)]) - 1
  total_return = (total_return / total_return.iloc[0]) - 1

  graph7 = pd.concat([price_return, total_return], axis=1)

  return graph7


# graph8
# ebidta is not doable
# revenue may be a bit off
@st.cache_data
def get_graph8(*_, finnhub_reported_data, quarterly_series, **rest):
  num_shares = nan_default_chain(finnhub_reported_data, ['us-gaap_WeightedAverageNumberOfSharesOutstandingBasic', 'us-gaap_WeightedAverageNumberOfSharesOutstandingBasic'])
  revenue_ttm = piecewise_op_search(quarterly_series['salesPerShare'], num_shares.fillna(method='ffill'), operator.mul)[::-1].rolling(4).sum()
  revenue_growth = revenue_ttm.rolling(5).apply(lambda a: a[4] / a[0])

  graph8 = revenue_growth.to_frame()
  return graph8


# graph9
@st.cache_data
def get_graph9(*_, quarterly_series, **rest):
  graph9 = pd.concat([quarterly_series['roeTTM'], quarterly_series['rotcTTM'], quarterly_series['roaTTM']], axis=1)[::-1]

  return graph9


# graph10
# close enough, but a bit off bcuz of derivation inconsistency? (should we sac?)
@st.cache_data
def get_graph10(*_, finnhub_reported_data, quarterly_series, **rest):

  num_shares = nan_default_chain(finnhub_reported_data, ['us-gaap_WeightedAverageNumberOfSharesOutstandingBasic', 'us-gaap_WeightedAverageNumberOfSharesOutstandingBasic'])
  revenue_ttm = piecewise_op_search(quarterly_series['salesPerShare'], num_shares.fillna(method='ffill'), operator.mul)[::-1].rolling(4).sum()

  graph10 = revenue_ttm.to_frame()
  return graph10


# graph11
@st.cache_data
def get_graph11(*_, finnhub_reported_data, **rest):
  shares_outstanding_diluted = nan_default_chain(finnhub_reported_data, ['us-gaap_WeightedAverageNumberOfDilutedSharesOutstanding', 'WeightedAverageNumberOfDilutedSharesOutstanding'])

  graph11 = shares_outstanding_diluted.rolling(4).mean().to_frame()

  return graph11


# graph12
# debt: maybe figure something out with ratios
@st.cache_data
def get_graph12(*_, finnhub_reported_data, quarterly_series, **rest):
  book_value = quarterly_series['bookValue']

  num_shares = nan_default_chain(finnhub_reported_data, ['us-gaap_WeightedAverageNumberOfSharesOutstandingBasic', 'us-gaap_WeightedAverageNumberOfSharesOutstandingBasic'])
  book_share = piecewise_op_search(book_value, num_shares, operator.truediv) * 1000000
  tangible_book_value = quarterly_series['tangibleBookValue'] * 1000000

  graph12 = pd.concat([book_share, tangible_book_value], axis=1)[::-1]

  return graph12

graph_funcs = [get_graph1, get_graph2, get_graph3, get_graph4, get_graph5, get_graph6, get_graph7, get_graph8, get_graph9, get_graph10, get_graph11, get_graph12]


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
        "yaxis": "# shares",
        "show_legend": False,
    },
    {
        "title": "Book Value / Share, Tangible Book Value",
    },
]

ticker_vals = [val.strip() for val in ticker_input.split(',') if val.strip() != ""]

if len(ticker_vals) > 0:
  tabs = st.tabs(ticker_vals)
else:
  tabs = []
  st.text("Enter a stock above, or a series of stocks seperated by commas")

for ticker, tab in zip(ticker_vals, tabs):
  try:
    start_date = datetime.datetime(2021, 8, 22).replace(tzinfo=datetime.timezone.utc)
    ticker_data = get_ticker_data(ticker, start_date)
  except Exception as e:
    tab.error(f"Data could not be fetched. Double check the ticker {ticker} is correct.")
    tab.exception(e)
    continue

  for func, data in zip(graph_funcs, meta_info):
    try:
      graph = func(**ticker_data)
      graph = graph[graph.index >= start_date]

      fig = px.line(graph, title=(f"{ticker}: {data['title']}"))
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
      tab.plotly_chart(fig)

    except Exception as e:
      tab.error(f"Data could not be fetched. Double check the ticker {ticker} is correct.")
      tab.exception(e)
      continue
