# -*- coding: utf-8 -*-
#
# python3-RevPiModIO
#
# Webpage: https://revpimodio.org/
# (c) Sven Sager, License: LGPLv3
#
"""Bildet die App Sektion von piCtory ab."""


class App(object):

    """Bildet die App Sektion der config.rsc ab."""

    def __init__(self, app):
        """Instantiiert die App-Klasse.
        @param app piCtory Appinformationen"""
        self.name = app["name"]
        self.version = app["version"]
        self.language = app["language"]
        # TODO: Layout untersuchen und anders abbilden
        self.layout = app["layout"]
