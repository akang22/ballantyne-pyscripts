import streamlit as st
import pandas as pd
from main import main_func

st.title("XIRR Applet")
tabs = st.tabs(["CSV input", "Database Input (wip)",  "Walkthrough (wip)"])

cashflow = tabs[0].file_uploader("Cashflows", type=["csv"])
monthend = tabs[0].file_uploader("Month End Values", type=["csv"])
starting = tabs[0].file_uploader("Account Starting Values", type=["csv"])

for i, tab in enumerate(tabs[:-1]):
    submitted = tab.button("Submit", key=f"submit${i}")
    if submitted:
        res_data_frame, interim = main_func(cashflow, monthend, starting, return_interim=True)
        tab.header("Final Result")
        tab.dataframe(res_data_frame, use_container_width=True)
        tab.header("Interim Results")
        for account, df in interim.items():
            tab.subheader(f"{account}")
            tab.dataframe(pd.DataFrame(df), use_container_width=True)
