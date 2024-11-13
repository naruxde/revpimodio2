# -*- coding: utf-8 -*-
"""Test signals."""
__author__ = "Sven Sager"
__copyright__ = "Copyright (C) 2024 Sven Sager"
__license__ = "GPLv2"

from os.path import dirname

from .. import TestRevPiModIO
from ..helper import ExitSignal


class TestSignals(TestRevPiModIO):
    data_dir = dirname(__file__)

    def test_handle_signal_end(self):
        rpi = self.modio(autorefresh=True)
        rpi.io.v_druck.value = True

        def ende():
            rpi.io.v_druck.value = False

        rpi.handlesignalend(ende)

        th_ende = ExitSignal(1)
        th_ende.start()
        rpi.mainloop()

        self.assertFalse(rpi.io.v_druck.value)
