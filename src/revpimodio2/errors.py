# -*- coding: utf-8 -*-
"""Error classes of RevPiModIO."""
__author__ = "Sven Sager"
__copyright__ = "Copyright (C) 2023 Sven Sager"
__license__ = "LGPLv3"


class RevPiModIOError(Exception):
    pass


class DeviceNotFoundError(RevPiModIOError):
    pass
