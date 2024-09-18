# -*- coding: utf-8 -*-
"""Tests for replace io file."""
__author__ = "Sven Sager"
__copyright__ = "Copyright (C) 2024 Sven Sager"
__license__ = "GPLv2"

from os.path import join, dirname

from tests import TestRevPiModIO


class TestReplaceIO(TestRevPiModIO):

    data_dir = dirname(__file__)

    def test_replace_io_file(self):
        replace_io_file = join(self.data_dir, "replace_io.conf")
        rpi = self.modio(replace_io_file=replace_io_file)
        self.assertEqual(rpi.replace_io_file, replace_io_file)
        rpi.setdefaultvalues()
        self.assertEqual(rpi.io.test1.value, -1)
        self.assertFalse(rpi.io.r_bit0.value)
        self.assertTrue(rpi.io.r_bit1.value)
        self.assertFalse(rpi.io.r_bit5.value)
        self.assertFalse("Output_19" in rpi.io)

        self.assertEqual(rpi.io.test1.byteorder, "big")
        self.assertEqual(rpi.io.r_bit0.byteorder, "little")

        self.assertEqual(rpi.io.r_bit0.bmk, "EinBit")

        with self.assertRaises(RuntimeError):
            rpi.export_replaced_ios("/gehtnich/replace_io.conf")

        with self.assertRaises(ValueError):
            rpi.io.test1.export = 1
        rpi.io.test1.export = True
        rpi.io.Input_20.replace_io("byte_test", "3s", defaultvalue=b"\xff\x00\x80", export=True)
        rpi.export_replaced_ios("/tmp/replace_io.conf")
        del rpi

        rpi = self.modio(replace_io_file="/tmp/replace_io.conf")
        self.assertTrue(rpi.io.test1.export)
        self.assertTrue(rpi.io.byte_test.export)
        self.assertEqual(rpi.io.byte_test.defaultvalue, b"\xff\x00\x80")

    def test_fb_replace_io_fail(self):
        with self.assertRaises(RuntimeError):
            rpi = self.modio(replace_io_file=join(self.data_dir, "replace_io_fail.conf"))
        with self.assertRaises(RuntimeError):
            rpi = self.modio(replace_io_file="no_file_nonono")
        with self.assertRaises(RuntimeError):
            rpi = self.modio(replace_io_file=join(self.data_dir, "replace_io_failformat.conf"))
        with self.assertRaises(ValueError):
            rpi = self.modio(
                replace_io_file=join(self.data_dir, "replace_io_faildefaultvalue_bool.conf")
            )
        with self.assertRaises(ValueError):
            rpi = self.modio(
                replace_io_file=join(self.data_dir, "replace_io_faildefaultvalue_int.conf")
            )
        with self.assertRaises(ValueError):
            rpi = self.modio(replace_io_file=join(self.data_dir, "replace_io_failbit_int.conf"))
        with self.assertRaisesRegex(ValueError, r"defaultvalue to bytes"):
            rpi = self.modio(replace_io_file=join(self.data_dir, "replace_io_bytes_fail.conf"))
