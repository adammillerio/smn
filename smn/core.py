#!/usr/bin/env python3
from sys import argv
from types import ModuleType
from typing import Callable
from inspect import isfunction

import click

import os, sys


def find_best_app(module: ModuleType) -> click.Group:
    """Given a module instance this tries to find the best possible
    application in the module or raises an exception.
    """

    # Search for app factory functions.
    app_factory = getattr(module, "create_cli", None)

    if isfunction(app_factory):
        try:
            app = app_factory()

            if isinstance(app, click.Group):
                return app
        except TypeError as e:
            if not _called_with_wrong_args(app_factory):
                raise

            raise ValueError(
                f"Detected factory 'create_cli' in module '{module.__name__}',"
                " but could not call it without arguments. Use"
                f" '{module.__name__}:{create_cli}(args)'"
                " to specify arguments."
            ) from e

    raise ValueError(
        "Failed to find Flask application or factory in module"
        f" '{module.__name__}'. Use '{module.__name__}:name'"
        " to specify one."
    )


def _called_with_wrong_args(f: Callable[..., click.Group]) -> bool:
    """Check whether calling a function raised a ``TypeError`` because
    the call failed or because something in the factory raised the
    error.

    :param f: The function that was called.
    :return: ``True`` if the call failed.
    """
    tb = sys.exc_info()[2]

    try:
        while tb is not None:
            if tb.tb_frame.f_code is f.__code__:
                # In the function, it was called successfully.
                return False

            tb = tb.tb_next

        # Didn't reach the function.
        return True
    finally:
        # Delete tb to break a circular reference.
        # https://docs.python.org/2/library/sys.html#sys.exc_info
        del tb


def locate_app(module_name: str) -> click.Group:
    try:
        __import__(module_name)
    except ImportError:
        # Reraise the ImportError if it occurred within the imported module.
        # Determine this by checking whether the trace has a depth > 1.
        if sys.exc_info()[2].tb_next:  # type: ignore[union-attr]
            raise ValueError(
                f"While importing {module_name!r}, an ImportError was"
                f" raised:\n\n{traceback.format_exc()}"
            ) from None
        else:
            raise NoAppException(f"Could not import {module_name!r}.") from None

    module = sys.modules[module_name]

    return find_best_app(module)


def prepare_import(path: str) -> str:
    """Given a filename this will try to calculate the python path, add it
    to the search path and return the actual module name that is expected.
    """
    path = os.path.realpath(path)

    fname, ext = os.path.splitext(path)
    if ext == ".py":
        path = fname

    if os.path.basename(path) == "__init__":
        path = os.path.dirname(path)

    module_name = []

    # move up until outside package structure (no __init__.py)
    while True:
        path, name = os.path.split(path)
        module_name.append(name)

        if not os.path.exists(os.path.join(path, "__init__.py")):
            break

    if sys.path[0] != path:
        sys.path.insert(0, path)

    return ".".join(module_name[::-1])


def load_cli() -> click.Group:
    """Loads the Flask app (if not yet loaded) and returns it.  Calling
    this multiple times will just result in the already loaded app to
    be returned.
    """

    import_name = prepare_import("cli.py")
    app = locate_app(import_name)

    return app


def cli() -> None:
    tome = load_cli()

    # Run the root tome command, which now has all tomes registered to it.
    tome()
