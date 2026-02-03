# -*- coding: utf-8 -*-
"""Maps the Summary section from piCtory."""
__author__ = "Sven Sager"
__copyright__ = "Copyright (C) 2023 Sven Sager"
__license__ = "LGPLv2"


class Summary:
    """Maps the Summary section of config.rsc."""

    __slots__ = "inptotal", "outtotal"

    def __init__(self, summary: dict):
        """
        Instantiates the RevPiSummary class.

        :param summary: piCtory summary information
        """
        self.inptotal = summary.get("inpTotal", -1)
        self.outtotal = summary.get("outTotal", -1)
