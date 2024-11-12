# -*- coding: utf-8 -*-
"""Test errors in config.rsc"""
__author__ = "Sven Sager"
__copyright__ = "Copyright (C) 2024 Sven Sager"
__license__ = "GPLv2"

from os.path import dirname

from .. import TestRevPiModIO


class TestConfigRscBugs(TestRevPiModIO):

    data_dir = dirname(__file__)

    def test_overlapping(self):
        with self.assertWarnsRegex(Warning, r"RelayOutputPadding_[1-4]"):
            self.modio(configrsc="config_overlapping_bits.rsc")

        with self.assertWarnsRegex(Warning, r"RelayCycleWarningThreshold_4"):
            self.modio(configrsc="config_overlapping_bytes.rsc")

    def test_floating_offsets(self):
        with self.assertWarnsRegex(Warning, r"Offset value 31.5"):
            self.modio(configrsc="config_floating_offset.rsc")
