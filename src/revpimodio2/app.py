# -*- coding: utf-8 -*-
"""Bildet die App Sektion von piCtory ab."""
__author__ = "Sven Sager"
__copyright__ = "Copyright (C) 2023 Sven Sager"
__license__ = "LGPLv2"

from time import gmtime, strptime


class App:
    """Bildet die App Sektion der config.rsc ab."""

    __slots__ = "name", "version", "language", "layout", "savets"

    def __init__(self, app: dict):
        """
        Instantiiert die App-Klasse.

        :param app: piCtory Appinformationen
        """
        self.name = app.get("name", "")
        """Name of creating app"""

        self.version = app.get("version", "")
        """Version of creating app"""

        self.language = app.get("language", "")
        """Language of creating app"""

        self.savets = app.get("saveTS", None)
        """Timestamp of configuraiton"""

        if self.savets is not None:
            try:
                self.savets = strptime(self.savets, "%Y%m%d%H%M%S")
            except Exception:
                self.savets = gmtime(0)

        # TODO: Layout untersuchen und anders abbilden
        self.layout = app.get("layout", {})
