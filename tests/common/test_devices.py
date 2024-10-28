# -*- coding: utf-8 -*-
"""Tests instantiation all local classes."""
__author__ = "Sven Sager"
__copyright__ = "Copyright (C) 2024 Sven Sager"
__license__ = "GPLv2"

from os.path import dirname

from revpimodio2 import OUT, MEM, INP
from revpimodio2.device import Virtual, Base
from tests import TestRevPiModIO


class TestDevicesModule(TestRevPiModIO):
    data_dir = dirname(__file__)

    def test_device(self):
        """Test device attributes."""
        rpi = self.modio()

        self.assertEqual(rpi.device[64].name, "virt01")
        self.assertEqual(rpi.device.virt01.length, 64)
        self.assertEqual(rpi.device.virt01.name, "virt01")
        self.assertIsInstance(rpi.device.virt01.offset, int)
        self.assertEqual(rpi.device.virt01.position, 64)
        self.assertEqual(rpi.device.virt01.producttype, 32768)

        # Magic
        self.assertEqual("virt01" in rpi.device, True)
        self.assertEqual("nixnix" in rpi.device, False)
        self.assertEqual(64 in rpi.device, True)
        self.assertEqual(128 in rpi.device, False)
        self.assertEqual(rpi.device.virt01 in rpi.device, True)
        self.assertIsInstance(bytes(rpi.device.virt01), bytes)

        # We have 7 devices in config.rsc file
        self.assertEqual(len(rpi.device), 7)

    def test_devs_and_ios(self):
        """Test IO grouping of devices."""
        rpi = self.modio()

        self.assertEqual(len(rpi.device.virt01), 64)

        # getIOs
        self.assertIsInstance(rpi.device.aio01.get_inputs(), list)
        self.assertIsInstance(rpi.device.aio01.get_outputs(), list)
        self.assertIsInstance(rpi.device.aio01.get_memories(), list)
        int_inputs = len(rpi.device.aio01.get_inputs())
        int_output = len(rpi.device.aio01.get_outputs())

        self.assertIsInstance(rpi.device.aio01.get_allios(), list)
        self.assertEqual(len(rpi.device.aio01.get_allios()), int_inputs + int_output)

        # IO Byte vergleichen
        int_byte = 0
        for devio in [rpi.device.aio01.get_allios(), rpi.device.aio01.get_memories()]:
            for io in devio:
                int_byte += io.length
        self.assertEqual(len(rpi.device.aio01), int_byte)

        # Test the types of IOs
        len_end = 0
        len_start = len_end
        for io in rpi.device.aio01.get_inputs():
            self.assertEqual(io.type, INP)
            len_end += io.length
        self.assertEqual(len_start, rpi.device.aio01._slc_inp.start)
        self.assertEqual(len_end, rpi.device.aio01._slc_inp.stop)

        len_start = len_end
        for io in rpi.device.aio01.get_outputs():
            self.assertEqual(io.type, OUT)
            len_end += io.length
        self.assertEqual(len_start, rpi.device.aio01._slc_out.start)
        self.assertEqual(len_end, rpi.device.aio01._slc_out.stop)

        len_start = len_end
        for io in rpi.device.aio01.get_memories():
            self.assertEqual(io.type, MEM)
            len_end += io.length
        self.assertEqual(len_start, rpi.device.aio01._slc_mem.start)
        self.assertEqual(len_end, rpi.device.aio01._slc_mem.stop)

    def test_device_modifications(self):
        """Test device modifications."""
        rpi = self.modio()

        # Zugriffe
        self.assertIsInstance(rpi.device.virt01, Virtual)
        self.assertIsInstance(rpi.device["virt01"], Virtual)

        # IO-Abfragen
        self.assertEqual("pbit0_7" in rpi.device.virt01, True)
        self.assertEqual(rpi.io.pbit0_7 in rpi.device.virt01, True)
        self.assertEqual(33 in rpi.device.virt01, False)
        self.assertEqual(552 in rpi.device.virt01, True)

        # Löschen
        del rpi.device.virt01
        with self.assertRaises(AttributeError):
            rpi.device.virt01
        self.assertEqual(rpi.device[0].name, "picore01")
        del rpi.device[0]
        with self.assertRaises(IndexError):
            rpi.device[0]
        with self.assertRaises(AttributeError):
            rpi.device.picore01

        del rpi.device[rpi.device.di01]

    def test_new_basedevice(self):
        """Test unknown (new) base device."""
        rpi = self.modio(configrsc="config_new_base.rsc")
        self.assertEqual(type(rpi.device[0]), Base)
        del rpi
