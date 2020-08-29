# -*- coding: utf-8 -*-
"""Bildet die App Sektion von piCtory ab."""
from time import strptime

__author__ = "Sven Sager"
__copyright__ = "Copyright (C) 2020 Sven Sager"
__license__ = "LGPLv3"


class App(object):
    """Bildet die App Sektion der config.rsc ab."""

    __slots__ = "name", "version", "language", "layout", "savets"

    def __init__(self, app: dict):
        """
        Instantiiert die App-Klasse.

        :param app: piCtory Appinformationen
        """
        self.name = app["name"]
        """Name of creating app"""

        self.version = app["version"]
        """Version of creating app"""

        self.language = app["language"]
        """Language of creating app"""

        # Speicherungszeitpunkt laden, wenn vorhanden
        self.savets = app.get("saveTS", None)
        """Timestamp of configuraiton"""

        if self.savets is not None:
            try:
                self.savets = strptime(self.savets, "%Y%m%d%H%M%S")
            except ValueError:
                self.savets = None

        # TODO: Layout untersuchen und anders abbilden
        self.layout = app["layout"]
