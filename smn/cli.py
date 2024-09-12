#!/usr/bin/env python3
import sys
from importlib.machinery import ModuleSpec
from importlib.util import find_spec, module_from_spec, spec_from_file_location
from os.path import splitext
from pathlib import Path
from logging import Logger, getLogger
from typing import Tuple, Optional

import click
from invoke.exceptions import CollectionNotFound
from invoke.loader import FilesystemLoader
from pyre_extensions import none_throws

from smn import tome

logger: Logger = getLogger(__name__)


def load_cli(path: Optional[str] = None) -> None:
    """Locate and load the root Summoner tome.

    This will locate and load the nearest tome.py file from the current working
    directory to the filesystem root. Once a tome.py file is located, it will
    be executed in order to "program" the Summoner root click CLI group.

    The directory of the located tome.py file is also added to the python path,
    allowing for import of other files during execution.

    If a path is provided, the loader will instead attempt to load the provided
    module or file directly.

    Args:
        path: Optional[str]. Either a python module path or a file path to a root
            tome.

    Raises:
        CollectionNotFound: If no tome.py file could be located in any directory
            between the current working directory and root.
        ValueError: If a root tome module or file exists, but yields no valid
            module spec.
    """

    if not path:
        # Use invoke's loader to find a module tome.py in any directory between
        # the current working directory and root.
        loader = FilesystemLoader()
        module_spec = loader.find("tome")
    elif splitext(path)[1] == ".py":
        # Path is (probably) a file, attempt to load a spec at this path.
        module_spec = spec_from_file_location("tome", path)
    else:
        # Path is a module path, attempt to find a spec in the class path.
        module_spec = find_spec(path)

    if not isinstance(module_spec, ModuleSpec):
        # File/module exists, but yielded no spec on load.
        raise ValueError(f"could not locate root tome module at {path}")

    # Make the path that the located root tome file is present in the first python
    # path, allowing for "local" imports.
    module_path = Path(none_throws(module_spec.origin)).parent
    if sys.path[0] != module_path:
        sys.path.insert(0, str(module_path))

    # Load and execute the located root tome module.
    module = module_from_spec(module_spec)
    none_throws(module_spec.loader).exec_module(module)


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
    type=str,
    required=False,
    help="directly specify either a file or import path to root tome",
    envvar="SMN_TOME",
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

            raise click.exceptions.Exit(2)
    except ModuleNotFoundError:
        click.secho(f"could not import a root tome at {_tome}", fg="red")
        raise click.exceptions.Exit(3)
    except FileNotFoundError:
        click.secho(f"could not find a root tome file at {_tome}", fg="red")
        raise click.exceptions.Exit(4)
    except ValueError:
        click.secho(f"no valid python module for root tome at {_tome}", fg="red")
        raise click.exceptions.Exit(5)
    except Exception:
        logger.exception(f"encountered exception while loading {_tome}")
        click.secho(f"failed to load root tome at {_tome}", fg="red")
        raise click.exceptions.Exit(1)

    # Run the programmed click Group.
    tome()


# Since an invalid --tome can still be provided prior to load, replace the loader's
# usage formatter with the root tome's for consistency.
# pyre-ignore[8]
smn.format_usage = tome.format_usage


if __name__ == "__main__":
    smn()
