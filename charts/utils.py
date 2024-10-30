import math


def custom_round(x):
    try:
        return round(x, 3 - int(math.floor(math.log10(abs(x)))))
    except:
        return x
