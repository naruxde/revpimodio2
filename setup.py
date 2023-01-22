#! /usr/bin/env python3
# -*- coding: utf-8 -*-
"""Setup-script for revpimodio2."""
__author__ = "Sven Sager"
__copyright__ = "Copyright (C) 2023 Sven Sager"
__license__ = "LGPLv3"

from setuptools import setup, find_namespace_packages

with open("README.md") as fh:
    # Load long description from readme file
    long_description = fh.read()

setup(
    name="revpimodio2",
    version="2.6.0rc3",

    packages=find_namespace_packages("src"),
    package_dir={'': 'src'},
    include_package_data=True,

    python_requires="~=3.2",
    install_requires=[],
    entry_points={},

    platforms=["all"],

    url="https://revpimodio.org/",
    license="LGPLv3",
    author="Sven Sager",
    author_email="akira@narux.de",
    maintainer="Sven Sager",
    maintainer_email="akira@revpimodio.org",
    description="Python3 programming for RevolutionPi of KUNBUS GmbH",
    long_description=long_description,
    long_description_content_type="text/markdown",
    keywords=["revpi", "revolution pi", "revpimodio", "plc", "automation"],
    classifiers=[
        "Development Status :: 5 - Production/Stable",
        "Environment :: Console",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: "
        "GNU Lesser General Public License v3 (LGPLv3)",
        "Operating System :: MacOS :: MacOS X",
        "Operating System :: Microsoft :: Windows",
        "Operating System :: POSIX",
        "Programming Language :: Python :: 3",
        "Topic :: Software Development :: Libraries :: Python Modules"
    ],
)
