# -*- coding: utf-8 -*-
"""Test RevPi Flat devices."""
__author__ = "Sven Sager"
__copyright__ = "Copyright (C) 2024 Sven Sager"
__license__ = "GPLv2"

from os.path import dirname

import revpimodio2
from .. import TestRevPiModIO


class TestFlat(TestRevPiModIO):

    data_dir = dirname(__file__)

    def test_flat(self):
        rpi = self.modio(configrsc="config_flat.rsc")
        rpi.setdefaultvalues()

        self.assertIsInstance(rpi.core, revpimodio2.device.Flat)

        # Check FLAT LEDs
        rpi.core.A1 = revpimodio2.OFF
        self.assertEqual(rpi.io.RevPiLED.get_value(), b"\x00\x00")
        self.assertEqual(rpi.core.A1, 0)
        rpi.core.A1 = revpimodio2.GREEN
        self.assertEqual(rpi.io.RevPiLED.get_value(), b"\x01\x00")
        self.assertEqual(rpi.core.A1, 1)
        rpi.core.A1 = revpimodio2.RED
        self.assertEqual(rpi.io.RevPiLED.get_value(), b"\x02\x00")
        self.assertEqual(rpi.core.A1, 2)
        with self.assertRaises(ValueError):
            rpi.core.A1 = 5

        rpi.core.A2 = revpimodio2.OFF
        self.assertEqual(rpi.core.A2, 0)
        rpi.core.A2 = revpimodio2.GREEN
        self.assertEqual(rpi.io.RevPiLED.get_value(), b"\x06\x00")
        self.assertEqual(rpi.core.A2, 1)
        rpi.core.A2 = revpimodio2.RED
        self.assertEqual(rpi.io.RevPiLED.get_value(), b"\x0a\x00")
        self.assertEqual(rpi.core.A2, 2)
        with self.assertRaises(ValueError):
            rpi.core.A2 = 5

        rpi.core.A3 = revpimodio2.OFF
        self.assertEqual(rpi.core.A3, 0)
        rpi.core.A3 = revpimodio2.GREEN
        self.assertEqual(rpi.io.RevPiLED.get_value(), b"\x1a\x00")
        self.assertEqual(rpi.core.A3, 1)
        rpi.core.A3 = revpimodio2.RED
        self.assertEqual(rpi.io.RevPiLED.get_value(), b"\x2a\x00")
        self.assertEqual(rpi.core.A3, 2)
        with self.assertRaises(ValueError):
            rpi.core.A3 = 5

        rpi.core.A4 = revpimodio2.OFF
        self.assertEqual(rpi.core.A4, 0)
        rpi.core.A4 = revpimodio2.GREEN
        self.assertEqual(rpi.io.RevPiLED.get_value(), b"\x6a\x00")
        self.assertEqual(rpi.core.A4, 1)
        rpi.core.A4 = revpimodio2.RED
        self.assertEqual(rpi.io.RevPiLED.get_value(), b"\xaa\x00")
        self.assertEqual(rpi.core.A4, 2)
        with self.assertRaises(ValueError):
            rpi.core.A4 = 5

        rpi.core.A5 = revpimodio2.OFF
        self.assertEqual(rpi.core.A5, 0)
        rpi.core.A5 = revpimodio2.GREEN
        self.assertEqual(rpi.io.RevPiLED.get_value(), b"\xaa\x01")
        self.assertEqual(rpi.core.A5, 1)
        rpi.core.A5 = revpimodio2.RED
        self.assertEqual(rpi.io.RevPiLED.get_value(), b"\xaa\x02")
        self.assertEqual(rpi.core.A5, 2)
        with self.assertRaises(ValueError):
            rpi.core.A5 = 5

        # Call special values
        self.assertIsInstance(rpi.core.temperature, int)
        self.assertIsInstance(rpi.core.frequency, int)
        rpi.core.wd_toggle()

        # Direct assignment not allowed
        with self.assertRaisesRegex(AttributeError, r"direct assignment is not supported"):
            rpi.core.a1green = True

        rpi.exit()
        del rpi

        # Bit piCtory config
        rpi = self.modio(configrsc="config_flat_bits.rsc")
        del rpi
