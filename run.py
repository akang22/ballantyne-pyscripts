import streamlit
import streamlit.runtime.scriptrunner.magic_funcs

import streamlit.web.bootstrap
import os, sys
from pages import aml, xirr
import app


if __name__ == "__main__":
    flag_options = {
        "server.port": 8501,
        "global.developmentMode": False,
    }

    streamlit.web.bootstrap.load_config_options(flag_options=flag_options)
    flag_options["_is_running_with_streamlit"] = True

    streamlit.web.bootstrap.run(
        "app.py",
        False,
        [],
        flag_options,
    )
