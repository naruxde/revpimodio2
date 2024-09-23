# -*- coding: utf-8 -*-
"""Shared functions for tests."""
__author__ = "Sven Sager"
__copyright__ = "Copyright (C) 2024 Sven Sager"
__license__ = "GPLv2"

from os.path import dirname, join
from tempfile import NamedTemporaryFile
from unittest import TestCase

import revpimodio2

DEFAULT_PROCIMG = join(dirname(__file__), "proc.img")
RUN_ON_REVPI = False  # todo: Check revpi system


class TestRevPiModIO(TestCase):

    data_dir = dirname(__file__)

    def setUp(self):
        self.fh_procimg = NamedTemporaryFile("wb+", 0, prefix="test_procimg_")
        self.fh_procimg.write(b"\x00" * 4096)
        self.fh_procimg.seek(0)

    def tearDown(self):
        self.fh_procimg.close()

    def modio(self, **kwargs):
        """Default ModIO object with temp process image."""
        if not RUN_ON_REVPI:
            if "procimg" in kwargs:
                # Use a copy of given prepared process image
                with open(kwargs["procimg"], "rb") as fh:
                    self.fh_procimg.write(fh.read())
                    self.fh_procimg.seek(0)

            # Always use the temporary process image of testing class
            kwargs["procimg"] = self.fh_procimg.name

            # Always use a config inside the testing folder (default config.rsc)
            kwargs["configrsc"] = join(self.data_dir, kwargs.get("configrsc", "config.rsc"))

        return revpimodio2.RevPiModIO(**kwargs)
