#!/usr/bin/env python3
from typing import Any, Callable, Optional, Tuple, Union, cast

import click
from fabric2 import Connection
from invoke.exceptions import UnexpectedExit
from invoke.runners import Promise, Result


class Context(Connection):
    """Summoner Context.

    This is an extension of the main InvokeContext which has some additional
    context configuration and execution utilities for the summoner CLI. It is
    used with click.make_pass_decorator to provide a pass_context decorator
    that injects the Context as a dependency into commands.

    Public Attributes:
        smn_dry_run: bool. Whether or not smn was invoked with --dry-run, which
            is a general use flag for dry run actions in commands.
        smn_debug: bool. Whether or not smn was invoked with --debug, enabling
            additional debug output command execution. Defaults to False.
    """

    def __init__(
        self,
        host: str,
        cache_force: bool = False,
        cache_disable: bool = False,
        *args: Any,
        **kwargs: Any,
    ) -> None:
        # Initialize connection with the supplied host.
        super().__init__(host, *args, **kwargs)

        # From invoke.DataProxy (InvokeContext's subclass) docs:
        # All methods (of this object or in subclasses) must take care to
        # initialize new attributes via ``self._set(name='value')``, or they'll
        # run into recursion errors!
        self._set(smn_dry_run=False)
        self._set(smn_debug=False)
        self._set(smn_is_local=host == "local")
        self._set(smn_use_crlf=False)
        self._set(smn_cache_force=cache_force)
        self._set(smn_cache_disable=cache_disable)

    def cache_command(
        self,
        command: str,
        ttl: int,
        stale: Optional[int] = None,
        force: bool = False,
    ) -> str:
        """Add caching to a command run with bkt.

        Requires the bkt utility: https://github.com/dimo414/bkt

        Args:
            command: str. Command to run with bkt caching.
            ttl: int. Duration in seconds to cache the command result.
            stale: Optional[int]. An optional time in seconds, lower than the
                ttl. If the same command is invoked between stale and ttl, bkt
                will cache the result in the background, avoiding a run in the
                foreground after the ttl expires.
            force: bool. If True, this will force a run and re-cache of the
                command.

        Returns:
            cmd: str. The provided command, with bkt caching arguments added.

        Raises:
            ValueError: If stale is greater than ttl.
        """

        if stale is not None and stale > ttl:
            raise ValueError(f"Invalid stale setting {stale} must be lower than {ttl}")

        ttl_flag = f"--ttl={ttl}s"
        maybe_stale = f"--stale={stale}s" if stale else ""
        maybe_force = "--force" if self.smn_cache_force or force else ""

        return f"bkt {ttl_flag} {maybe_stale} {maybe_force} -- {command}"

    def run(
        self,
        command: str,
        *args: Any,
        **kwargs: Any,
    ) -> Result:
        """Run a command.

        This conditionally calls either InvokeContext.run (Connection.local)
        locally or Connection.run remotely depending on if a remote host was supplied
        via the --host flag. Otherwise, this behaves exactly like InvokeContext.run.

        Run arguments (applies to local or remote):
        https://docs.pyinvoke.org/en/stable/api/runners.html#invoke.runners.Runner.run

        The disown and asynchronous options to the invoke runner have been
        split into their own methods run_disown and run_async in order to avoid
        a complex return type.

        Args:
            command: str. Command to run.
            use_crlf: bool. Replace LF (\\n) with CRLF (\\r\\n) when sending to
                process stdin. This can help with tools like fzf which expect
                CRLF for interactive user confirmation.
            cache_ttl: int. (bkt) Duration in seconds to cache the command
                result.
            cache_stale: Optional[int]. (bkt) An optional time in seconds, lower than the
                ttl. If the same command is invoked between stale and ttl, bkt
                will cache the result in the background, avoiding a run in the
                foreground after the ttl expires.
            cache_force: bool. (bkt) If True, this will force a run and re-cache of the
                command.

        Returns:
            result: Result. Result of command execution.

        Raises:
            UnexpectedExit: If execution of the command fails unexpectedly.
            ValueError: If disown=True or asynchronous=True are provided. These
                have distinct return types so their dedicated run_disown and
                run_async functions on the Context should be called.
        """

        if kwargs.get("disown"):
            raise ValueError("Use ctx.run_disown() instead of ctx.run(disown=True)")
        elif kwargs.get("asynchronous") in kwargs:
            raise ValueError(
                "Use ctx.run_async() instead of ctx.run(asynchronous=True)"
            )

        return cast(Result, self.__run(command, *args, **kwargs))

    def run_async(self, command: str, *args: Any, **kwargs: Any) -> Promise:
        """Run a command asynchronously.

        This leverages invoke's asynchronous=True option, which will immediately
        return a Promise after starting the command in another thread. See
        the docs for invoke.run for more info.

        Args:
            command: str. Command to run.

        Returns:
            promise: Promise. An invoke Promise object with execution info for
                the command running in the background.
        """

        return cast(Promise, self.__run(command, *args, **kwargs, asynchronous=True))

    def run_disown(self, command: str, *args: Any, **kwargs: Any) -> None:
        """Run a command and "disown" it.

        This leverages invoke's disown=True option, which immediately returns
        after starting the command, effectively forking it from the smn process.

        Args:
            command: str. Command to run.
        """

        return cast(None, self.__run(command, *args, **kwargs, disown=True))

    # invoke.Context already has a _run method
    def __run(
        self,
        command: str,
        *args: Any,
        use_crlf: bool = False,
        cache_ttl: Optional[int] = None,
        cache_stale: Optional[int] = None,
        cache_force: bool = False,
        **kwargs: Any,
    ) -> Union[None, Result, Promise]:
        if cache_ttl and not self.smn_cache_disable:
            command = self.cache_command(command, cache_ttl, cache_stale, cache_force)

        # See smn.runners.Local and smn.runners.Remote
        # Set the user supplied value for use_crlf on the Context, which is the
        # only thing the runner has access to in order to determine whether or
        # not to enable CRLF replacement.
        self._set(smn_use_crlf=use_crlf)

        if self.smn_is_local:
            # Fabric's Connection is based on Invoke's Context, but it rebinds .run
            # to .local, which allows for a Connection class to be used for both remote
            # and local execution.
            return self.local(command, *args, **kwargs)
        else:
            # Run the Fabric Connection's run() method on the supplied remote
            # host instead.
            return super().run(command, *args, **kwargs)

    def run_entrypoint(
        self, name: str, command: Tuple[str, ...], *args: Any, **kwargs: Any
    ) -> None:
        """Run an "entrypoint".

        This is intended for use inside of smn-run entrypoints, and will pass
        through all arguments from smn to a given named command.

        All unspecified args/kwargs will be forwarded on to Context.run.

        Args:
            name: str. Name of the command to run.
            command: Tuple[str, ...]. All arguments passed through from an
                entrypoint smn-run command.
        """

        try:
            self.run(f"{name} {' '.join(command)}", *args, **kwargs)
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
