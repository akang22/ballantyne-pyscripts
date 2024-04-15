import bisect
import datetime
from dataclasses import dataclass
from enum import Enum
from pyxirr import xirr
from typing import Type


@dataclass
class Entry:
    amount: float
    date: datetime.date

    def __lt__(self, other: "Entry"):
        return self.date < other.date or (
            self.date == other.date and self.amount < other.amount
        )

    def split(self, negative=False):
        return (self.date, (-1 if negative else 1) * self.amount)


@dataclass
class DateRange:
    start: datetime.date
    end: datetime.date


class EntryList:
    def __init__(self):
        self.list_map = []

    def append(self, entry: Type[Entry]):
        bisect.insort_left(self.list_map, entry)

    def get_list(self, daterange: Type[DateRange]):
        print(daterange)
        x, y = (
            max(bisect.bisect_left(self.list_map, Entry(0, daterange.start)) - 1, 0),
            bisect.bisect_right(self.list_map, Entry(0, daterange.end)) + 1,
        )
        return self.list_map[x:y]


class Config:
    def __init__(self, config_map):
        self.config_map = config_map

    def get_keys(self):
        return self.config_map.keys()

    def compute_XIRR_table(self, entries: Type[EntryList]):
        ret_obj = {}
        for (name, daterange) in self.config_map.items():
            arr = entries.get_list(daterange)
            new_arr = (
                []
                if len(arr) < 2
                else [arr[0].split()]
                + [val.split(i) for i in [True, False] for val in arr[1:-1]]
                + [arr[-1].split(negative=True)]
            )
            ret_obj[name] = (xirr(new_arr) + 1) ** (
                min(1, (daterange.end - daterange.start).days / 365)
            ) - 1
        return ret_obj
