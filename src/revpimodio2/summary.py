# -*- coding: utf-8 -*-
"""Bildet die Summary-Sektion von piCtory ab."""
__author__ = "Sven Sager"
__copyright__ = "Copyright (C) 2023 Sven Sager"
__license__ = "LGPLv2"


class Summary:
    """Bildet die Summary-Sektion der config.rsc ab."""

    __slots__ = "inptotal", "outtotal"

    def __init__(self, summary: dict):
        """
        Instantiiert die RevPiSummary-Klasse.

        :param summary: piCtory Summaryinformationen
        """
        self.inptotal = summary.get("inpTotal", -1)
        self.outtotal = summary.get("outTotal", -1)
