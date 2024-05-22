#!/usr/bin/env python3
import sys
from typing import Any, Callable, Tuple, Optional

import click
from click_tree import ClickTreeParam
from invoke.context import Context as InvokeContext
from invoke.config import Config
from invoke.exceptions import UnexpectedExit
from invoke.runners import Result

from smn.utils import DefaultGroup


class Context(InvokeContext):
    """Summoner Context.

    This is an extension of the main InvokeContext which has some additional
    context configuration and execution utilities for the summoner CLI. It is
    used with click.make_pass_decorator to provide a pass_context decorator
    that injects the Context as a dependency into commands.

    Public Attributes:
        smn_debug: bool. Whether or not smn was invoked with --debug, enabling
            additional debug output command execution. Defaults to False.
    """

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)

        # From invoke.DataProxy (InvokeContext's subclass) docs:
        # All methods (of this object or in subclasses) must take care to
        # initialize new attributes via ``self._set(name='value')``, or they'll
        # run into recursion errors!
        self._set(smn_dry_run=False)
        self._set(smn_debug=False)

    def run_entrypoint(self, name: str, command: Tuple[str, ...]) -> None:
        """Run an "entrypoint".

        This is intended for use inside of smn-run entrypoints, and will pass
        through all arguments from smn to a given named command.

        Args:
            name: str. Name of the command to run.
            command: Tuple[str, ...]. All arguments passed through from an
                entrypoint smn-run command.
        """

        try:
            self.run(f"{name} {' '.join(command)}")
        except UnexpectedExit as e:
            # Re-raise nonzero exit code from entrypoint.
            raise click.exceptions.Exit(e.result.exited)


# Function decorator to pass global CLI context into a function. This is used to
# make the InvokeContext available in any tomes that ask for it.
# pyre-fixme[5]: Globally accessible variable `pass_context` must be specified
# as type that does not contain `Any`.
pass_context: Callable[..., Any] = click.make_pass_decorator(Context, ensure=True)


@click.group(
    name="smn",
    cls=DefaultGroup,
    default_if_no_args=True,
    context_settings={"help_option_names": ["--smn-help"]},
)
@click.option(
    "--tree",
    is_flag=True,
    type=ClickTreeParam(scoped=True, ignore_names=["smn-run"]),
    help="enable tree display.",
)
@click.option("--dry-run", is_flag=True, default=False, help="enable dry-run mode")
@click.option(
    "--disable-execution",
    is_flag=True,
    default=False,
    help="disable all command execution.",
)
@click.option(
    "--debug", is_flag=True, default=False, help="output additional debug info"
)
@pass_context
@click.pass_context
def tome(
    click_ctx: click.Context,
    ctx: Context,
    tree: Optional[bool],
    dry_run: bool,
    disable_execution: bool,
    debug: bool,
) -> None:
    """a macro command runner"""

    ctx._set(smn_dry_run=dry_run)
    ctx._set(smn_debug=debug)

    cfg = {}
    cfg["run"] = {
        # Enable echo of all running commands.
        "echo": ctx.smn_debug,
        # Mirror tty configuration of environment that is invoking smn. For example,
        # echo '{}' | tee empty.json will set pty=False, which will allow stdin
        # to flow in.
        "pty": sys.stdin.isatty(),
        # Disable all invoke command execution, this seems to also force echo=True.
        "dry": disable_execution,
    }

    ctx.config = Config(overrides=cfg)


@tome.command("smn-run", default=True, help="unearth a dusty tome")
def smn_run() -> None:
    click.secho("grimoire", fg="green")
