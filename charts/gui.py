import plotly.express as px
from apikeys import ConfigKey, get_secret
import pandas as pd


import finnhub
finnhub_client = finnhub.Client(api_key="cqlhvupr01qo3h6thdtgcqlhvupr01qo3h6thdu0")


a = finnhub_client.company_basic_financials('AAPL', 'all')

quarterly_series = a


