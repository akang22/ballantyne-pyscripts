import numpy as np
import pandas as pd
import datetime
import models
import pathlib

debug = print
def expect(cond, message):
    if not cond:
        debug(message)
        exit()

if __name__ == "__main__":
    # todo: make this based off a single date
    config = models.Config({
        "QD": models.DateRange(datetime.date(2024, 1, 1), datetime.date(2024, 3, 31)),
        "YD": models.DateRange(datetime.date(2024, 1, 1), datetime.date(2024, 3, 31)),
        "XIRR-1": models.DateRange(datetime.date(2023, 4, 1), datetime.date(2024, 3, 31)),
        "XIRR-3": models.DateRange(datetime.date(2021, 4, 1), datetime.date(2024, 3, 31)),
        "XIRR-5": models.DateRange(datetime.date(2019, 4, 1), datetime.date(2024, 3, 31)),
        "XIRR-10": models.DateRange(datetime.date(2018, 10, 1), datetime.date(2024, 3, 31)),
        "XIRR-INC": models.DateRange(datetime.date(2018, 10, 1), datetime.date(2024, 3, 31))

        })

    data = pd.read_excel((pathlib.Path(__file__).parent / 'test.xlsm').resolve(), sheet_name=None)

    ret = {}
    
    for df in data.values():
        for x, y in zip(*np.where(df.values == 'test_token')):
            debug(f"Found token at coordinates {(x, y)} on sheet {df}, parsing.")
            expect(df.iat[x + 1, y] == 'name:', f"Expected \"name:\" at cell {x+ 1, y}, found {df.iat[x + 1, y]}")
            expect(isinstance(df.iat[x+1, y+1], str), f"Expected string at cell {x + 1, y+1}, found {df.iat[x + 1, y+1]}")
            name = df.iat[x + 1, y + 1]
            expect(name not in ret, f"Found name {name} already in ret. Since this will override the previous value, have each name be unique.")
            expect(df.iat[x + 2, y] == 'amounts:', f"Expected \"amounts:\" at cell {x, y+1}, found {df.iat[x + 2, y]}")
            i = 3
            entry_list = models.EntryList()
            dates = []
            while df.iat[x + i, y] != 'end':
                val = df.iat[x + i, y]
                date = df.iat[x + i, y + 1]
                expect(isinstance(val, (int, float)), f"Expected cell {x + i, y} to contain a number, found {df.iat[x + i, y]}")
                try:
                    if (isinstance(date, datetime.datetime)):
                        entry_list.append(models.Entry(val, date.date()))
                    else:
                        entry_list.append(models.Entry(val, datetime.strptime(date, "%d-%m-%Y").date()))
                except: 
                    expect(False, f"Expected cell {x + i, y+ 1} to contain a date, found {df.iat[x + i, y + 1]}")
                i += 1

            # print(repr(entry_list.listMap))

            ret[name] = config.compute_XIRR_table(entry_list)

    ret_df = pd.DataFrame(data={k : list(v.values()) for k, v in ret.items()}, index=config.get_keys())
    ret_df.to_csv('out.csv')
