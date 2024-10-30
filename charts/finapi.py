import requests
from requests_cache import CachedSession

from apikeys import ConfigKey, get_secret
import pandas as pd
import datetime
import yfinance

# initialize perhaps with other things like useragent, retry, caching
r = CachedSession("finapi", expire_after=datetime.timedelta(hours=1))

FMP_DATE_FORMAT = "%Y-%m-%d"

# todo:
# add typing, data verification, etc decorators


def add_date_index(func):
    def new(*args, **kwargs):
        v = func(*args, **kwargs)
        if v is None:
            return v
        v.index = pd.to_datetime(v.index).date
        return v.iloc[::-1]

    return new


@add_date_index
def price(ticker: str):
    apikey = get_secret(ConfigKey.FMP)
    val = r.get(
        f"https://financialmodelingprep.com/api/v3/historical-price-full/{ticker}?apikey={apikey}"
    ).json()

    ret = []
    i = 0

    while len(val.get("historical", [])) > 0:
        i += 1
        ret.extend(val["historical"])
        last_date = datetime.datetime.strptime(
            val["historical"][-1]["date"], FMP_DATE_FORMAT
        ) - datetime.timedelta(days=1)

        val = r.get(
            f"https://financialmodelingprep.com/api/v3/historical-price-full/{ticker}?to={last_date.strftime(FMP_DATE_FORMAT)}&apikey={apikey}"
        ).json()
        if i > 40:
            break

    return pd.DataFrame(ret).set_index("date")["close"]


@add_date_index
def mcap(ticker: str):
    # todo: cache this
    apikey = get_secret(ConfigKey.FMP)
    val = r.get(
        f"https://financialmodelingprep.com/api/v3/historical-market-capitalization/{ticker}?apikey={apikey}"
    ).json()

    ret = []
    # prevent spam pinging their servers due to bugs
    i = 0
    while len(val) > 0:
        i += 1
        ret = [*ret, *(val)]
        last_date = datetime.datetime.strptime(
            val[-1]["date"], FMP_DATE_FORMAT
        ) - datetime.timedelta(days=1)
        val = r.get(
            f"https://financialmodelingprep.com/api/v3/historical-market-capitalization/{ticker}?to={last_date.strftime(FMP_DATE_FORMAT)}&apikey={apikey}"
        ).json()
        if i > 40:
            # stock lasted over 200 years? likely bug.
            break
    return pd.DataFrame(ret).set_index("date")["marketCap"]


@add_date_index
def _enterprise_vals(ticker: str):
    apikey = get_secret(ConfigKey.FMP)
    # todo, cache this result
    val = r.get(
        f"https://financialmodelingprep.com/api/v3/enterprise-values/{ticker}/?period=quarter&apikey={apikey}"
    ).json()

    return pd.DataFrame(val).set_index("date")


def enterprise_value(ticker: str):
    return _enterprise_vals(ticker)["enterpriseValue"]


def total_debt(ticker: str):
    return _enterprise_vals(ticker)["addTotalDebt"]


@add_date_index
def _income_statement(ticker: str):
    apikey = get_secret(ConfigKey.FMP)
    # todo, cache this result
    val = r.get(
        f"https://financialmodelingprep.com/api/v3/income-statement/{ticker}?period=quarter&apikey={apikey}"
    ).json()

    return pd.DataFrame(val).set_index("date")


def revenue(ticker: str):
    return _income_statement(ticker)["revenue"]


def eps(ticker: str):
    return _income_statement(ticker)["eps"]


def eps_diluted(ticker: str):
    return _income_statement(ticker)["epsdiluted"]


def weighted_average_shares_diluted_outstanding(ticker: str):
    return _income_statement(ticker)["weightedAverageShsOutDil"]


def ebitda(ticker: str):
    return _income_statement(ticker)["ebitda"]


def net_income(ticker: str):
    return _income_statement(ticker)["netIncome"]


@add_date_index
def dividends(ticker: str):
    apikey = get_secret(ConfigKey.FMP)
    val = r.get(
        f"https://financialmodelingprep.com/api/v3/historical-price-full/stock_dividend/{ticker}?apikey={apikey}"
    ).json()["historical"]
    # todo: make exception?
    if len(val) == 0:
        return None

    # todo: think if should use adj or not
    return pd.DataFrame(val).set_index("date")["dividend"]


@add_date_index
def _key_metrics(ticker: str):
    apikey = get_secret(ConfigKey.FMP)
    val = r.get(
        f"https://financialmodelingprep.com/api/v3/key-metrics/{ticker}?period=quarter&apikey={apikey}"
    ).json()

    # todo: think if should use adj or not
    return pd.DataFrame(val).set_index("date")


def price_earnings(ticker: str):
    return _ratios(ticker)["priceEarningsRatio"]
    # return _key_metrics(ticker)['peRatio']


def ev_ebitda(ticker: str):
    return _key_metrics(ticker)["enterpriseValueOverEBITDA"]


def book_value_share(ticker: str):
    return _key_metrics(ticker)["bookValuePerShare"]


def tangible_book_value(ticker: str):
    v = _key_metrics(ticker)

    v["tangibleBookValuePerShare"] = (
        v["tangibleBookValuePerShare"]
        / v["revenuePerShare"]
        / v["priceToSalesRatio"]
        * v["marketCap"]
    )

    return v["tangibleBookValuePerShare"].rename("tangibleBookValue")


@add_date_index
def _ratios(ticker: str):
    apikey = get_secret(ConfigKey.FMP)
    val = r.get(
        f"https://financialmodelingprep.com/api/v3/ratios/{ticker}?period=quarter&apikey={apikey}"
    ).json()

    # todo: think if should use adj or not
    return pd.DataFrame(val).set_index("date")


def ebit_revenue(ticker: str):
    return _ratios(ticker)["ebitPerRevenue"]


def price_book(ticker: str):
    return _ratios(ticker)["priceToBookRatio"]


def price_sales(ticker: str):
    return _ratios(ticker)["priceToSalesRatio"]


def price_cashflow(ticker: str):
    return _ratios(ticker)["priceCashFlowRatio"]


def return_assets(ticker: str):
    return _ratios(ticker)["returnOnAssets"]


def return_equity(ticker: str):
    return _ratios(ticker)["returnOnEquity"]


def return_total_capital(ticker: str):
    return _ratios(ticker)["returnOnCapitalEmployed"]
