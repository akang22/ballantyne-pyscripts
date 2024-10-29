import streamlit as st
import pandas as pd
from charts import finapi
import plotly.graph_objects as go
from datetime import datetime, timedelta

tickers = [
    "A", "AAPL", "ADBE", "AMAT", "AMZN", "BAC", "BAM", "BN", "BDX", "BLK", 
    "BNS", "BX", "CM", "CNR.TO", "CP", "DE", "DHI", "DHR", "DIS", "DOL",
    "EW", "GOOG", "HD", "JPM", "MET", "MNST", "MSFT", "MSI", "NDAQ", "RY",
    "SHW", "SLF", "TD", "TIH.TO", "TMO", "TSM", "TXN", "TFII", "ULTA", "URI", 
    "WCN", "WFG"
]

purchase_dates = [
    "2018-12-31", "2018-12-31", "2018-12-31", "2018-12-31", "2018-12-31", "2018-12-31", 
    "2022-12-09", "2022-12-09", "2018-12-31", "2018-12-31", "2018-12-31", "2019-09-16", 
    "2018-12-31", "2018-12-31", "2018-12-31", "2022-06-15", "2024-05-16", "2018-12-31", 
    "2023-03-15", "2018-12-31", "2018-12-31", "2018-12-31", "2018-12-31", "2018-12-31", 
    "2022-02-10", "2021-03-16", "2018-12-31", "2020-05-21", "2018-12-31", "2018-12-31", 
    "2022-01-25", "2018-12-31", "2018-12-31", "2018-12-31", "2018-12-31", "2024-08-08", 
    "2018-12-31", "2024-05-16", "2022-11-09", "2022-01-25", "2018-12-31", "2018-12-31"
]

st.title("Stock Price Return vs. SP500 from Purchase Date")
date_filter_option = st.selectbox(
    "Select Date Range:",
    ["Since Purchase Date", "1 Month", "3 Months", "Year-to-Date", "1 Year"],
    index=0  # default
)

input_tickers = st.text_area("Enter Tickers (comma-separated):", value=", ".join(tickers))
input_dates = st.text_area("Enter Purchase Dates (comma-separated, YYYY-MM-DD):", value=", ".join(purchase_dates))

tickers = [ticker.strip() for ticker in input_tickers.split(",")]
purchase_dates = [date.strip() for date in input_dates.split(",")]

@st.cache_data
def plot_price_return_vs_sp500(ticker, purchase_date, start_date_filter):
    try:
        index_ticker = "XIU.TO" if ticker.endswith(".TO") else "SPY"
        
        ticker_price = finapi.price(ticker)
        index_price = finapi.price(index_ticker)
        
        purchase_date = pd.Timestamp(purchase_date).strftime("%Y-%m-%d")
        ticker_price.index = pd.to_datetime(ticker_price.index).strftime("%Y-%m-%d")
        index_price.index = pd.to_datetime(index_price.index).strftime("%Y-%m-%d")
        
        if purchase_date not in ticker_price.index or purchase_date not in index_price.index:
            st.error(f"No data available from {purchase_date} for {ticker} or {index_ticker}.")
            return None
        
        # adjust dates
        today = datetime.today()
        if start_date_filter == "1 Month":
            adjusted_start_date = today - timedelta(days=30)
        elif start_date_filter == "3 Months":
            adjusted_start_date = today - timedelta(days=90)
        elif start_date_filter == "1 Year":
            adjusted_start_date = today - timedelta(days=365)
        elif start_date_filter == "Year-to-Date":
            adjusted_start_date = datetime(today.year, 1, 1)
        else:  # Since Purchase Date
            adjusted_start_date = pd.Timestamp(purchase_date)

        ticker_price = ticker_price.loc[adjusted_start_date.strftime("%Y-%m-%d"):]
        index_price = index_price.loc[adjusted_start_date.strftime("%Y-%m-%d"):]

        ticker_return = (ticker_price / ticker_price.iloc[0]) - 1
        index_return = (index_price / index_price.iloc[0]) - 1
        
        returns_df = pd.concat([index_return, ticker_return], axis=1, keys=[index_ticker, ticker])
        
        fig = go.Figure()
        fig.add_trace(go.Scatter(x=returns_df.index, y=returns_df[index_ticker], mode="lines", name=index_ticker))
        fig.add_trace(go.Scatter(x=returns_df.index, y=returns_df[ticker], mode="lines", name=ticker))
        
        fig.update_layout(
            title=f"{ticker} Price Return vs {index_ticker} from {adjusted_start_date.strftime('%Y-%m-%d')}",
            xaxis_title="Date",
            yaxis_title="Return",
            hovermode="x unified"
        )

        return fig
    except KeyError:
        st.error(f"No data available for {ticker} on {purchase_date}.")
    except Exception as e:
        st.error(f"Error fetching data for {ticker}: {e}")
        return None


# Iterate through each ticker and purchase date and display the graph
for ticker, purchase_date in zip(tickers, purchase_dates):
    st.subheader(f"{ticker} Relative Stock Return")
    fig = plot_price_return_vs_sp500(ticker, purchase_date, date_filter_option)
    if fig:
        st.plotly_chart(fig, use_container_width=True)
