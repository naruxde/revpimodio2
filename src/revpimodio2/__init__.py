# -*- coding: utf-8 -*-
"""
Provides all classes for the RevolutionPi.

Webpage: https://revpimodio.org/

Provides classes for easy use of the Revolution Pi from
KUNBUS GmbH (https://revolutionpi.com/) . All I/Os are
read from the piCtory configuration and made directly accessible by their names.
For gateways, custom IOs can be configured across multiple bytes.
With the defined names, the desired data is accessed directly.
The user can register functions as events for all IOs. The module
executes these when data changes.
"""
__all__ = [
    "IOEvent",
    "RevPiModIO",
    "RevPiModIODriver",
    "RevPiModIOSelected",
    "run_plc",
    "RevPiNetIO",
    "RevPiNetIODriver",
    "RevPiNetIOSelected",
    "run_net_plc",
    "Cycletools",
    "EventCallback",
    "ProductType",
    "DeviceType",
    "AIO",
    "COMPACT",
    "DI",
    "DO",
    "DIO",
    "FLAT",
    "MIO",
]
__author__ = "Sven Sager <akira@revpimodio.org>"
__copyright__ = "Copyright (C) 2023 Sven Sager"
__license__ = "LGPLv2"

from .__about__ import __version__
from ._internal import *
from .helper import Cycletools, EventCallback
from .io import IOEvent
from .modio import RevPiModIO, RevPiModIODriver, RevPiModIOSelected, run_plc
from .netio import RevPiNetIO, RevPiNetIODriver, RevPiNetIOSelected, run_net_plc
from .pictory import ProductType, DeviceType, AIO, COMPACT, DI, DO, DIO, FLAT, MIO
