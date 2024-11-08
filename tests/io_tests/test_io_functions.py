# -*- coding: utf-8 -*-
"""Tests instantiation all local classes."""
__author__ = "Sven Sager"
__copyright__ = "Copyright (C) 2024 Sven Sager"
__license__ = "GPLv2"

from os.path import dirname

from revpimodio2 import OUT
from .. import TestRevPiModIO


class TestIoFunctions(TestRevPiModIO):
    data_dir = dirname(__file__)

    def test_io_base(self):
        """Test io attributes."""
        rpi = self.modio()

        # Transformations
        self.assertEqual(rpi.io.v_druck.address, 307)
        with self.assertRaises(AttributeError):
            rpi.io.v_druck.address = 10
        self.assertEqual(rpi.io.v_druck.byteorder, "little")
        with self.assertRaises(AttributeError):
            rpi.io.v_druck.byteorder = "big"
        self.assertIsInstance(rpi.io.v_druck.defaultvalue, bool)
        self.assertEqual(rpi.io.v_druck.defaultvalue, 0)
        with self.assertRaises(AttributeError):
            rpi.io.v_druck.defaultvalue = 255
        self.assertEqual(rpi.io.v_druck.length, 0)
        with self.assertRaises(AttributeError):
            rpi.io.v_druck.length = 2
        self.assertEqual(rpi.io.v_druck.name, "v_druck")
        with self.assertRaises(AttributeError):
            rpi.io.v_druck.name = "test"
        self.assertEqual(rpi.io.v_druck.type, OUT)
        with self.assertRaises(AttributeError):
            rpi.io.v_druck.type = 399
        self.assertFalse(rpi.io.v_druck.value)

        self.assertFalse(rpi.io.v_druck._read_only_io)
        self.assertTrue(rpi.io.t_stop._read_only_io)

        rpi.io.v_druck(True)
        self.assertTrue(rpi.io.v_druck.value)
        rpi.io.v_druck.value = False
        self.assertFalse(rpi.io.v_druck())

        # Magic-function __call__
        self.assertEqual(rpi.io.pbit0_7(), 0)
        self.assertFalse(bool(rpi.io.v_druck))
        self.assertFalse(bool(rpi.io.magazin1))
        rpi.io.magazin1(129)
        self.assertEqual(int(rpi.io.magazin1), 129)
        self.assertEqual(rpi.io.magazin1(), 129)
        rpi.io.magazin1.value = 128
        self.assertTrue(bool(rpi.io.magazin1))
        self.assertEqual(int(rpi.io.magazin1), 128)
        self.assertEqual(rpi.io.magazin1(), 128)
        with self.assertRaises(TypeError):
            rpi.io.magazin1(b"\x00")

        rpi.io.meldung0_7.replace_io("test4", frm="?", bit=4)
        rpi.io.test4(True)
        rpi.io.test4(False)

        with self.assertRaises(ValueError):
            rpi.io.magazin1.byteorder = 0
        rpi.io.magazin1.byteorder = "big"
        self.assertIsInstance(rpi.io.magazin1.defaultvalue, int)

        # Signed and unsigned change
        self.assertEqual(rpi.io.magazin1.value, 128)
        self.assertEqual(rpi.io.magazin1.signed, False)
        with self.assertRaises(TypeError):
            rpi.io.magazin1.signed = 0
        rpi.io.magazin1.signed = True
        self.assertEqual(rpi.io.magazin1.signed, True)
        self.assertEqual(rpi.io.magazin1.value, -128)

        with self.assertRaises(TypeError):
            rpi.io.magazin1.value = "test"

        # Cound IOs
        int_len = len(rpi.io)
        int_iter = 0
        for myio in rpi.io:
            int_iter += 1
        self.assertEqual(int_len, int_iter)

        self.assertEqual(rpi.io["v_druck"].name, "v_druck")
        with self.assertRaises(IndexError):
            rpi.io[8192]
        with self.assertRaises(AttributeError):
            # Prevent input assignment
            rpi.io.v_druck = True
