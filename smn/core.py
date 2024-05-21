#!/usr/bin/env python3
from sys import argv

from smn import tome


def cli() -> None:
    # Run the root tome command, which now has all tomes registered to it.
    tome()
