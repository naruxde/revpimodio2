# -*- coding: utf-8 -*-
"""Helper functions for all tests."""
__author__ = "Sven Sager"
__copyright__ = "Copyright (C) 2024 Sven Sager"
__license__ = "GPLv2"

import os
from signal import SIGINT
from threading import Thread
from time import sleep


class ChangeThread(Thread):
    """Thread to change IO values in background."""

    def __init__(self, revpi, ioname, iovalue, time):
        """Init ChangeThread-class."""
        super().__init__()
        self.revpi = revpi
        self.ioname = ioname
        self.time = time
        self.iovalue = iovalue

    def run(self):
        """Thread starten."""
        sleep(self.time)
        self.revpi.io[self.ioname].value = self.iovalue


class ExitSignal(Thread):
    """Call SIGINT after given time."""

    def __init__(self, time):
        """Signal SIGINT after given time."""
        super().__init__()
        self.time = time

    def run(self):
        sleep(self.time)
        os.kill(os.getpid(), SIGINT)


class ExitThread(Thread):
    """Call .exit() of ModIO after given time."""

    def __init__(self, revpi, time):
        """"""
        super().__init__()
        self.revpi = revpi
        self.time = time

    def run(self):
        sleep(self.time)
        self.revpi.exit()
