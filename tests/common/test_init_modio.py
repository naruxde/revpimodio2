# -*- coding: utf-8 -*-
"""Tests instantiation all local classes."""
__author__ = "Sven Sager"
__copyright__ = "Copyright (C) 2024 Sven Sager"
__license__ = "GPLv2"

from os import remove, makedirs
from os.path import join, dirname
from shutil import copyfile
from warnings import warn

import revpimodio2
from .. import TestRevPiModIO


class TestInitModio(TestRevPiModIO):

    data_dir = dirname(__file__)

    def test_init_classes(self):
        """Tests instantiation."""
        with self.assertRaises(RuntimeError):
            revpimodio2.RevPiModIO(
                procimg=self.fh_procimg.name,
                configrsc="/opt/KUNBUS/config_lock.rsc",
            )

        # Prepare default args for direct ModIO classes
        defaultkwargs = {
            "procimg": self.fh_procimg.name,
            "configrsc": join(self.data_dir, "config.rsc"),
        }

        # Check default path of config.rsc
        for config_file in ("/opt/KUNBUS/config.rsc", "/etc/revpi/config.rsc"):
            config_dir = dirname(config_file)
            try:
                makedirs(config_dir, exist_ok=True)
                copyfile(defaultkwargs["configrsc"], config_file)
            except PermissionError:
                warn(f"Skip test for default location of '{config_file}' - permission denied")
            else:
                revpimodio2.RevPiModIO(procimg=self.fh_procimg.name)
                remove(config_file)

        # RevPiModIO
        rpi = self.modio()
        del rpi
        rpi = self.modio(autorefresh=True)
        rpi.cleanup()
        del rpi
        rpi = self.modio(monitoring=True)
        del rpi
        rpi = self.modio(syncoutputs=False)
        del rpi
        rpi = self.modio(simulator=True)
        del rpi

        # Init with old config.rsc and same device names
        with self.assertWarnsRegex(Warning, r"equal device name '.*' in pictory configuration."):
            rpi = self.modio(configrsc="config_old.rsc")
        self.assertEqual(rpi.device.virt01.position, 64)
        self.assertEqual(rpi.device["virt01"].position, 64)
        self.assertEqual(len(rpi.device), 6)
        del rpi

        # Init with unknown DeviceType
        with self.assertWarnsRegex(Warning, r"device type 'XXX' on position 64 unknown"):
            rpi = self.modio(configrsc="config_unknown.rsc")
        self.assertEqual(len(rpi.device), 5)
        del rpi

        # Init with empty config
        with self.assertRaises(RuntimeError):
            self.modio(configrsc="config_empty.rsc")

        # Init with RevPi 1.1
        rpi = self.modio(configrsc="config_rpi11.rsc")
        self.assertEqual(len(rpi.device), 4)
        del rpi

        # Init with 'null' JSON
        rpi = self.modio(configrsc="config_null.rsc")
        # notaus_ok null
        # motorschutz_ok "null"
        self.assertFalse(rpi.io.notaus_ok._defaultvalue)
        self.assertFalse(rpi.io.motorschutz_ok._defaultvalue)
        # self.assertEqual(len(rpi.device), 4)
        del rpi

        # RevPiModIOSelected
        rpi = revpimodio2.RevPiModIOSelected([32, 33], **defaultkwargs)
        self.assertEqual(2, len(rpi.device))
        del rpi
        with self.assertRaises(revpimodio2.errors.DeviceNotFoundError):
            # Liste mit einem ungültigen Device als <class 'list'>
            rpi = revpimodio2.RevPiModIOSelected([32, 10], **defaultkwargs)
        with self.assertRaises(revpimodio2.errors.DeviceNotFoundError):
            # Ungültiges Device als <class 'int'>
            rpi = revpimodio2.RevPiModIOSelected(100, **defaultkwargs)
        with self.assertRaises(ValueError):
            # Ungültiger Devicetype
            rpi = revpimodio2.RevPiModIOSelected([True], **defaultkwargs)

        ds = revpimodio2.modio.DevSelect(
            "", "productType", (str(revpimodio2.pictory.ProductType.DI),)
        )
        rpi = revpimodio2.RevPiModIOSelected(ds, **defaultkwargs)
        self.assertEqual(len(rpi.device), 2)
        del rpi

        ds = revpimodio2.modio.DevSelect("", "bmk", ("RevPi DO",))
        rpi = revpimodio2.RevPiModIOSelected(ds, **defaultkwargs)
        self.assertEqual(len(rpi.device), 2)
        del rpi

        # RevPiModIODriver
        with self.assertRaises(revpimodio2.errors.DeviceNotFoundError):
            # Liste mit einem ungültigen Device als <class 'list'>
            rpi = revpimodio2.RevPiModIODriver([64, 100], **defaultkwargs)
        with self.assertRaises(revpimodio2.errors.DeviceNotFoundError):
            # Ungültiges Device als <class 'int'>
            rpi = revpimodio2.RevPiModIODriver([100], **defaultkwargs)
        with self.assertRaises(ValueError):
            # Ungültiger Devicetype
            rpi = revpimodio2.RevPiModIODriver([True], **defaultkwargs)

        rpi = revpimodio2.RevPiModIODriver(64, **defaultkwargs)
        self.assertEqual(1, len(rpi.device))
        del rpi
        rpi = revpimodio2.RevPiModIODriver("virt01", **defaultkwargs)
        self.assertEqual(1, len(rpi.device))
        del rpi

        # Core ios als bits
        rpi = self.modio(configrsc="config_core_bits.json")
        del rpi

        # Bad offset
        with self.assertWarnsRegex(
            Warning,
            r"(Device offset ERROR in piCtory configuration!|"
            r"is not in the device offset and will be ignored)",
        ):
            rpi = self.modio(configrsc="config_bad_offset.rsc")
        del rpi
