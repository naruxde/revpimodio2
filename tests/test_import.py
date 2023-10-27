# -*- coding: utf-8 -*-
"""Test module import."""
# SPDX-FileCopyrightText: 2023 Sven Sager
# SPDX-License-Identifier: GPL-2.0-or-later

import unittest


class ModuleImport(unittest.TestCase):
    def test_import(self):
        """Test the import of the module."""
        import revpimodio2

        self.assertEqual(type(revpimodio2.__version__), str)
