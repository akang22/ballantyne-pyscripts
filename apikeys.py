import dotenv
from enum import Enum


class ConfigKey(Enum):
    ALPHA_VANTAGE = "ALPHA_VANTAGE"
    FINNHUB = "FINNHUB"


def get_secret(key: ConfigKey):
    return dotenv.dotenv_values()[key.value]
