# -*- coding: utf-8 -*-
"""Tests for RevPi 4 devices."""
__author__ = "Sven Sager"
__copyright__ = "Copyright (C) 2024 Sven Sager"
__license__ = "GPLv2"

from os.path import join, dirname

import revpimodio2
from tests import TestRevPiModIO


class TestRevPi4(TestRevPiModIO):

    data_dir = dirname(__file__)

    def test_connect4(self):
        rpi = self.modio(configrsc="config_connect4.rsc")
        rpi.setdefaultvalues()

        self.assertIsInstance(rpi.core, revpimodio2.device.Connect4)

        # Test all LED (A1 - A5) with all colors
        lst_led_test = [
            (rpi.core._get_leda1, rpi.core._set_leda1),
            (rpi.core._get_leda2, rpi.core._set_leda2),
            (rpi.core._get_leda3, rpi.core._set_leda3),
            (rpi.core._get_leda4, rpi.core._set_leda4),
            (rpi.core._get_leda5, rpi.core._set_leda5),
        ]
        for i in range(len(lst_led_test)):
            get_led = lst_led_test[i][0]
            set_led = lst_led_test[i][1]
            for k in (
                (revpimodio2.GREEN, 2),
                (revpimodio2.RED, 1),
                (revpimodio2.BLUE, 4),
                (revpimodio2.OFF, 0),
            ):
                set_led(k[0])
                self.assertEqual(
                    rpi.io.RevPiLED.get_value(),
                    (k[1] << (i * 3)).to_bytes(2, "little"),
                )
                self.assertEqual(get_led(), k[0])
            with self.assertRaises(ValueError):
                set_led(8)

        self.assertIsInstance(rpi.core.temperature, int)
        self.assertIsInstance(rpi.core.frequency, int)

        with self.assertRaises(NotImplementedError):
            rpi.core.wd_toggle()

        with self.assertRaisesRegex(AttributeError, r"direct assignment is not supported"):
            rpi.core.a5green = True

        rpi.exit()
        del rpi

    def test_connect4_ios(self):
        rpi = self.modio(configrsc="config_connect4.rsc")
        rpi.setdefaultvalues()

        # Test X2 output
        self.assertEqual(rpi.io.RevPiOutput.value, 0)
        rpi.core.x2out.value = True
        self.assertEqual(rpi.io.RevPiOutput.value, 1)

        # Test X2 input
        self.assertEqual(rpi.io.RevPiStatus.value, 0)
        self.assertFalse(rpi.core.x2in.value)

        # Modify process image: Bit 6 of status is the input (int 64 -> hex 40)
        self.fh_procimg.write(b"\x40")

        rpi.readprocimg()
        self.assertEqual(rpi.io.RevPiStatus.value, 64)
        self.assertTrue(rpi.core.x2in.value)
