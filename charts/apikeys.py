import dotenv
from enum import Enum
import streamlit


class ConfigKey(Enum):
    ALPHA_VANTAGE = "ALPHA_VANTAGE"
    FINNHUB = "FINNHUB"


def get_secret(key: ConfigKey):
    return streamlit.secrets[key.value]
    # return dotenv.dotenv_values()[key.value]