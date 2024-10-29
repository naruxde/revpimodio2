# -*- coding: utf-8 -*-
"""Test mainloop functions."""
__author__ = "Sven Sager"
__copyright__ = "Copyright (C) 2024 Sven Sager"
__license__ = "GPLv2"

from os.path import dirname
from time import sleep

import revpimodio2
from tests import TestRevPiModIO
from tests.helper import ExitThread, ChangeThread

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


class TestMainloop(TestRevPiModIO):

    data_dir = dirname(__file__)

    def setUp(self):
        global event_data
        event_data = (None, None)
        super().setUp()

    def test_mainloop(self):
        """Test basic mainloop functions."""
        rpi = self.modio(debug=False)

        with self.assertRaises(RuntimeError):
            # Auto refresh not running
            rpi.mainloop()

        # Too long refresh time
        with self.assertRaises(ValueError):
            rpi._imgwriter.refresh = 4

        # Create events
        rpi.io.meldung0_7.reg_event(xxx)
        rpi.io.meldung8_15.reg_event(xxx_thread, as_thread=True)

        # Start mainloop
        rpi.autorefresh_all()
        rpi.mainloop(blocking=False)

        sleep(0.1)
        rpi.io.meldung0_7.value = 100
        sleep(0.06)
        self.assertEqual(event_data, ("meldung0_7", 100))
        rpi.io.meldung8_15.value = 200
        sleep(0.06)
        self.assertEqual(event_data, ("meldung8_15", 200))

        self.assertEqual(rpi.ioerrors, 0)

        rpi.exit()
        rpi.setdefaultvalues()
        sleep(0.05)

        # Remember old IO before replacing things for tests
        io_old = rpi.io.meldung0_7
        self.assertTrue(io_old in io_old._parentdevice._dict_events)
        self.assertTrue(io_old in rpi.device.virt01)

        rpi.io.meldung0_7.replace_io("test1", "?", event=xxx)
        rpi.io.meldung0_7.replace_io("test2", "?", bit=1, event=xxx)
        rpi.io.meldung0_7.replace_io("test3", "?", bit=2)
        rpi.io.meldung0_7.replace_io("test4", "?", bit=3, event=xxx, delay=300)
        rpi.io.meldung0_7.replace_io("test5", "?", bit=4, event=xxx_thread, as_thread=True)
        rpi.io.meldung0_7.replace_io(
            "test6", "?", bit=5, event=xxx_thread, as_thread=True, delay=200
        )

        rpi.io.magazin1.reg_timerevent(xxx, 200)
        rpi.io.test3.reg_timerevent(xxx, 200, edge=revpimodio2._internal.RISING)

        self.assertFalse(io_old in io_old._parentdevice._dict_events)
        self.assertFalse(io_old in rpi.device.virt01)

        rpi.autorefresh_all()
        rpi.mainloop(blocking=False)
        sleep(0.1)

        # Direct events
        rpi.io.test1.value = True
        sleep(0.06)
        self.assertEqual(event_data, ("test1", True))
        rpi.io.test2.value = True
        sleep(0.06)
        self.assertEqual(event_data, ("test2", True))

        # Timer events
        rpi.io.test3.value = True
        sleep(0.1)
        self.assertEqual(event_data, ("test2", True))
        rpi.io.test3.value = False
        sleep(0.15)
        self.assertEqual(event_data, ("test3", True))

        rpi.io.magazin1.value = 1
        rpi.io.test4.value = True
        sleep(0.1)
        self.assertEqual(event_data, ("test3", True))
        rpi.io.test4.value = False
        sleep(0.15)
        self.assertEqual(event_data, ("magazin1", 1))
        rpi.io.test4.value = True
        sleep(1)
        self.assertEqual(event_data, ("test4", True))

        rpi.io.test5.value = True
        rpi.io.test6.value = True
        sleep(0.1)
        self.assertEqual(event_data, ("test5", True))
        sleep(0.15)
        self.assertEqual(event_data, ("test6", True))

        self.assertFalse(rpi.exitsignal.is_set())

        rpi.exit(full=False)

        self.assertTrue(rpi.exitsignal.is_set())

        rpi.io.test1.unreg_event()
        rpi.io.test1.reg_event(xxx_timeout)

        sleep(0.3)

        # Exceed cylcle time in main loop
        with self.assertWarnsRegex(RuntimeWarning, r"io refresh time of 0 ms exceeded!"):
            rpi._imgwriter._refresh = 0.0001
            sleep(0.1)
        rpi.exit()

        del rpi

    def test_mainloop_bad_things(self):
        """Tests incorrect use of the mainloop."""
        rpi = self.modio(autorefresh=True)

        with self.assertRaises(TypeError):
            rpi._imgwriter._collect_events(1)

        # Bad event function without needed arguments
        rpi.io.meldung0_7.replace_io("test5", "?", bit=4, event=lambda: None)

        th = ChangeThread(rpi, "test5", True, 0.3)
        th.start()
        with self.assertRaises(TypeError):
            rpi.mainloop()

        sleep(0.1)

        rpi.io.meldung0_7.replace_io("test1", "?", event=xxx_timeout)
        th_ende = ExitThread(rpi, 1)
        th = ChangeThread(rpi, "test1", True, 0.3)
        th_ende.start()
        th.start()
        with self.assertWarnsRegex(
            RuntimeWarning, r"can not execute all event functions in one cycle"
        ):
            rpi.mainloop()

        rpi.autorefresh_all()
        rpi.mainloop(blocking=False)
        # Change cycletime while running a loop
        with self.assertRaisesRegex(
            RuntimeError, r"can not change cycletime when cycleloop or mainloop is"
        ):
            rpi.cycletime = 60

        # Start second loop
        with self.assertRaisesRegex(RuntimeError, r"can not start multiple loops mainloop"):
            rpi.cycleloop(lambda x: None)
        rpi.exit()

        # Test imgwriter monitoring
        rpi.autorefresh_all()
        sleep(0.2)
        rpi._imgwriter.stop()
        sleep(0.1)
        with self.assertRaisesRegex(RuntimeError, r"autorefresh thread not running"):
            rpi.mainloop()

        rpi.exit()

    def test_prefire(self):
        """Test reg_event with prefire parameter."""
        rpi = self.modio(autorefresh=True)

        rpi.io.fu_lahm.reg_event(xxx, prefire=True)
        self.assertFalse(rpi.io.fu_lahm.value)
        rpi.mainloop(blocking=False)
        sleep(0.1)

        # Registration without prefire is allowed while running mainloop
        rpi.io.fu_schnell.reg_event(xxx)
        with self.assertRaises(RuntimeError):
            # Registration with prefire ist not allowed while running mainloop
            rpi.io.Counter_1.reg_event(xxx, prefire=True)

        self.assertEqual(event_data, ("fu_lahm", False))
        rpi.cleanup()

        rpi = self.modio(autorefresh=True)
        rpi.io.Input_32.reg_event(xxx_thread, as_thread=True, prefire=True)
        rpi.mainloop(blocking=False)
        sleep(0.1)
        self.assertEqual(event_data, ("Input_32", False))
        rpi.cleanup()
