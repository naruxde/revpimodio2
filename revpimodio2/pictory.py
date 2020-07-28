# -*- coding: utf-8 -*-
"""Pictory aliases for IO values."""

__author__ = "Théo Rozier"
__copyright__ = "Copyright (C) 2018 Sven Sager"
__license__ = "LGPLv3"


class AIO10:

    OUT_RANGE_OFF       = 0     # Off
    OUT_RANGE_0_5V      = 1     # 0 - 5V
    OUT_RANGE_0_10V     = 2     # 0 - 10V
    OUT_RANGE_N5_5V     = 3     # -5 - 5V
    OUT_RANGE_N10_10V   = 4     # -10 - 10V
    OUT_RANGE_0_5P5V    = 5     # 0 - 5.5V
    OUT_RANGE_0_11V     = 6     # 0 - 11V
    OUT_RANGE_N5P5_5P5V = 7     # -5.5 - 5.5V
    OUT_RANGE_N11_11V   = 8     # -11 - 11V
    OUT_RANGE_4_20MA    = 9     # 4 - 20mA
    OUT_RANGE_0_20MA    = 10    # 0 - 20mA
    OUT_RANGE_0_24MA    = 11    # 0 - 24mA

    IN_RANGE_N10V_10V   = 1     # -10 - 10V
    IN_RANGE_0_10V      = 2     # 0 - 10V
    IN_RANGE_0_5V       = 3     # 0 - 5V
    IN_RANGE_N5_5V      = 4     # -5 - 5V
    IN_RANGE_0_20MA     = 5     # 0 - 20mA
    IN_RANGE_0_24MA     = 6     # 0 - 24mA
    IN_RANGE_4_20MA     = 7     # 4 - 20mA
    IN_RANGE_N25_25MA   = 8     # -25 - 25mA


class DIO10:

    IN_MODE_DIRECT          = 0 # Direct
    IN_MODE_COUNT_RISING    = 1 # Counter, rising edge
    IN_MODE_COUNT_FALLING   = 2 # Counter, falling edge
    IN_MODE_ENCODER         = 3 # Encoder

    IN_DEBOUNCE_OFF         = 0 # Off
    IN_DEBOUNCE_25US        = 1 # 25us
    IN_DEBOUNCE_750US       = 2 # 750us
    IN_DEBOUNCE_3MS         = 3 # 3ms