#!/usr/bin/env python3
from smn import tome
from click import Group


def create_cli() -> Group:
    return tome.create_cli()
