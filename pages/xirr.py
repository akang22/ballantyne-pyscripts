import streamlit as st
import pandas as pd
from xirr import main_func

st.title("XIRR Applet")
tabs = st.tabs(["CSV input", "Database Input (wip)", "Walkthrough (wip)"])

with st.sidebar:
    if st.button("Rerun"):
        st.rerun()

with tabs[0]:
    cashflow = st.file_uploader("Cashflows", type=["csv"])
    monthend = st.file_uploader("Month End Values", type=["csv"])
    starting = st.file_uploader("Account Starting Values", type=["csv"])

    st.markdown("### Custom Interval")
    start_date = st.date_input("Start Date", value=None)
    end_date = st.date_input("End Date", value=None)

for i, tab in enumerate(tabs[:-1]):
    submitted = tab.button("Submit", key=f"submit${i}")
    if submitted:
        res_data_frame, interim = main_func(
                cashflow, monthend, starting, return_interim=True, custom_intervals={f"testing"
                #{start_date} - {end_date}"
                                                                                     : (lambda d: pd.Timestamp(start_date), pd.Timestamp(end_date)) } if (start_date and end_date) else {}
        )
        tab.header("Final Result")
        tab.dataframe(res_data_frame, use_container_width=True)
        tab.header("Interim Results")
        for account, df in interim.items():
            tab.subheader(f"{account}")
            tab.dataframe(pd.DataFrame(df), use_container_width=True)
