# -*- coding: utf-8 -*-
#
# python3-RevPiModIO
#
# Webpage: https://revpimodio.org/
# (c) Sven Sager, License: LGPLv3
#
"""Bildet die Summary-Sektion von piCtory ab."""


class Summary(object):

    """Bildet die Summary-Sektion der config.rsc ab."""

    def __init__(self, summary):
        """Instantiiert die RevPiSummary-Klasse.
        @param summary piCtory Summaryinformationen"""
        self.inptotal = summary["inpTotal"]
        self.outtotal = summary["outTotal"]
