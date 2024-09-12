#!/usr/bin/env python3
from typing import Any, Callable, Tuple, Optional

import click
from invoke.exceptions import UnexpectedExit
from invoke.runners import Result
from fabric import Connection


class Context(Connection):
    """Summoner Context.

    This is an extension of the fabric Connection/invoke Context which has some
    additional context configuration and execution utilities for the summoner CLI.
    It is used with click.make_pass_decorator to provide a pass_context decorator
    that injects the Context as a dependency into commands.

    Args:
        host: str. SSH host to run commands on.

    Public Attributes:
        smn_dry_run: bool. Whether or not smn was invoked with --dry-run, which
            is a general use flag for dry run actions in commands.
        smn_debug: bool. Whether or not smn was invoked with --debug, enabling
            additional debug output command execution. Defaults to False.
        smn_is_local: bool. True of host argument (-H/--host) is local.
    """

    def __init__(self, host: str, *args: Any, **kwargs: Any) -> None:
        # Initialize connection with the supplied host.
        super().__init__(host, *args, **kwargs)

        # From invoke.DataProxy (InvokeContext's subclass) docs:
        # All methods (of this object or in subclasses) must take care to
        # initialize new attributes via ``self._set(name='value')``, or they'll
        # run into recursion errors!
        self._set(smn_dry_run=False)
        self._set(smn_debug=False)
        self._set(smn_is_local=host == "local")

    def run(self, *args: Any, **kwargs: Any) -> Optional[Result]:
        """Run a command.

        This conditionally calls either InvokeContext.run (Connection.local)
        locally or Connection.run remotely depending on if a remote host was supplied
        via the --host flag. Otherwise, this behaves exactly like InvokeContext.run.

        Run arguments (applies to local or remote):
        https://docs.pyinvoke.org/en/stable/api/runners.html#invoke.runners.Runner.run

        Returns:
            result: Optional[Result]. Result of command execution, if captured.
        """

        if self.smn_is_local:
            # Fabric's Connection is based on Invoke's Context, but it rebinds .run
            # to .local, which allows for a Connection class to be used for both remote
            # and local execution.
            return self.local(*args, **kwargs)
        else:
            # Run the Fabric Connection's run() method on the supplied remote
            # host instead.
            return super().run(*args, **kwargs)

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
# make the Context available in any tomes that ask for it. ensure=False is set
# because the Context is manually created and set in the main tome() function
# instead.
# pyre-fixme[5]: Globally accessible variable `pass_context` must be specified
# as type that does not contain `Any`.
pass_context: Callable[..., Any] = click.make_pass_decorator(Context, ensure=False)
