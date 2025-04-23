#!/usr/bin/env python3
from __future__ import annotations

from contextlib import contextmanager, nullcontext
from contextvars import ContextVar
from copy import deepcopy
from os import PathLike, chdir, environ, execvp, execvpe
from sys import stdin
from typing import (
    Any,
    Callable,
    Generator,
    Mapping,
    NoReturn,
    Optional,
    Tuple,
    Union,
    cast,
)

import click
from fabric2 import Connection
from fabric2.config import Config
from invoke.exceptions import UnexpectedExit
from invoke.runners import Promise, Result

from smn.runners import Local, Remote
from smn.utils import exit_on_failure as _exit_on_failure

_HOST_CTX: ContextVar[Context] = ContextVar("_HOST_CTX")


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
        disable_execution: bool = False,
        dry_run: bool = False,
        debug: bool = False,
        *args: Any,
        **kwargs: Any,
    ) -> None:
        # Initialize connection with the supplied host.
        super().__init__(host, *args, **kwargs)

        # From invoke.DataProxy (InvokeContext's subclass) docs:
        # All methods (of this object or in subclasses) must take care to
        # initialize new attributes via ``self._set(name='value')``, or they'll
        # run into recursion errors!
        self._set(smn_dry_run=dry_run)
        self._set(smn_debug=debug)
        self._set(smn_is_local=host == "local")
        self._set(smn_cache_force=cache_force)
        self._set(smn_cache_disable=cache_disable)
        self._set(smn_disable_execution=disable_execution)

        # The state of this is managed via the _run() method based on the
        # use_crlf parameter
        self._set(smn_use_crlf=False)

        cfg = {}
        cfg["run"] = {
            # Enable echo of all running commands.
            "echo": debug,
            # Mirror tty configuration of environment that is invoking smn. For example,
            # echo '{}' | tee empty.json will set pty=False, which will allow stdin
            # to flow in.
            "pty": stdin.isatty(),
            # Disable all invoke command execution, this seems to also force echo=True.
            "dry": disable_execution,
        }

        # Use smn's custom Local and Remote runners for all actions.
        cfg["runners"] = {
            "local": Local,
            "remote": Remote,
        }

        self.config = Config(overrides=cfg)

    @contextmanager
    def ssh(self, host: str) -> Generator[None, None, None]:
        """Remote host context manager.

        This provides an interface similar to smn -H as a context manager, which
        will temporarily establish and execute commands against a remote host
        over SSH while it is active.

        Like invoke's ctx.cd, this will apply to all run() invocations within it:

        @tome.command("test")
        @pass_context
        def test(ctx: Context) -> None:
            ctx.run("hostname")

            with ctx.ssh("host1"):
                ctx.run("hostname")

                with ctx.ssh("host2"):
                    ctx.run("hostname")

        This would result in the hostname command being run locally, on host1,
        and on host2. Note that the Context is simply replaced in the case of
        multiple contexts, it does not provide any sort of SSH jump function.

        Args:
            host: str. Remote host to set up SSH Context for.
        """

        if not self.smn_dry_run:
            token = _HOST_CTX.set(
                Context(
                    host=host,
                    cache_force=self.smn_cache_force,
                    cache_disable=self.smn_cache_disable,
                    disable_execution=self.smn_disable_execution,
                    dry_run=self.smn_dry_run,
                    debug=self.smn_debug,
                )
            )
        else:
            # Dry run, don't make a context, since this will open a connection
            # even if execution is disabled
            token = None

        try:
            yield
        finally:
            if token:
                _HOST_CTX.reset(token)

    @contextmanager
    def host_context(self) -> Generator[Context, None, None]:
        """Retrieve the current host Context.

        In ctx.ssh() contexts, this will return the Context created for the
        remote host. Otherwise, it will return this Context itself.

        Yields:
            host_context: Context. Current host context to execute commands on.
        """

        yield _HOST_CTX.get(self)

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

        with self.host_context() as ctx:
            return cast(Result, ctx.__run(command, *args, **kwargs))

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

        with self.host_context() as ctx:
            return cast(Promise, ctx.__run(command, *args, **kwargs, asynchronous=True))

    def run_disown(self, command: str, *args: Any, **kwargs: Any) -> None:
        """Run a command and "disown" it.

        This leverages invoke's disown=True option, which immediately returns
        after starting the command, effectively forking it from the smn process.

        Args:
            command: str. Command to run.
        """

        with self.host_context() as ctx:
            return cast(None, ctx.__run(command, *args, **kwargs, disown=True))

    # invoke.Context already has a _run method
    def __run(
        self,
        command: str,
        *args: Any,
        use_crlf: bool = False,
        cache_ttl: Optional[int] = None,
        cache_stale: Optional[int] = None,
        cache_force: bool = False,
        exit_on_failure: bool = False,
        **kwargs: Any,
    ) -> Union[None, Result, Promise]:
        if cache_ttl and not self.smn_cache_disable:
            command = self.cache_command(command, cache_ttl, cache_stale, cache_force)

        # See smn.runners.Local and smn.runners.Remote
        # Set the user supplied value for use_crlf on the Context, which is the
        # only thing the runner has access to in order to determine whether or
        # not to enable CRLF replacement.
        self._set(smn_use_crlf=use_crlf)

        maybe_exit = _exit_on_failure() if exit_on_failure else nullcontext()
        with maybe_exit:
            if self.smn_is_local:
                # Fabric's Connection is based on Invoke's Context, but it rebinds
                # .run to .local, which allows for a Connection class to be used
                # for both remote and local execution.
                return self.local(command, *args, **kwargs)
            else:
                # Run the Fabric Connection's run() method on the supplied remote
                # host instead.
                return super().run(command, *args, **kwargs)

    def run_entrypoint(
        self,
        name: str | PathLike[str],
        command: Tuple[str, ...],
        *args: Any,
        **kwargs: Any,
    ) -> None:
        """Run an "entrypoint".

        This is intended for use inside of smn-run entrypoints, and will pass
        through all arguments from smn to a given named command.

        All unspecified args/kwargs will be forwarded on to Context.run.

        Args:
            name: str | PathLike[str]. Name or path of the command to run.
            command: Tuple[str, ...]. All arguments passed through from an
                entrypoint smn-run command.
        """

        try:
            self.run(f"{name} {' '.join(command)}", *args, **kwargs)
        except UnexpectedExit as e:
            # Re-raise nonzero exit code from entrypoint.
            raise click.exceptions.Exit(e.result.exited)

    def exec(
        self,
        command: str,
        env: Optional[Mapping[str, str]] = None,
        replace_env: bool = False,
        echo: bool = False,
    ) -> NoReturn:
        """Execute a command and replace smn with the new process.

        This is a special purpose method which uses the execvp() and execvpe()
        syscalls to execute the supplied command. Unlike run(), which uses the
        invoke/fabric libraries to start a new child process, this will completely
        replace smn with the supplied command. It will retain the same PID and
        all stdout/stdin/signals/etc will be routed to the executed command.

        Because this is a system call and a full replacement, it can only be
        run on the local machine smn itself is running on, and it will never
        return, so it cannot be used in between a chain of other commands. For
        almost all cases run() is preferred.

        However, subprocessing can get a bit messy when dealing with highly
        interactive programs. Garbled output/input, uncaught interrupts abruptly
        killing your subprocess, and inputs not working as expected are common
        when using things like neovim/ssh/htop through run(), since there is a
        lot of Python and threading in front of it.

        In these cases, exec() is ideal (and more or less essential). Since it
        is a full replacement, none of the above matters. smn will just start
        your command and completely get out of the way.

        More info: https://linux.die.net/man/3/execvp

        In addition to the local only caveat above, there are a few others:
        * A very limited set of invoke.run() options are implemented, see Args
        * With a dry run or execution disabled, smn will print the command and
          exit 0 to simulate the replacement behavior

        If exec() is called within a ctx.cd() context(s), then the chdir syscall
        will be used to update the working directory of the smn process itself
        prior to executing the command.

        Args:
            command: str. Command to run.
            env: Optional[Mapping[str, str]]. If provided, a copy of smn's
                running environment with these updates will be supplied to the
                execvpe() syscall.
            replace_env: bool. If True, the supplied env will be supplied
                directly to execvpe() discarding smn's current environment.
            echo: bool. If True, the command will be printed to stdout prior
                to execution.

        Raises:
            RuntimeError: If exec() is called while smn is running on a non-local
                host via the -H/--host flag.
        """

        with self.host_context() as ctx:
            ctx._exec(tuple(command.split(" ")), env, replace_env, echo)

    def exec_entrypoint(
        self,
        name: str | PathLike[str],
        command: Tuple[str, ...],
        env: Optional[Mapping[str, str]] = None,
        replace_env: bool = False,
        echo: bool = False,
    ) -> NoReturn:
        """Execute an "entrypoint" and replace smn with the new process.

        This is intended for use inside of smn-run entrypoints, and will pass
        through all arguments from smn to a given named command. See the docs
        for the main exec() method for more info.

        Args:
            name: str | PathLike[str]. Name or path of the command to run.
            command: Tuple[str, ...]. All arguments passed through from an
                entrypoint smn-run command.
            env: Optional[Mapping[str, str]]. If provided, a copy of smn's
                running environment with these updates will be supplied to the
                execvpe() syscall.
            replace_env: bool. If True, the supplied env will be supplied
                directly to execvpe() discarding smn's current environment.
            echo: bool. If True, the command will be printed to stdout prior
                to execution.

        Raises:
            RuntimeError: If exec() is called while smn is running on a non-local
                host via the -H/--host flag.
        """

        # args becomes the argv of the process being executed, which most things
        # expect to be the name of the executable
        command_args = (str(name),) + command

        with self.host_context() as ctx:
            ctx._exec(command_args, env, replace_env, echo)

    def _exec(
        self,
        argv: Tuple[str, ...],
        env: Optional[Mapping[str, str]] = None,
        replace_env: bool = False,
        echo: bool = False,
    ) -> NoReturn:
        if not self.smn_is_local:
            raise RuntimeError("exec is a syscall and is only supported on local runs")

        if echo or (self.smn_disable_execution or self.smn_dry_run):
            cmd = " ".join(argv)

            if self.cwd:
                cmd = f"cd {self.cwd} && {cmd}"

            cmd = self.config.run.echo_format.format(command=cmd)
            click.secho(cmd)

        if self.smn_disable_execution or self.smn_dry_run:
            # Explicitly exit 0 to simulate exec replacement behavior
            raise click.exceptions.Exit(0)

        if self.cwd:
            # Change the smn process working directory to the current cwd if
            # this is being ran in a with ctx.cd() block
            chdir(self.cwd)

        if not env:
            # Exec with the same environment as smn
            execvp(argv[0], argv)
        else:
            if replace_env:
                # Exec with the environment replaced entirely by the one provided
                execvpe(argv[0], argv, env)
            else:
                # Exec with a copy of smn's os.environ, updating it with the env
                # provided
                new_env = deepcopy(environ)
                new_env.update(env)

                execvpe(argv[0], argv, new_env)


# Function decorator to pass global CLI context into a function. This is used to
# make the Context available in any tomes that ask for it. ensure=False is set
# because the Context is manually created and set in the main tome() function
# instead.
# pyre-fixme[5]: Globally accessible variable `pass_context` must be specified
# as type that does not contain `Any`.
pass_context: Callable[..., Any] = click.make_pass_decorator(Context, ensure=False)
