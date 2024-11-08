# -*- coding: utf-8 -*-
"""Test cycle loop functions."""
__author__ = "Sven Sager"
__copyright__ = "Copyright (C) 2024 Sven Sager"
__license__ = "GPLv2"

from os.path import dirname, join
from time import sleep

import revpimodio2
from .. import TestRevPiModIO
from ..helper import ExitThread

event_data = (None, None)


def xxx(name, value):
    """Test event function."""
    global event_data
    event_data = (name, value)


def xxx_thread(th):
    """Test event function with thread."""
    global event_data
    event_data = (th.ioname, th.iovalue)
    th.stop()


def xxx_timeout(name, value):
    """Test event with long timeout."""
    sleep(0.1)


class TestCycleloop(TestRevPiModIO):

    data_dir = dirname(__file__)

    def setUp(self):
        global event_data
        event_data = (None, None)
        super().setUp()

    def test_cycleloop(self):
        """Testet Cycleloop-Funktion."""
        rpi = self.modio()
        with self.assertRaises(RuntimeError):
            rpi.cycleloop(zyklus, 51)

        rpi.autorefresh_all()
        with self.assertRaises(RuntimeError):
            rpi.cycleloop(False, 51)
        rpi.cycleloop(zyklus, 51)

        with self.assertRaises(TypeError):
            rpi.cycleloop(lambda: None)

        rpi.exit()

        rpi.autorefresh_all()
        sleep(0.1)
        rpi._imgwriter.stop()
        sleep(0.1)
        with self.assertRaisesRegex(RuntimeError, r"autorefresh thread not running"):
            rpi.cycleloop(zyklus)

        rpi.exit()

    def test_cycleloop_longtime(self):
        """Testet no data."""
        rpi = self.modio(autorefresh=True)
        rpi.debug = -1
        rpi._imgwriter.lck_refresh.acquire()
        th_ende = ExitThread(rpi, 4)
        th_ende.start()

        with self.assertWarnsRegex(
            RuntimeWarning, r"no new io data in cycle loop for 2500 milliseconds"
        ):
            rpi.cycleloop(zyklus)

        rpi.exit()

    def test_cycletools(self):
        rpi = self.modio()
        ct = revpimodio2.Cycletools(50, rpi)
        with self.assertRaises(TypeError):
            ct.changed("bad_value")
        with self.assertRaises(ValueError):
            ct.changed(rpi.io.magazin1, edge=revpimodio2._internal.RISING)
        del rpi

    def test_run_plc(self):
        self.assertEqual(
            revpimodio2.run_plc(
                zyklus,
                cycletime=30,
                procimg=self.fh_procimg.name,
                configrsc=join(self.data_dir, "config.rsc"),
            ),
            1,
        )


def zyklus(ct):
    """Cycle program for testing the cycle loop."""
    if ct.flag10c:
        ct.set_ton("test", 100)
        ct.set_tof("test", 100)
        ct.set_tp("test", 100)
        ct.set_tonc("testc", 3)
        ct.set_tofc("testc", 3)
        ct.set_tpc("testc", 3)

    ct.get_ton("test")
    ct.get_tof("test")
    ct.get_tp("test")
    ct.get_tonc("testc")
    ct.get_tofc("testc")
    ct.get_tpc("testc")

    t = ct.runtime

    # Check change
    ct.changed(ct.io.v_druck, edge=revpimodio2._internal.RISING)
    ct.changed(ct.io.magazin1)

    if ct.flag20c:
        return 1
