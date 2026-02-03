# -*- coding: utf-8 -*-
"""Maps the App section from piCtory."""
__author__ = "Sven Sager"
__copyright__ = "Copyright (C) 2023 Sven Sager"
__license__ = "LGPLv2"

from time import gmtime, strptime


class App:
    """Maps the App section of config.rsc."""

    __slots__ = "name", "version", "language", "layout", "savets"

    def __init__(self, app: dict):
        """
        Instantiates the App class.

        :param app: piCtory app information
        """
        self.name = app.get("name", "")
        """Name of creating app"""

        self.version = app.get("version", "")
        """Version of creating app"""

        self.language = app.get("language", "")
        """Language of creating app"""

        self.savets = app.get("saveTS", None)
        """Timestamp of configuration"""

        if self.savets is not None:
            try:
                self.savets = strptime(self.savets, "%Y%m%d%H%M%S")
            except Exception:
                self.savets = gmtime(0)

        # TODO: Examine layout and map differently
        self.layout = app.get("layout", {})
