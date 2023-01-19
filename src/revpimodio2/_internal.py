# -*- coding: utf-8 -*-
"""Internal functions and values for this package."""
__author__ = "Sven Sager"
__copyright__ = "Copyright (C) 2023 Sven Sager"
__license__ = "GPLv3"

# Global package values
OFF = 0
GREEN = 1
RED = 2
RISING = 31
FALLING = 32
BOTH = 33
INP = 300
OUT = 301
MEM = 302
PROCESS_IMAGE_SIZE = 4096


def acheck(check_type, **kwargs) -> None:
    """
    Check type of given arguments.

    Use the argument name as keyword and the argument itself as value.

    :param check_type: Type to check
    :param kwargs: Arguments to check
    """
    for var_name in kwargs:
        none_okay = var_name.endswith("_noneok")

        if not (isinstance(kwargs[var_name], check_type) or
                none_okay and kwargs[var_name] is None):
            msg = "Argument '{0}' must be {1}{2}".format(
                var_name.rstrip("_noneok"), str(check_type),
                " or <class 'NoneType'>" if none_okay else ""
            )
            raise TypeError(msg)


def consttostr(value) -> str:
    """
    Gibt <class 'str'> fuer Konstanten zurueck.

    Diese Funktion ist erforderlich, da enum in Python 3.2 nicht existiert.

    :param value: Konstantenwert
    :return: <class 'str'> Name der Konstanten
    """
    if value == 0:
        return "OFF"
    elif value == 1:
        return "GREEN"
    elif value == 2:
        return "RED"
    elif value == 31:
        return "RISING"
    elif value == 32:
        return "FALLING"
    elif value == 33:
        return "BOTH"
    elif value == 300:
        return "INP"
    elif value == 301:
        return "OUT"
    elif value == 302:
        return "MEM"
    else:
        return ""
