#!/usr/bin/env python3
from smn import tome, Context, pass_context


@tome.command("hello")
@pass_context
def hello(ctx: Context) -> None:
    """world!"""

    ctx.run("echo 'world!'", echo=True)
