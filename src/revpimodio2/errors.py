# -*- coding: utf-8 -*-
"""Error classes of RevPiModIO."""
__author__ = "Sven Sager"
__copyright__ = "Copyright (C) 2023 Sven Sager"
__license__ = "LGPLv2"


class RevPiModIOError(Exception):
    """Base exception class for RevPiModIO errors."""

    pass


class DeviceNotFoundError(RevPiModIOError):
    """Raised when a requested device cannot be found in the configuration."""

    pass
