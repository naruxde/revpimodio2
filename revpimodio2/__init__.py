# -*- coding: utf-8 -*-
"""
Stellt alle Klassen fuer den RevolutionPi zur Verfuegung.

Webpage: https://revpimodio.org/

Stellt Klassen fuer die einfache Verwendung des Revolution Pis der
Kunbus GmbH (https://revolution.kunbus.de/) zur Verfuegung. Alle I/Os werden
aus der piCtory Konfiguration eingelesen und mit deren Namen direkt zugreifbar
gemacht. Fuer Gateways sind eigene IOs ueber mehrere Bytes konfigurierbar
Mit den definierten Namen greift man direkt auf die gewuenschten Daten zu.
Auf alle IOs kann der Benutzer Funktionen als Events registrieren. Diese
fuehrt das Modul bei Datenaenderung aus.
"""
__all__ = [
    "RevPiModIO", "RevPiModIODriver", "RevPiModIOSelected", "run_plc",
    "RevPiNetIO", "RevPiNetIODriver", "RevPiNetIOSelected",
    "Cycletools", "EventCallback",
    "AIO", "COMPACT", "DI", "DO", "DIO", "FLAT",
]
__author__ = "Sven Sager <akira@revpimodio.org>"
__copyright__ = "Copyright (C) 2020 Sven Sager"
__license__ = "LGPLv3"
__name__ = "revpimodio2"
__version__ = "2.5.7"

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


class DeviceNotFoundError(Exception):
    """Fehler wenn ein Device nicht gefunden wird."""

    pass


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


# Benötigte Klassen importieren
from .pictory import AIO, COMPACT, DI, DO, DIO, FLAT
from .helper import Cycletools, EventCallback
from .modio import RevPiModIO, RevPiModIODriver, RevPiModIOSelected, run_plc
from .netio import RevPiNetIO, RevPiNetIODriver, RevPiNetIOSelected
