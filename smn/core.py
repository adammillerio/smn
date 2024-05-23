#!/usr/bin/env python3
import sys
from importlib.util import module_from_spec
from pathlib import Path

from invoke.exceptions import CollectionNotFound
from invoke.loader import FilesystemLoader

from smn import tome


def load_cli() -> None:
    """Locate and load the root Summoner tome.

    This will locate and load the nearest tome.py file from the current working
    directory to the filesystem root. Once a tome.py file is located, it will
    be executed in order to "program" the Summoner root click CLI group.

    The directory of the located tome.py file is also added to the python path,
    allowing for import of other files during execution.
    """

    # TODO: Add explicit --tome option for path override.
    loader = FilesystemLoader()
    module_spec = loader.find("tome")

    # Make the path that the located tome.py file is present in the first python
    # path, allowing for "local" imports.
    module_path = Path(module_spec.origin).parent
    if sys.path[0] != module_path:
        sys.path.insert(0, str(module_path))

    # Load and execute the located tome.py module.
    module = module_from_spec(module_spec)
    module_spec.loader.exec_module(module)


def cli() -> None:
    try:
        # Load a tome.py file to program the smn click Group.
        load_cli()
    except CollectionNotFound:
        print("unable to locate tome.py file")
        exit(1)

    # Run the programmed click Group.
    tome()


if __name__ == "__main__":
    cli()
