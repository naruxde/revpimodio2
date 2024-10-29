# -*- coding: utf-8 -*-
"""Test events."""
__author__ = "Sven Sager"
__copyright__ = "Copyright (C) 2024 Sven Sager"
__license__ = "GPLv2"

from os.path import dirname
from threading import Event
from time import sleep

from revpimodio2 import RISING, FALLING
from tests import TestRevPiModIO
from tests.helper import ChangeThread

event_data = (None, None)


def xxx(name, value):
    """Test event function."""
    global event_data
    event_data = (name, value)


class TestEvents(TestRevPiModIO):
    data_dir = dirname(__file__)

    def setUp(self):
        global event_data
        event_data = (None, None)
        super().setUp()

    def test_events(self):
        """Test event functions."""
        rpi = self.modio()

        with self.assertRaises(ValueError):
            rpi.io.magazin1.reg_event(xxx, edge=RISING)
        rpi.io.magazin1.reg_event(xxx)
        with self.assertRaises(RuntimeError):
            rpi.io.magazin1.reg_event(xxx)
        self.assertTrue(rpi.io.magazin1 in rpi.device.virt01._dict_events)
        rpi.io.magazin1.unreg_event()
        self.assertFalse(rpi.io.magazin1 in rpi.device.virt01._dict_events)

        with self.assertRaises(ValueError):
            rpi.io.v_druck.reg_event(None)
        with self.assertRaises(ValueError):
            rpi.io.v_druck.reg_event(xxx, delay=-100)
        rpi.io.v_druck.reg_event(xxx, delay=100, edge=RISING)
        with self.assertRaises(RuntimeError):
            rpi.io.v_druck.reg_event(xxx)
        with self.assertRaises(RuntimeError):
            rpi.io.v_druck.reg_event(xxx, edge=RISING)
        rpi.io.v_druck.reg_event(xxx, edge=FALLING, as_thread=True)
        rpi.io.v_druck.reg_event(lambda name, value: None, edge=FALLING, as_thread=True)
        self.assertEqual(len(rpi.device.do01._dict_events[rpi.io.v_druck]), 3)

        rpi.io.v_druck.unreg_event(xxx, RISING)

    def test_dd_timer_events(self):
        """Testet timer events."""
        rpi = self.modio()

        with self.assertRaises(ValueError):
            rpi.io.magazin1.reg_timerevent(xxx, 200, edge=RISING)
        rpi.io.magazin1.reg_timerevent(xxx, 200)
        with self.assertRaises(RuntimeError):
            rpi.io.magazin1.reg_timerevent(xxx, 200)
        rpi.io.magazin1.reg_timerevent(lambda name, value: None, 200)

        with self.assertRaises(ValueError):
            rpi.io.v_druck.reg_timerevent(None, 200)
        with self.assertRaises(ValueError):
            rpi.io.v_druck.reg_timerevent(xxx, -100)
        rpi.io.v_druck.reg_timerevent(xxx, 100, edge=RISING)
        with self.assertRaises(RuntimeError):
            rpi.io.v_druck.reg_timerevent(xxx, 200)
        with self.assertRaises(RuntimeError):
            rpi.io.v_druck.reg_timerevent(xxx, 200, edge=RISING)
        rpi.io.v_druck.reg_timerevent(xxx, 200, edge=FALLING, as_thread=True)

        self.assertEqual(len(rpi.device.do01._dict_events[rpi.io.v_druck]), 2)
        rpi.io.v_druck.unreg_event(xxx, RISING)
        self.assertEqual(len(rpi.device.do01._dict_events[rpi.io.v_druck]), 1)
        rpi.io.v_druck.unreg_event(xxx, FALLING)
        self.assertFalse(rpi.io.v_druck in rpi.device.do01._dict_events)
        rpi.io.magazin1.unreg_event()

    def test_dh_wait(self):
        """Test .wait functions of IOs."""
        rpi = self.modio()
        with self.assertRaises(RuntimeError):
            rpi.io.v_druck.wait()

        rpi.autorefresh_all()
        with self.assertRaises(ValueError):
            rpi.io.v_druck.wait(edge=30)
        with self.assertRaises(ValueError):
            rpi.io.v_druck.wait(edge=34)
        with self.assertRaises(TypeError):
            rpi.io.v_druck.wait(exitevent=True)
        with self.assertRaises(ValueError):
            rpi.io.v_druck.wait(timeout=-1)
        with self.assertRaises(ValueError):
            rpi.io.meldung0_7.wait(edge=RISING)

        self.assertEqual(rpi.io.v_druck.wait(okvalue=False), -1)
        self.assertEqual(rpi.io.v_druck.wait(timeout=100), 2)
        self.assertEqual(rpi.io.v_druck.wait(edge=RISING, timeout=100), 2)

        # Exit event caught
        x = Event()
        x.set()
        self.assertEqual(rpi.io.v_druck.wait(exitevent=x), 1)

        # Successful waiting
        th = ChangeThread(rpi, "fu_lahm", True, 0.5)
        th.start()

        self.assertEqual(rpi.io.fu_lahm.wait(), 0)

        th = ChangeThread(rpi, "fu_lahm", False, 0.3)
        th.start()
        th = ChangeThread(rpi, "fu_lahm", True, 0.6)
        th.start()

        self.assertEqual(rpi.io.fu_lahm.wait(edge=RISING), 0)

        # Error while refreshing IO data
        rpi._imgwriter.stop()
        self.assertEqual(rpi.io.v_druck.wait(timeout=100), 2)

        rpi.io.fu_lahm.value = False
        sleep(0.1)
        rpi.exit()
