#!/usr/bin/env python3
from typing import Optional
from sys import stdin

import click
from click_tree import ClickTreeParam
from invoke.config import Config

from smn.context import Context, pass_context


@click.group(
    name="smn",
    context_settings={"help_option_names": ["--smn-help"]},
)
@click.option(
    "--tome",
    "_tome",
    type=click.Path(exists=True, file_okay=True, dir_okay=False, readable=True),
    required=False,
    help="directly specify path to root tome",
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
def tome(
    ctx: Context,
    _tome: Optional[str],
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
        "pty": stdin.isatty(),
        # Disable all invoke command execution, this seems to also force echo=True.
        "dry": disable_execution,
    }

    ctx.config = Config(overrides=cfg)
