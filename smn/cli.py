#!/usr/bin/env python3
import sys
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
from logging import Logger, getLogger
from typing import Tuple, Optional

import click
from invoke.exceptions import CollectionNotFound
from invoke.loader import FilesystemLoader

from smn import tome

logger: Logger = getLogger(__name__)


def load_cli(path: Optional[str] = None) -> None:
    """Locate and load the root Summoner tome.

    This will locate and load the nearest tome.py file from the current working
    directory to the filesystem root. Once a tome.py file is located, it will
    be executed in order to "program" the Summoner root click CLI group.

    The directory of the located tome.py file is also added to the python path,
    allowing for import of other files during execution.

    Raises:
        CollectionNotFound: If no tome.py file could be located in any directory
            between the current working directory and root.
    """

    if not path:
        # Use invoke's loader to find a module tome.py in any directory between
        # the current working directory and root.
        loader = FilesystemLoader()
        module_spec = loader.find("tome")
    else:
        module_spec = spec_from_file_location("tome", path)

    # Make the path that the located root tome file is present in the first python
    # path, allowing for "local" imports.
    module_path = Path(module_spec.origin).parent
    if sys.path[0] != module_path:
        sys.path.insert(0, str(module_path))

    # Load and execute the located root tome module.
    module = module_from_spec(module_spec)
    module_spec.loader.exec_module(module)


@click.command(
    "smn-run",
    context_settings={
        # Unknown arguments could be for user smn commands, so pass them through.
        "ignore_unknown_options": True,
    },
    # Disable help option since we will defer to the actual smn CLI's help page
    # after programming.
    add_help_option=False,
)
@click.option(
    "--tome",
    "_tome",
    type=click.Path(exists=True, file_okay=True, dir_okay=False, readable=True),
    required=False,
    help="directly specify path to root tome",
)
@click.option(
    "--smn-help",
    is_flag=True,
    default=False,
    help="Show this message and exit.",
)
@click.argument("command", nargs=-1, type=click.UNPROCESSED)
def smn(_tome: Optional[str], smn_help: bool, command: Tuple[str, ...]) -> None:
    try:
        # Load a root tome to program the smn click Group.
        load_cli(_tome)
    except CollectionNotFound:
        # If the user passed --smn-help, then just show the unprogrammed help
        # for the smn CLI. In all other cases, print a failure to load and exit
        # with a nonzero code.
        if not smn_help:
            click.secho(
                "unable to locate tome.py file in any directory up to root",
                fg="red",
            )
            click.secho(
                "try specifying one with --tome or run smn --smn-help for more info",
                fg="yellow",
            )

            raise click.exceptions.Exit(1)
    except Exception:
        logger.exception(f"encountered exception while loading {_tome}")
        click.secho(f"failed to load root tome at {_tome}", fg="red")
        raise click.exceptions.Exit(1)

    # Run the programmed click Group.
    tome()


# Since an invalid --tome can still be provided prior to load, replace the loader's
# usage formatter with the root tome's for consistency.
smn.format_usage = tome.format_usage


if __name__ == "__main__":
    smn()
