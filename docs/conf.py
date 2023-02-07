# coding=utf-8
# Configuration file for the Sphinx documentation builder.
#
# For the full list of built-in configuration values, see the documentation:

import os
import sys

sys.path.insert(0, os.path.abspath('../src'))
from revpimodio2 import __version__

# -- Project information -----------------------------------------------------

project = 'revpimodio2'
copyright = '2023, Sven Sager'
author = 'Sven Sager'
version = __version__

# -- General configuration ---------------------------------------------------

extensions = [
    'sphinx.ext.autodoc',
    'sphinx.ext.todo',
    'sphinx.ext.viewcode'
]

templates_path = ['_templates']
exclude_patterns = ['_build', 'Thumbs.db', '.DS_Store']

# -- Options for HTML output -------------------------------------------------

html_theme = 'alabaster'
html_static_path = ['_static']
