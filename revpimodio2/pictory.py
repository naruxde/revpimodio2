# -*- coding: utf-8 -*-
"""Pictory aliases for IO values."""

__author__ = "Théo Rozier"
__copyright__ = "Copyright (C) 2020 Sven Sager"
__license__ = "LGPLv3"


# RAP files are located under "/var/www/pictory/resources/data/rap/".
# Checked *.rap files already check and do not define any alias :
# - RevPiCore_20160818_1_0.rap
# - RevPiCore_20170210_1_1.rap
# - RevPiCore_20170404_1_2.rap
# - RevPiConCan_20180425_1_0.rap
# - RevPiGateCANopen_20161102_1_0.rap


class AIO:
    """Memory value mappings for RevPi AIO 1.0 (RevPiAIO_20170301_1_0.rap)."""
    OUT_RANGE_OFF = 0  # Off
    OUT_RANGE_0_5V = 1  # 0 - 5V
    OUT_RANGE_0_10V = 2  # 0 - 10V
    OUT_RANGE_N5_5V = 3  # -5 - 5V
    OUT_RANGE_N10_10V = 4  # -10 - 10V
    OUT_RANGE_0_5P5V = 5  # 0 - 5.5V
    OUT_RANGE_0_11V = 6  # 0 - 11V
    OUT_RANGE_N5P5_5P5V = 7  # -5.5 - 5.5V
    OUT_RANGE_N11_11V = 8  # -11 - 11V
    OUT_RANGE_4_20MA = 9  # 4 - 20mA
    OUT_RANGE_0_20MA = 10  # 0 - 20mA
    OUT_RANGE_0_24MA = 11  # 0 - 24mA

    # Slew rate deceleration
    OUT_SLEW_OFF = 0
    OUT_SLEW_ON = 1

    # Slew rate step size
    OUT_SLEW_STEP_SIZE_1LSB = 0
    OUT_SLEW_STEP_SIZE_2LSB = 1
    OUT_SLEW_STEP_SIZE_4LSB = 2
    OUT_SLEW_STEP_SIZE_8LSB = 3
    OUT_SLEW_STEP_SIZE_16LSB = 4
    OUT_SLEW_STEP_SIZE_32LSB = 5
    OUT_SLEW_STEP_SIZE_64LSB = 6
    OUT_SLEW_STEP_SIZE_128LSB = 7

    # Clock rate of slew rate deceleration in kHz
    OUT_SLEW_CLOCK_258_KZH = 0
    OUT_SLEW_CLOCK_200_KZH = 1
    OUT_SLEW_CLOCK_154_KZH = 2
    OUT_SLEW_CLOCK_131_KZH = 3
    OUT_SLEW_CLOCK_116_KZH = 4
    OUT_SLEW_CLOCK_70_KZH = 5
    OUT_SLEW_CLOCK_38_KZH = 6
    OUT_SLEW_CLOCK_26_KZH = 7
    OUT_SLEW_CLOCK_20_KZH = 8
    OUT_SLEW_CLOCK_16_KZH = 9
    OUT_SLEW_CLOCK_10_KZH = 10
    OUT_SLEW_CLOCK_8P3_KZH = 11
    OUT_SLEW_CLOCK_6P9_KZH = 12
    OUT_SLEW_CLOCK_5P5_KZH = 13
    OUT_SLEW_CLOCK_4P2_KZH = 14
    OUT_SLEW_CLOCK_3P3_KZH = 15

    IN_RANGE_N10V_10V = 1  # -10 - 10V
    IN_RANGE_0_10V = 2  # 0 - 10V
    IN_RANGE_0_5V = 3  # 0 - 5V
    IN_RANGE_N5_5V = 4  # -5 - 5V
    IN_RANGE_0_20MA = 5  # 0 - 20mA
    IN_RANGE_0_24MA = 6  # 0 - 24mA
    IN_RANGE_4_20MA = 7  # 4 - 20mA
    IN_RANGE_N25_25MA = 8  # -25 - 25mA

    ADC_DATARATE_5HZ = 0  # 5 Hz
    ADC_DATARATE_10HZ = 1  # 10 Hz
    ADC_DATARATE_20HZ = 2  # 20 Hz
    ADC_DATARATE_40HZ = 3  # 40 Hz
    ADC_DATARATE_80HZ = 4  # 80 Hz
    ADC_DATARATE_160HZ = 5  # 160 Hz
    ADC_DATARATE_320HZ = 6  # 320 Hz
    ADC_DATARATE_640HZ = 7  # 640 Hz

    RTD_TYPE_PT100 = 0  # PT100
    RTD_TYPE_PT1000 = 1  # PT1000

    RTD_2_WIRE = 2  # 2-wire
    RTD_3_WIRE = 0  # 3-wire
    RTD_4_WIRE = 1  # 4-wire


class DI:
    """Memory value mappings for RevPi DI 1.0  (RevPiDI_20160818_1_0.rap)."""
    IN_MODE_DIRECT = 0  # Direct
    IN_MODE_COUNT_RISING = 1  # Counter, rising edge
    IN_MODE_COUNT_FALLING = 2  # Counter, falling edge
    IN_MODE_ENCODER = 3  # Encoder

    IN_DEBOUNCE_OFF = 0  # Off
    IN_DEBOUNCE_25US = 1  # 25us
    IN_DEBOUNCE_750US = 2  # 750us
    IN_DEBOUNCE_3MS = 3  # 3ms


class DO:
    """Memory value mappings for RevPi DO 1.0  (RevPiDO_20160818_1_0.rap)."""
    OUT_PWM_FREQ_40HZ = 1  # 40Hz 1%
    OUT_PWM_FREQ_80HZ = 2  # 80Hz 2%
    OUT_PWM_FREQ_160HZ = 4  # 160Hz 4%
    OUT_PWM_FREQ_200HZ = 5  # 200Hz 5%
    OUT_PWM_FREQ_400HZ = 10  # 400Hz 10%


class DIO(DI, DO):
    """Memory value mappings for RevPi DIO 1.0 (RevPiDIO_20160818_1_0.rap)."""
    pass


class COMPACT:
    """Memory value mappings for RevPi Compact 1.0 (RevPiCompact_20171023_1_0.rap)."""
    DIN_DEBOUNCE_OFF = 0  # Off
    DIN_DEBOUNCE_25US = 1  # 25us
    DIN_DEBOUNCE_750US = 2  # 750us
    DIN_DEBOUNCE_3MS = 3  # 3ms

    AIN_MODE_OFF = 0  # Off
    AIN_MODE_0_10V = 1  # 0 - 10V
    AIN_MODE_PT100 = 3  # PT100
    AIN_MODE_PT1000 = 7  # PT1000


class FLAT:
    """Memory value mappings for RevPi Flat 1.0 (RevPiFlat_20200921_1_0.rap)."""
    IN_RANGE_0_10V = 0
    IN_RANGE_4_20MA = 1
