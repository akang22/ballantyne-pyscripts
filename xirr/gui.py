import streamlit as st
from main import main_func

st.title("XIRR Applet")
tabs = st.tabs(["Database Input (wip)", "CSV input", "Walkthrough (wip)"])

cashflow = tabs[1].file_uploader("Cashflows", type=["csv"])
monthend = tabs[1].file_uploader("Month End Values", type=["csv"])
starting = tabs[1].file_uploader("Account Starting Values", type=["csv"])

for i, tab in enumerate(tabs[:-1]):
    submitted = tab.button("Submit", key=f"submit${i}")
    if submitted:
        res_data_frame, interim = main_func(cashflow, monthend, starting, return_interim=True)
        tab.header("Final Result")
        tab.table(res_data_frame)
        tab.header("Interim Results")
        tab.table(interim)
