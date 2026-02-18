# -*- coding: utf-8 -*-
"""Test for RevPi Compact."""
__author__ = "Sven Sager"
__copyright__ = "Copyright (C) 2024 Sven Sager"
__license__ = "GPLv2"

from os.path import dirname

import revpimodio2
from .. import TestRevPiModIO


class TestCompact(TestRevPiModIO):

    data_dir = dirname(__file__)

    def test_compact(self):
        rpi = self.modio(configrsc="config_compact.rsc")

        self.assertIsInstance(rpi.core, revpimodio2.device.Compact)

        # Check COMPACT LEDs
        self.assertEqual(rpi.io.RevPiLED.get_value(), b"\x00")
        rpi.core.A1 = revpimodio2.OFF
        self.assertEqual(rpi.core.A1, 0)
        rpi.core.A1 = revpimodio2.GREEN
        self.assertEqual(rpi.io.RevPiLED.get_value(), b"\x01")
        self.assertEqual(rpi.core.A1, 1)
        rpi.core.A1 = revpimodio2.RED
        self.assertEqual(rpi.io.RevPiLED.get_value(), b"\x02")
        self.assertEqual(rpi.core.A1, 2)
        with self.assertRaises(ValueError):
            rpi.core.A1 = 5

        rpi.core.A2 = revpimodio2.OFF
        self.assertEqual(rpi.core.A2, 0)
        self.assertEqual(rpi.io.RevPiLED.get_value(), b"\x02")
        rpi.core.A2 = revpimodio2.GREEN
        self.assertEqual(rpi.io.RevPiLED.get_value(), b"\x06")
        self.assertEqual(rpi.core.A2, 1)
        rpi.core.A2 = revpimodio2.RED
        self.assertEqual(rpi.io.RevPiLED.get_value(), b"\x0a")
        self.assertEqual(rpi.core.A2, 2)
        with self.assertRaises(ValueError):
            rpi.core.A2 = 5

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
        rpi = self.modio(configrsc="config_compact_bits.json")
        del rpi
