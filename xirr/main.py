import datetime
import pathlib

import dateutil
import numpy as np
import pandas as pd
import pyxirr


def expect(cond, message):
    if not cond:
        print(message)
        exit()


def get_monthend_date(date):
    return (date + dateutil.relativedelta.relativedelta(months=1)).replace(
        day=1
    ) + dateutil.relativedelta.relativedelta(days=-1)


def main_func(cashflow_file, monthend_file, starting_file, return_interim=False):
    cashflows = pd.read_csv(
        cashflow_file,
        parse_dates=["TRADDATE"],
    )
    month_end = pd.read_csv(
        monthend_file,
        parse_dates=["as_of_date"],
    )
    starting = pd.read_csv(
        starting_file,
        parse_dates=["STARTMV_DATE"],
    )
    return main_func_pds(cashflows, month_end, starting, return_interim=return_interim)


# TODO: add other options like dates
def main_func_pds(cashflows, month_end, starting, return_interim=False):
    custom_intervals = pd.read_csv(
        pathlib.Path(__file__).parent / "settings" / "intervals.csv",
        parse_dates=["StartDate", "EndDate"],
    )
    config = {
        "QD": lambda d: (
            d[1].replace(month=(((d[1].month - 1) // 3) * 3 + 1), day=1)
            + dateutil.relativedelta.relativedelta(days=-1),
            d[1],
        ),
        "YD": lambda d: (
            d[1].replace(month=1, day=1)
            + dateutil.relativedelta.relativedelta(days=-1),
            d[1],
        ),
        "XIRR-1": lambda d: (
            d[1] + dateutil.relativedelta.relativedelta(years=-1),
            d[1],
        ),
        "XIRR-3": lambda d: (
            d[1] + dateutil.relativedelta.relativedelta(years=-3),
            d[1],
        ),
        "XIRR-5": lambda d: (
            d[1] + dateutil.relativedelta.relativedelta(years=-5),
            d[1],
        ),
        "XIRR-10": lambda d: (
            d[1] + dateutil.relativedelta.relativedelta(years=-10),
            d[1],
        ),
        "XIRR-INC": lambda d: d,
        **{
            row.Name: lambda d: (row.StartDate, row.EndDate)
            for row in custom_intervals.itertuples()
        },
    }

    starting["PortCode"] = starting["PortCode"].astype("str").str.strip()
    cashflows["PortCode"] = cashflows["PortCode"].astype("str").str.strip()
    cashflows["TRANTYPE"] = cashflows["TRANTYPE"].astype("str").str.strip()
    month_end["PortCode"] = month_end["PortCode"].astype("str").str.strip()

    counts = starting["PortCode"].value_counts()

    expect(
        starting["PortCode"].is_unique,
        f"Expected 'PortCode' in startingMVs to be unique. However, port codes {', '.join([str(a) for a in counts[counts > 1].index.values])} are repeated.",
    )

    val_dict = {}
    ret = {}

    for account in starting["PortCode"]:
        # add + or - depending on transaction type
        aflows = (
            cashflows[cashflows["PortCode"] == account]
            .apply(
                lambda x: (
                    x.iloc[0],
                    x.iloc[1],
                    x.iloc[2],
                    x.iloc[3] * (-1 if x.iloc[2] == "WITHDRAWAL" else 1),
                ),
                axis=1,
                result_type="broadcast",
            )
            .rename(columns={"TRADDATE": "Date", "NETAMTC": "Value"})
        )

        aend = (
            month_end[month_end["PortCode"] == account]
            .rename(columns={"MarketValue": "Value", "as_of_date": "Date"})
            .apply(
                lambda x: (x.iloc[0], x.iloc[1], get_monthend_date(x.iloc[2])),
                axis=1,
                result_type="broadcast",
            )
        )
        aend = aend.loc[pd.to_datetime(aend["Date"]).dt.month % 3 == 0]
        final_date = aend["Date"].max()
        astart = starting[starting["PortCode"] == account].rename(
            columns={"OPENING_MKTVAL": "Value", "STARTMV_DATE": "Date"}
        )

        aflows = aflows[["Date", "Value"]]
        aflows["Type"] = 1
        aend = aend[["Date", "Value"]]
        aend["Type"] = 2
        astart = astart[["Date", "Value"]]
        astart["Type"] = 0

        vals = (
            pd.concat(
                [
                    astart,
                    aend,
                    aend.apply(
                        lambda x: (x.iloc[0], -x.iloc[1], x.iloc[2]),
                        axis=1,
                        result_type="broadcast",
                    ),
                    aflows,
                ]
            )
            .sort_values(["Date", "Type", "Value"], axis="index")
            .reset_index(drop=True)
        )

        # TODO: redo this
        # there arel ikely small bugs with cashflows on same day

        acc_dict = {}
        for name, get_bounds in config.items():
            if aend.empty:
                acc_dict[name] = None
                continue

            start_date, end_date = get_bounds((astart["Date"].min(), final_date))
            if astart["Date"].min() <= start_date and end_date <= final_date:
                # get rid of the first negative monthend and last positive monthend.
                index_or_neg1 = lambda x, y: x.index[y] if len(x.index) > 0 else -1
                first_index = index_or_neg1(
                    vals[
                        (start_date == vals["Date"])
                        & (vals["Value"] <= 0)
                        & (vals["Type"] == 2)
                    ],
                    0,
                )
                last_index = index_or_neg1(
                    vals[
                        (vals["Date"] == end_date)
                        & (vals["Value"] >= 0)
                        & (vals["Type"] == 2)
                    ],
                    -1,
                )
                try:
                    val = vals[
                        (vals.index > first_index) & (vals.index < last_index)
                    ].drop(["Type"], axis="columns")
                    acc_dict[name] = round(
                        (pyxirr.xirr(val) + 1)
                        ** (min(1, (end_date - start_date).days / 365))
                        - 1,
                        4,
                    )
                except Exception:
                    acc_dict[name] = None
            else:
                acc_dict[name] = None

        ret[account] = acc_dict

        val_dict[account] = vals

    ret_df = (
        pd.DataFrame(
            data={k: list(v.values()) for k, v in ret.items()}, index=config.keys()
        )
    ).transpose()
    if return_interim:
        return ret_df, val_dict
    return ret_df


if __name__ == "__main__":
    # TODO do cli shit
    # TODO more testing
    ret_df = main_func(
        pathlib.Path(__file__).parent / "data" / "CashFlows.csv",
        pathlib.Path(__file__).parent / "data" / "MonthEnd Market Values.csv",
        pathlib.Path(__file__).parent / "data" / "Starting Market Values.csv",
    )
    ret_df.to_csv("output.csv")
    print("Output saved to output.csv")
