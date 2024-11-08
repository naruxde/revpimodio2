# -*- coding: utf-8 -*-
"""Tests instantiation all local classes."""
__author__ = "Sven Sager"
__copyright__ = "Copyright (C) 2024 Sven Sager"
__license__ = "GPLv2"

from os.path import dirname

from revpimodio2.io import IntIOCounter
from .. import TestRevPiModIO


class TestIos(TestRevPiModIO):
    data_dir = dirname(__file__)

    def test_ios(self):
        """Test values of IOs."""
        rpi = self.modio()

        # Change values
        rpi.io.magazin1.value = 255
        self.assertEqual(rpi.io.magazin1.value, 255)
        rpi.device.virt01.setdefaultvalues()
        self.assertEqual(rpi.io.magazin1.value, 0)

        # Use __call__ function
        with self.assertRaises(TypeError):
            rpi.io.magazin1.set_value(44)
        with self.assertRaises(ValueError):
            rpi.io.magazin1.set_value(b"\x01\x01")
        rpi.io.magazin1.set_value(b"\x01")
        self.assertEqual(rpi.io.magazin1.value, 1)

        # Inputs and Mems
        with self.assertRaises(RuntimeError):
            rpi.io.magazin1_max.set_value(b"\x01")
        with self.assertRaises(RuntimeError):
            rpi.io.InputMode_1.set_value(b"\x01")

        rpi.io.magazin1_max._iotype = 303
        with self.assertRaises(RuntimeError):
            rpi.io.magazin1_max.set_value(b"\x01")

    def test_counter_io(self):
        """Test counter inputs."""
        rpi = self.modio()

        # Just for testing buffered mode
        rpi._buffedwrite = True

        # Counter vorbereiten
        self.fh_procimg.seek(rpi.io.Counter_1.address)
        self.fh_procimg.write(b"\x00\x01")
        rpi.readprocimg()

        self.assertEqual(type(rpi.io.Counter_1), IntIOCounter)
        self.assertEqual(rpi.io.Counter_1.value, 256)
        rpi.io.Counter_1.reset()
        rpi.readprocimg()
        self.assertEqual(rpi.io.Counter_1.value, 0)

        # This will use ioctl calls
        rpi._run_on_pi = True

        with self.assertWarnsRegex(RuntimeWarning, r"'iorst' and count \d"):
            rpi.io.Counter_1.reset()
        self.assertEqual(rpi.ioerrors, 1)

        del rpi

        rpi = self.modio(monitoring=True)
        self.assertEqual(type(rpi.io.Counter_2), IntIOCounter)
        with self.assertRaises(RuntimeError):
            rpi.io.Counter_2.reset()
        del rpi

        rpi = self.modio(simulator=True)
        self.assertEqual(type(rpi.io.Counter_3), IntIOCounter)
        with self.assertRaises(RuntimeError):
            rpi.io.Counter_3.reset()
        del rpi

    def test_superio(self):
        """Testet mehrbittige IOs."""
        rpi = self.modio(configrsc="config_supervirt.rsc")

        # Adressen und Längen prüfen
        self.assertEqual(rpi.device[65]._offset, 75)

        self.assertEqual(rpi.io.InBit_1.length, 1)
        self.assertEqual(rpi.io.InBit_2.length, 0)
        self.assertEqual(rpi.io.InBit_6.address, 75)
        self.assertEqual(rpi.io.InBit_48.address, 80)
        self.assertEqual(rpi.io.InDword_1.address, 99)
        self.assertEqual(rpi.io.OutBit_1.length, 1)
        self.assertEqual(rpi.io.OutBit_2.length, 0)
        self.assertEqual(rpi.io.OutBit_8.address, 107)
        self.assertEqual(rpi.io.OutBit_9.address, 108)

        self.assertEqual(len(rpi.device[65]._ba_devdata), 64)

        # Inputs setzen
        rpi.io.OutBit_6.value = True
        self.assertTrue(rpi.io.OutBit_6.value)
        self.assertEqual(rpi.device[65]._ba_devdata[32:38], b"\x20\x00\x00\x00\x00\x00")
        rpi.io.OutBit_48.value = True
        self.assertEqual(rpi.device[65]._ba_devdata[32:38], b"\x20\x00\x00\x00\x00\x80")
