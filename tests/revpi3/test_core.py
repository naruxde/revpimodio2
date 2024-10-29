# -*- coding: utf-8 -*-
"""Tests for RevPi Core 1/3 devices."""
__author__ = "Sven Sager"
__copyright__ = "Copyright (C) 2024 Sven Sager"
__license__ = "GPLv2"

from os.path import dirname

from revpimodio2 import RED, GREEN, OFF, BLUE
from revpimodio2.io import IOBase, IntIO
from tests import TestRevPiModIO


class TestRevPiCore(TestRevPiModIO):

    data_dir = dirname(__file__)

    def test_core(self):
        """Test Core device."""
        rpi = self.modio(configrsc="config_core.rsc")

        # Test IOs of core device
        for io in rpi.core:
            self.assertIsInstance(io, IntIO)
            self.assertEqual(type(io.value), int)

        # Test CORE LEDs
        def get_led_byte():
            self.fh_procimg.seek(6)
            return self.fh_procimg.read(1)

        lst_test_led = [
            (rpi.core._get_leda1, rpi.core._set_leda1, GREEN, b"\x01"),
            (rpi.core._get_leda1, rpi.core._set_leda1, OFF, b"\x00"),
            (rpi.core._get_leda1, rpi.core._set_leda1, RED, b"\x02"),
            (rpi.core._get_leda2, rpi.core._set_leda2, GREEN, b"\x06"),
            (rpi.core._get_leda2, rpi.core._set_leda2, OFF, b"\x02"),
            (rpi.core._get_leda2, rpi.core._set_leda2, RED, b"\x0a"),
        ]
        for get_led, set_led, value, expected in lst_test_led:
            with rpi.io:
                set_led(value)
            self.assertEqual(rpi.io.RevPiLED.get_value(), expected)
            self.assertEqual(get_led_byte(), expected)
            self.assertEqual(get_led(), value)
            with self.assertRaises(ValueError):
                set_led(BLUE)

        # LED IOs after previews tests both read leds are on
        self.assertIsInstance(rpi.core.a1green, IOBase)
        self.assertIsInstance(rpi.core.a1red, IOBase)
        self.assertIsInstance(rpi.core.a2green, IOBase)
        self.assertIsInstance(rpi.core.a1red, IOBase)
        with self.assertRaises(AttributeError):
            rpi.core.a1green = True
        with self.assertRaises(AttributeError):
            rpi.core.a1red = True
        with self.assertRaises(AttributeError):
            rpi.core.a2green = True
        with self.assertRaises(AttributeError):
            rpi.core.a2red = True
        with rpi.io:
            self.assertTrue(rpi.core.a1red())
            self.assertFalse(rpi.core.a1green())
            self.assertTrue(rpi.core.a2red())
            self.assertFalse(rpi.core.a2green())

        # Software watchdog (same bit as hardware watchdog on connect 3)
        self.assertFalse(rpi.core.wd.value)
        rpi.core.wd_toggle()
        self.assertTrue(rpi.core.wd.value)

        self.assertIsInstance(rpi.core.status, int)
        self.assertIsInstance(rpi.core.picontrolrunning, bool)
        self.assertIsInstance(rpi.core.unconfdevice, bool)
        self.assertIsInstance(rpi.core.missingdeviceorgate, bool)
        self.assertIsInstance(rpi.core.overunderflow, bool)
        self.assertIsInstance(rpi.core.leftgate, bool)
        self.assertIsInstance(rpi.core.rightgate, bool)
        self.assertIsInstance(rpi.core.iocycle, int)
        self.assertIsInstance(rpi.core.temperature, int)
        self.assertIsInstance(rpi.core.frequency, int)
        self.assertIsInstance(rpi.core.ioerrorcount, int)
        self.assertIsInstance(rpi.core.errorlimit1, int)
        rpi.core.errorlimit1 = 10
        self.assertEqual(rpi.core.errorlimit1, 10)
        with self.assertRaises(ValueError):
            rpi.core.errorlimit1 = -1
        self.assertIsInstance(rpi.core.errorlimit2, int)
        rpi.core.errorlimit2 = 1100
        self.assertEqual(rpi.core.errorlimit2, 1100)
        with self.assertRaises(ValueError):
            rpi.core.errorlimit2 = 65999

    def test_core_old_errorlimits(self):
        """Test non-existing error limits of first core rap file."""
        with self.assertWarnsRegex(Warning, r"equal device name '.*' in pictory configuration."):
            rpi = self.modio(configrsc="config_old.rsc")

        # Errorlimits testen, die es nicht gibt (damals None, jetzt -1)
        self.assertEqual(rpi.core.errorlimit1, -1)
        self.assertEqual(rpi.core.errorlimit2, -1)

        with self.assertRaises(RuntimeError):
            rpi.core.errorlimit1 = 100
        with self.assertRaises(RuntimeError):
            rpi.core.errorlimit2 = 100

        del rpi
