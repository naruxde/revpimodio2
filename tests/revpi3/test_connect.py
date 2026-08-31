# -*- coding: utf-8 -*-
"""Tests for RevPi 4 devices."""
__author__ = "Sven Sager"
__copyright__ = "Copyright (C) 2024 Sven Sager"
__license__ = "GPLv2"

from os.path import dirname

from revpimodio2 import BLUE
from .. import TestRevPiModIO


class TestRevPiConnect(TestRevPiModIO):

    data_dir = dirname(__file__)

    def test_connect(self):
        """Test Connect functions."""
        for conf in ["config_connect.rsc", "config_connect_left.rsc"]:
            rpi = self.modio(configrsc=conf)

            def get_led_byte():
                self.fh_procimg.seek(6 if conf == "config_connect.rsc" else 119)
                return self.fh_procimg.read(1)

            # A3 am Connect testen
            rpi.core.A3 = 0
            self.assertEqual(rpi.core.A3, 0)
            rpi.core.A3 = 1
            self.assertEqual(rpi.io.RevPiLED.get_value(), b"\x10")
            self.assertEqual(rpi.core.A3, 1)
            rpi.writeprocimg()
            self.assertEqual(get_led_byte(), b"\x10")

            rpi.core.A2 = 0
            rpi.core.A2 = 1
            rpi.core.A3 = 2
            self.assertEqual(rpi.io.RevPiLED.get_value(), b"\x24")
            self.assertEqual(rpi.core.A3, 2)
            rpi.writeprocimg()
            self.assertEqual(get_led_byte(), b"\x24")

            rpi.core.A1 = 0
            rpi.core.A1 = 2
            self.assertEqual(rpi.io.RevPiLED.get_value(), b"\x26")
            rpi.writeprocimg()
            self.assertEqual(get_led_byte(), b"\x26")
            with self.assertRaises(ValueError):
                rpi.core.A3 = BLUE

            # Direct assignment must not work
            with self.assertRaises(AttributeError):
                rpi.core.a3green = True
            with self.assertRaises(AttributeError):
                rpi.core.a3green = True
            with self.assertRaises(AttributeError):
                rpi.core.wd = True
            with self.assertRaises(AttributeError):
                rpi.core.x2out = True
            with self.assertRaises(AttributeError):
                rpi.core.x2in = True

            # Test Hardware watchdog
            rpi.core.wd.value = True
            # Value: A1 = RED, A2 = GREEN, A3=RED + Bit 7
            self.assertEqual(rpi.io.RevPiLED.get_value(), b"\xa6")

            # Test output on connector X2 (Bit 6 on RevPiLED)
            self.assertFalse(rpi.core.x2out.value)
            rpi.core.x2out.value = True
            # Value: A1 = RED, A2 = GREEN, A3=RED + WD=True + Bit 6
            self.assertEqual(rpi.io.RevPiLED.get_value(), b"\xe6")
            rpi.writeprocimg()
            self.assertEqual(get_led_byte(), b"\xe6")
            self.assertTrue(rpi.core.x2out.value)

            # Test Input on connector X2 (Bit 6 on RevPiStatus)
            rpi.readprocimg()
            self.assertFalse(rpi.core.x2in.value)
            self.fh_procimg.seek(0 if conf == "config_connect.rsc" else 113)
            self.fh_procimg.write(b"\x40")
            rpi.readprocimg()
            self.assertTrue(rpi.core.x2in.value)
