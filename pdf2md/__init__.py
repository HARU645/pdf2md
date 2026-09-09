# -*- coding: utf-8 -*-
"""pdf2md - convert PDFs into Markdown meant to be read by an AI."""
from .convert import convert_file, convert_folder, Result

__all__ = ["convert_file", "convert_folder", "Result"]
__version__ = "0.1.0"
