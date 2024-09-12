#!/usr/bin/env python3
from smn import tome, Context, pass_context


@tome.group("sys", short_help="system commands")
@pass_context
def sys(ctx: Context) -> None:
    pass


@sys.command("info", help="system information")
@pass_context
def sys_info(ctx: Context) -> None:
    ctx.run("neofetch")
