# -*- coding: utf-8 -*-
"""Tests instantiation all local classes."""
__author__ = "Sven Sager"
__copyright__ = "Copyright (C) 2024 Sven Sager"
__license__ = "GPLv2"

import os
from os.path import join, dirname
from signal import SIGINT
from threading import Event

from .. import TestRevPiModIO


class TestModioClassBasics(TestRevPiModIO):

    data_dir = dirname(__file__)

    def test_appclass(self):
        """Test the .app class."""
        rpi = self.modio()
        self.assertEqual(rpi.app.language, "en")
        self.assertEqual(rpi.app.name, "PiCtory")
        self.assertEqual(rpi.app.version, "1.2.3")

        self.assertEqual(rpi.app.savets.tm_year, 2017)
        self.assertEqual(rpi.app.savets.tm_hour, 12)
        del rpi

        # Old config without saveTS
        with self.assertWarnsRegex(Warning, r"equal device name '.*' in pictory configuration."):
            rpi = self.modio(configrsc="config_old.rsc")
        self.assertIsNone(rpi.app.savets)
        del rpi

        rpi = self.modio(configrsc="config_wrong_tstime.rsc")
        self.assertEqual(rpi.app.savets.tm_year, 1970)
        del rpi

    def test_modio_attributes(self):
        """Test class attributs of RevPiModIO."""
        rpi = self.modio()

        self.assertEqual(rpi.configrsc, join(self.data_dir, "config.rsc"))
        self.assertEqual(rpi.cycletime, 20)
        rpi.cycletime = 60
        self.assertEqual(rpi.cycletime, 60)
        with self.assertRaises(ValueError):
            rpi.cycletime = 4
        with self.assertRaises(ValueError):
            rpi.cycletime = 2001

        self.assertEqual(rpi.ioerrors, 0)
        self.assertIs(type(rpi.length), int)
        self.assertEqual(rpi.maxioerrors, 0)
        rpi.maxioerrors = 200
        self.assertEqual(rpi.maxioerrors, 200)
        with self.assertRaises(ValueError):
            rpi.maxioerrors = -5
        self.assertEqual(rpi.monitoring, False)
        self.assertEqual(rpi.procimg, self.fh_procimg.name)
        self.assertEqual(rpi.simulator, False)
        self.assertIsNone(rpi.resetioerrors())

        # Exitevent
        with self.assertRaises(RuntimeError):
            rpi.handlesignalend(False)
        evt_cleanup = Event()

        def test_cleanup_function():
            # Test dummy for cleanup function
            evt_cleanup.set()

        rpi.handlesignalend(test_cleanup_function)
        os.kill(os.getpid(), SIGINT)
        self.assertTrue(evt_cleanup.is_set())

    def test_procimg(self):
        """Test interaction with process image."""
        rpi = self.modio()

        # Procimg IO all
        self.assertIsNone(rpi.setdefaultvalues())
        self.assertEqual(rpi.writeprocimg(), True)
        self.assertEqual(rpi.syncoutputs(), True)
        self.assertEqual(rpi.readprocimg(), True)

        # Procimg IO device
        self.assertIsNone(rpi.device.virt01.setdefaultvalues())
        self.assertEqual(rpi.device.virt01.writeprocimg(), True)
        self.assertEqual(rpi.device.virt01.syncoutputs(), True)
        self.assertEqual(rpi.device.virt01.readprocimg(), True)
