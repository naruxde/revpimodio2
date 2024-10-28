# -*- coding: utf-8 -*-
"""Tests for replace io file."""
__author__ = "Sven Sager"
__copyright__ = "Copyright (C) 2024 Sven Sager"
__license__ = "GPLv2"

from os.path import join, dirname

from revpimodio2.io import IntIOReplaceable
from tests import TestRevPiModIO


class TestReplaceIO(TestRevPiModIO):

    data_dir = dirname(__file__)

    def test_replacing(self):
        """Test replacing IOs."""
        rpi = self.modio()

        # Test type of IOs on an virtual device
        for io in rpi.device.virt01:
            self.assertIsInstance(io, IntIOReplaceable)

        # Try to replace hardware IO
        with self.assertRaises(AttributeError):
            rpi.io.v_druck.replace_io("test2", frm="?")

        rpi.io.pbit0_7.replace_io("test4", frm="?", bit=4)
        rpi.io.pbit0_7.replace_io("test5", frm="?", bit=5, byteorder="big")
        self.assertFalse(rpi.io.test4())
        self.assertFalse(rpi.io.test4.value)
        with self.assertRaises(MemoryError):
            rpi.io.pbit0_7.replace_io("test4_2", frm="?", bit=4)

        with self.assertRaises(ValueError):
            rpi.io.meldung0_7.replace_io("outtest", "?", bit=100)
        with self.assertRaises(ValueError):
            rpi.io.meldung0_7.replace_io("outtest", "?", byteorder="test")

        # Work with default values
        rpi.io.meldung0_7.replace_io("outtest", "?", defaultvalue=True)
        self.assertTrue(rpi.io.outtest.defaultvalue)
        self.assertFalse(rpi.io.outtest.value)
        rpi.io.outtest.value = True
        self.assertTrue(rpi.io.outtest.value)
        rpi.io.outtest.value = False

        # Apply given default values
        rpi.setdefaultvalues()
        self.assertTrue(rpi.io.outtest.value)

        with self.assertRaises(ValueError):
            rpi.io.pbit8_15.replace_io("test2", frm="hf")

        rpi.io.pbit8_15.replace_io("test2", frm="h")
        rpi.io.meldung8_15.replace_io(
            "testmeldung1",
            frm="h",
            byteorder="big",
            event=lambda io_name, io_value: None,
        )
        with self.assertRaises(MemoryError):
            rpi.io.meldung0_7.replace_io("testmeldung2", frm="h", byteorder="big")
        with self.assertRaises(TypeError):
            rpi.io._private_register_new_io_object(None)
        with self.assertRaises(AttributeError):
            rpi.io.testmeldung1.replace_io("testx", frm="?")

        self.assertEqual(rpi.io.testmeldung1.defaultvalue, 0)
        self.assertEqual(rpi.io.testmeldung1.frm, "h")
        self.assertTrue(rpi.io.testmeldung1.signed)
        self.assertEqual(rpi.io.testmeldung1.value, 0)

        # Set value
        rpi.io.testmeldung1.value = 200
        self.assertEqual(rpi.io.testmeldung1(), 200)
        rpi.io.testmeldung1(100)
        self.assertEqual(rpi.io.testmeldung1.value, 100)

        with self.assertRaises(BufferError):
            rpi.io.Output_32.replace_io("test", "h")

        # Byte value with default value
        with self.assertRaises(ValueError):
            rpi.io.Output_9.replace_io("drehzahl", "H", defaultvalue=b"\x00\x00\x00")
        with self.assertRaises(ValueError):
            rpi.io.Output_9.replace_io("drehzahl", "H", defaultvalue=b"\x00")
        rpi.io.Output_9.replace_io("drehzahl", "H", defaultvalue=b"\xff\xff")
        self.assertEqual(rpi.io.drehzahl.frm, "H")
        self.assertFalse(rpi.io.drehzahl.signed)
        self.assertEqual(rpi.io.drehzahl.defaultvalue, 65535)
        self.assertEqual(rpi.io.drehzahl.value, 0)
        rpi.setdefaultvalues()
        self.assertEqual(rpi.io.drehzahl.value, 65535)

        # Bit value with defaultvalue
        rpi.io.Output_11._defaultvalue = b"\x02"
        rpi.io.Output_11.replace_io("bitwert0", "?", bit=0)
        rpi.io.Output_11.replace_io("bitwert1", "?", bit=1)
        self.assertFalse(rpi.io.bitwert0.defaultvalue)
        self.assertTrue(rpi.io.bitwert1.defaultvalue)

        # Multi bytes
        with self.assertRaises(ValueError):
            rpi.io.Output_11.replace_io("mehrbyte", "ss")
        rpi.io.Output_11.replace_io("mehrbyte", "4s")
        self.assertEqual(rpi.io.mehrbyte.length, 4)
        self.assertEqual(rpi.io.mehrbyte.frm, "4s")
        self.assertEqual(rpi.io.mehrbyte.value, b"\x00\x00\x00\x00")
        rpi.io.mehrbyte.value = b"\xff\xff\xff\xff"
        self.assertEqual(rpi.io.mehrbyte.value, b"\xff\xff\xff\xff")

        # String defaultvalue (Encoding erros are filled with \x00)
        rpi.io.Output_15.replace_io("string", "4s", defaultvalue="t\xffst")
        self.assertEqual(rpi.io.string.value, b"\x00\x00\x00\x00")

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

    def test_replace_io_file_fail(self):
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
