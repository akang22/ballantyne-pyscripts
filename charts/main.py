import yfinance as yf
import requests
import json
import matplotlib.pyplot as plt
import numpy as np
import datetime
import pandas as pd
import json
from apikeys import ConfigKey, get_secret

ticker_val = "MSFT"
# todo: write a general class to handle external API and their caches
# then use this to write a base class (here) to extract the data
# lastly, run it with graphs

# yahoo finance has incomplete info
# also, need to handle incomplete data in general: how to present to user beyond just an error?
# need more indicators
# add different axes depending on stock

yahoo_finance_info = yf.Ticker(ticker_val)

my_start_date = datetime.datetime(2022, 1, 1)

ret = []
SINCE_START = datetime.datetime(1000, 1, 1)

income_url = f"https://www.alphavantage.co/query?function=INCOME_STATEMENT&symbol={ticker_val}&apikey={get_secret(ConfigKey.ALPHA_VANTAGE)}"
income_data = json.loads(requests.get(income_url).text)
quarterly_income_data = pd.DataFrame.from_dict(
    income_data["quarterlyReports"]
).set_index("fiscalDateEnding")

balance_url = f"https://www.alphavantage.co/query?function=BALANCE_SHEET&symbol={ticker_val}&apikey={get_secret(ConfigKey.ALPHA_VANTAGE)}"
balance_data = json.loads(requests.get(balance_url).text)
quarterly_balance_data = pd.DataFrame.from_dict(
    balance_data["quarterlyReports"]
).set_index("fiscalDateEnding")

cashflow_url = f"https://www.alphavantage.co/query?function=CASH_FLOW&symbol={ticker_val}&apikey={get_secret(ConfigKey.ALPHA_VANTAGE)}"
cashflow_data = json.loads(requests.get(cashflow_url).text)
quarterly_cashflow_data = pd.DataFrame.from_dict(
    cashflow_data["quarterlyReports"]
).set_index("fiscalDateEnding")


def get_price_return_plot(start_date):
    vals = yahoo_finance_info.history(period="max", start=start_date)[["Open"]].rename(
        columns={"Open": ticker_val}
    )
    base = vals.iloc[0]
    returns = ((vals / base) - 1) * 100
    return lambda: returns.plot(kind="line", title="Price Return")


def get_eps_plot():
    # issue: data is somewhat limited. EG for MSFT it only goes to 2022
    vals = (
        yahoo_finance_info.quarterly_income_stmt.transpose()[["Diluted EPS"]]
        .rename(columns={"Diluted ¬¬EPS": ticker_val})
        .astype("float64")
    )
    # Note: Not sure if TTM.
    return lambda: vals.plot(kind="line", title="Diluted Before Extra")


def get_shares_plot(start_date):
    total_shares = yahoo_finance_info.get_shares_full(start=start_date)
    return lambda: total_shares.plot()


def get_price_ratios_plot(start_date):
    total_shares = yahoo_finance_info.get_shares_full(start=start_date)
    prices = yahoo_finance_info.history(period="max", start=SINCE_START)[["Open"]]
    prices = prices[prices.index < total_shares.index[-1]]
    # we could technically do this faster ourselves, just by checking (as it will be O(sum of both)), but length of market_caps is not that long so the log is probably dwarfed just by not doing in python. Also, likely not a bottleneck
    # TODO: make this some kind of function
    market_cap = prices.Open * np.array(
        total_shares[total_shares.index.searchsorted(prices.index)]
    )

    # note: these values are fiscal UNTIL, so make sure we have the right side.
    sales_ttm = (
        quarterly_income_data[["totalRevenue"]][::-1]
        .rolling(4)
        .sum()
        .rename(columns={"totalRevenue": "value"})
    )
    book = quarterly_balance_data[["totalShareholderEquity"]][::-1].rename(
        columns={"totalShareholderEquity": "value"}
    )
    cashflow_ttm = (
        quarterly_cashflow_data[["operatingCashflow"]][::-1]
        .rolling(4)
        .sum()
        .rename(columns={"operatingCashflow": "value"})
    )

    sales_ttm.index = pd.to_datetime(sales_ttm.index, utc=True)
    book.index = pd.to_datetime(book.index, utc=True)
    cashflow_ttm.index = pd.to_datetime(cashflow_ttm.index, utc=True)

    cut_market_cap = market_cap[
        (market_cap.index < sales_ttm.index[-1])
        & (market_cap.index < book.index[-1])
        & (market_cap.index < cashflow_ttm.index[-1])
    ]

    sales_index_vals = sales_ttm.iloc[sales_ttm.index.searchsorted(cut_market_cap.index)].astype("float64")
    book_index_vals = book.iloc[book.index.searchsorted(cut_market_cap.index)].astype("float64")
    cashflow_index_vals = cashflow_ttm.iloc[
        cashflow_ttm.index.searchsorted(cut_market_cap.index)
    ].astype("float64")

    vals = cut_market_cap.to_frame().assign(
        **{
            "Price/Sales (TTM)": cut_market_cap / sales_index_vals.value.values,
            "Price/Book": cut_market_cap / book_index_vals.value.values,
            "Price/Cashflow (TTM)": cut_market_cap / cashflow_index_vals.value.values,
        }
    ).drop(columns=['Open'])

    vals.index = vals.index.tz_convert(None)
    vals = vals[vals.index > start_date]
    global ret
    ret = vals
    
    return lambda: vals.plot(kind="line", title="Price/Sales, Price/Book, Price/Cashflow")


# url = f'https://www.alphavantage.co/query?function=EARNINGS&symbol={ticker_val}&apikey={get_secret(ConfigKey.ALPHA_VANTAGE)}'
# response = requests.get(url)
# data = json.loads(response.text)
