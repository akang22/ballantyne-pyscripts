import streamlit

import streamlit.web.bootstrap as bootstrap 
import os, sys
from pages import aml, xirr


def resolve_path(path):
    resolved_path = os.path.abspath(os.path.join(os.getcwd(), path))
    return resolved_path


if __name__ == "__main__":
    bootstrap.run("app.py", False, args=['run'], flag_options={})
