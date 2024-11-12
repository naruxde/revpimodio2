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

    def test_lib_constants(self):
        """Tests constants of _internal module."""
        import revpimodio2

        self.assertEqual(revpimodio2._internal.consttostr(999), "")

        lst_const = [0, 1, 2, 3, 4, 5, 6, 7, 31, 32, 33, 300, 301, 302, 4096]
        internal_dict = revpimodio2._internal.__dict__  # type: dict
        for key in internal_dict:
            if type(internal_dict[key]) is int:
                const_value = internal_dict[key]
                self.assertEqual(revpimodio2._internal.consttostr(const_value), key)
                self.assertTrue(const_value in lst_const)

        # Test argument checker
        revpimodio2._internal.acheck(bool, arg01=True, arg02_noneok=None)
        revpimodio2._internal.acheck(int, arg01=0, arg02_noneok=10)
        revpimodio2._internal.acheck(str, arg01="", arg02_noneok="ja")

        with self.assertRaises(TypeError):
            revpimodio2._internal.acheck(str, arg01=None, arg02_noneok="test")
        with self.assertRaises(TypeError):
            revpimodio2._internal.acheck(bool, arg01=True, arg02=None)
