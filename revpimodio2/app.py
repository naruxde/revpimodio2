# -*- coding: utf-8 -*-
"""Bildet die App Sektion von piCtory ab."""
__author__ = "Sven Sager"
__copyright__ = "Copyright (C) 2018 Sven Sager"
__license__ = "LGPLv3"

from time import strptime


class App(object):

    """Bildet die App Sektion der config.rsc ab."""

    __slots__ = "name", "version", "language", "layout", "savets"

    def __init__(self, app):
        """Instantiiert die App-Klasse.
        @param app piCtory Appinformationen"""
        self.name = app["name"]
        self.version = app["version"]
        self.language = app["language"]

        # Speicherungszeitpunkt laden, wenn vorhanden
        self.savets = app.get("saveTS", None)
        if self.savets is not None:
            try:
                self.savets = strptime(self.savets, "%Y%m%d%H%M%S")
            except ValueError:
                self.savets = None

        # TODO: Layout untersuchen und anders abbilden
        self.layout = app["layout"]
