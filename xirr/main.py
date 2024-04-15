import numpy as np
import pandas as pd
import datetime
import models
import pathlib
import dateutil

debug = print


def expect(cond, message):
    if not cond:
        debug(message)
        exit()


if __name__ == "__main__":
    # todo: make this based off a single date
    config = models.Config(
        {
            "QD": lambda d: d.replace(month=(((d.month - 1) // 3) * 3 + 1), day=1)
            + dateutil.relativedelta.relativedelta(days=-1),
            "YD": lambda d: d.replace(month=1, day=1)
            + dateutil.relativedelta.relativedelta(days=-1),
            "XIRR-1": lambda d: d + dateutil.relativedelta.relativedelta(years=-1),
            "XIRR-3": lambda d: d + dateutil.relativedelta.relativedelta(years=-3),
            "XIRR-5": lambda d: d + dateutil.relativedelta.relativedelta(years=-5),
            "XIRR-10": lambda d: d + dateutil.relativedelta.relativedelta(years=-10),
            "XIRR-INC": lambda d: d + dateutil.relativedelta.relativedelta(years=-1000),
        }
    )

    data = pd.read_excel(
        (pathlib.Path(__file__).parent / "test.xlsm").resolve(), sheet_name=None
    )

    ret = {}

    for df in data.values():
        for x, y in zip(*np.where(df.values == "test_token")):
            debug(f"Found token at coordinates {(x, y)} on sheet {df}, parsing.")
            expect(
                df.iat[x + 1, y] == "name:",
                f'Expected "name:" at cell {x+ 1, y}, found {df.iat[x + 1, y]}',
            )
            expect(
                isinstance(df.iat[x + 1, y + 1], str),
                f"Expected string at cell {x + 1, y+1}, found {df.iat[x + 1, y+1]}",
            )
            name = df.iat[x + 1, y + 1]
            expect(
                name not in ret,
                f"Found name {name} already in ret. Since this will override the previous value, have each name be unique.",
            )
            expect(
                df.iat[x + 2, y] == "amounts:",
                f'Expected "amounts:" at cell {x, y+1}, found {df.iat[x + 2, y]}',
            )
            i = 3
            entry_list = models.EntryList()
            dates = []
            while df.iat[x + i, y] != "end":
                val = df.iat[x + i, y]
                date = df.iat[x + i, y + 1]
                expect(
                    isinstance(val, (int, float)),
                    f"Expected cell {x + i, y} to contain a number, found {df.iat[x + i, y]}",
                )
                try:
                    if isinstance(date, datetime.datetime):
                        entry_list.append(models.Entry(val, date.date()))
                    else:
                        entry_list.append(
                            models.Entry(
                                val, datetime.strptime(date, "%d-%m-%Y").date()
                            )
                        )
                except:
                    expect(
                        False,
                        f"Expected cell {x + i, y+ 1} to contain a date, found {df.iat[x + i, y + 1]}",
                    )
                i += 1

            ret[name] = config.compute_XIRR_table(entry_list)

    ret_df = (
        pd.DataFrame(
            data={k: list(v.values()) for k, v in ret.items()}, index=config.get_keys()
        )
    ).transpose()
    ret_df_percent = (ret_df * 100).round(2).map(lambda x: f"{x}%")
    ret_df_percent.to_csv("output.csv")
