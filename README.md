# Summoner (smn)

Summoner (`smn`) is a macro-utility for definining lightweight python based
automations using [fabric](https://github.com/fabric/fabric) and [click](https://github.com/pallets/click).

# Getting Started
## TL; DR

```bash
# Install summoner-cli
pip install summoner-cli

# Clone and run smn against the example tome
git clone https://github.com/adammillerio/smn.git
smn --smn-help
smn hello
```

## Detailed

Summoner can be installed via pip:

```bash
pip install summoner-cli
```

Commands are loaded into Summoner via a "Tome", which is just a Python file that
defines Commands and Groups using the Click CLI framework. This file can import
other files or define commands directly.

A basic hello world example (`hello_world.py`):

```python
#!/usr/bin/env python3
from smn import tome, Context, pass_context


@tome.command("hello")
@pass_context
def hello(ctx: Context) -> None:
    """world!"""

    ctx.run("echo \"hello $(hostname)!\"", echo=True)

```

This command can then be executed both locally by default, or on any remote SSH
host via the `-H` (`--host`) flag:

```bash
aemiller@izalith> smn --tome hello_world.py hello
echo "hello $(hostname)!"
hello izalith!
aemiller@izalith> smn --tome hello_world.py -H ravenholm hello
echo "hello $(hostname)!"
hello ravenholm!
```

In this example, `ravenholm` is a host defined in the local `~/.ssh/config`, which
is loaded similarly to the `ssh` CLI:
```
Host ravenholm
    HostName ravenholm.domain.local
    ...
```

An example tome with some basic commands is provided at [tome.py](tome.py). Summoner
will load `./tome.py` by default if `--tome` is not provided.


You can explore available tomes by invoking them with the `--smn-help` option:
```bash
smn --tome hello_world.py --smn-help
Usage: smn [OPTIONS] COMMAND [ARGS]...

  a macro command runner

Options:
  --tome FILE          directly specify path to root tome
  --tree               enable tree display
  --dry-run            enable dry-run mode
  --disable-execution  disable all command execution
  --debug              output additional debug info
  -H, --host TEXT      host to run commands on via ssh, defaults to local
                       execution
  --smn-help           Show this message and exit.

Commands:
  hello  world!
```

Or view a command tree with the `--tree` option:
```
smn --tome hello_world.py --tree
smn
+-- hello - world!
```

# Usage
`smn` is best explained via hands on examples. This will demonstrate adding a 
single task to `smn`.

## The Goal
Write a tome with a task which, when given invoked with `--name`, will retrieve 
the current machine hostname and return the message:

```
Hello {name}! This is {machine}.
```

It should also run `uname -a` to print current system info.

## Create the Tome and Task

"Tome" files are really just python files that register new click Commands and 
Groups to a root "tome". There's no enforced naming convention, but typically 
they are named `tome.py`. For this example, we will place it in the hello
directory:

`hello/tome.py`:
```python
#!/usr/bin/env python3
from socket import gethostname

import click

from smn import Context, pass_context, tome


@tome.command("hello", help="Greet a user and show system information.")
@click.option("--name", type=str, help="Name to greet", required=True)
@pass_context
def hello(ctx: Context, name: str) -> None:
    machine = gethostname()

    click.secho(f"Hello, {name}! This is {machine}.", fg="green")

    ctx.run("uname -a")

```

Task composition is just standard Click, with the option of passing in a Fabric
Connection/Context if needed for things like running system commands.

One important general design aspect of `smn` is that tomes and their tasks should 
be largely free of dependencies. Other CLI interfaces are intended to have flexible
interfaces, so they should be invoked as commands rather than in code.

## Register the Tome
To register the tome, create a root `tome.py` and import the `hello` tome that
was just created:
`tome.py`:
```python
from .hello.tome import __name__
```

This will import the tome, which will register it to the `smn` root tome. When
`smn` is invoked without the `--tome` option, it will look in the current directory
and all parent directories until it finds a `tome.py` file to load.

## Run the Tome and Command
At this point the Tome is registered and is visible in the root tome `--smn-help`:
```sh
smn --smn-help            
...
Commands:
  hello        Greet a user and show system information.
```

And running it will print the expected output:
```sh
smn hello --name 'Foo'
Hello, Foo! This is izalith.
Darwin izalith 23.3.0 Darwin Kernel Version 23.3.0: Wed Dec 20 21:30:59 PST 2023; root:xnu-10002.81.5~7/RELEASE_ARM64_T6030 arm64
```

# Advanced Usage

## Groups

Click Groups can be used to define multiple commands under a single tome, similar 
to how Invoke task files work. This adjusts the above example to turn `hello` 
into a group, and provide subcommands for a day and night greeting:

`hello/tome.py`:
```python
#!/usr/bin/env python3
from socket import gethostname

import click

from smn import Context, pass_context, tome


@tome.group("hello", short_help="Greet a user and show system information.")
@click.option("--name", type=str, help="Name to greet", required=True)
@pass_context
def hello(ctx: Context, name: str) -> None:
    machine = gethostname()

    click.secho(f"Hello, {name}! This is {machine}.", fg="green")

    ctx.run("uname -a")


@hello.command("day", help="Greet a user in the day.")
def hello_day() -> None:
    click.secho("Have a good day.")


@hello.command("night", help="Greet a user in the night.")
def hello_night() -> None:
    click.secho("Have a good night.")

```

Like any Click Group, this allows for clustering of shared code and arguments in 
the group definition:

```sh
smn hello --name 'Foo' day
Hello, Foo! This is izalith.
Darwin izalith 23.3.0 Darwin Kernel Version 23.3.0: Wed Dec 20 21:30:59 PST 2023; root:xnu-10002.81.5~7/RELEASE_ARM64_T6030 arm64
Have a good day.

smn hello --name 'Foo' night
Hello, Foo! This is izalith.
Darwin izalith 23.3.0 Darwin Kernel Version 23.3.0: Wed Dec 20 21:30:59 PST 2023; root:xnu-10002.81.5~7/RELEASE_ARM64_T6030 arm64
Have a good night.
```

## Click Context

If you need to share data within your tome, you can pass in the default Click Context. 

For example, to instead store the first message as an initial greeting so it can 
be included on one line:
`hello/tome.py`:
```python
#!/usr/bin/env python3
from socket import gethostname

import click

from aecode.tools.smn import Context, pass_context, tome


@tome.group("hello", short_help="Greet a user and show system information.")
@click.option("--name", type=str, help="Name to greet", required=True)
@pass_context
@click.pass_context
def hello(click_ctx: click.Context, ctx: Context, name: str) -> None:
    machine = gethostname()

    click_ctx.obj["initial_greeting"] = f"Hello, {name}! This is {machine}."

    ctx.run("uname -a")


@hello.command("day", help="Greet a user in the day.")
@click.pass_context
def hello_day(click_ctx: click.Context) -> None:
    initial_greeting = click_ctx.obj["initial_greeting"]

    click.secho(f"{initial_greeting} Have a good day.", fg="green")


@hello.command("night", help="Greet a user in the night.")
@click.pass_context
def hello_night(click_ctx: click.Context) -> None:
    initial_greeting = click_ctx.obj["initial_greeting"]

    click.secho(f"{initial_greeting} Have a good night.", fg="green")

```

```sh
smn hello --name 'Foo' day
Darwin izalith 23.3.0 Darwin Kernel Version 23.3.0: Wed Dec 20 21:30:59 PST 2023; root:xnu-10002.81.5~7/RELEASE_ARM64_T6030 arm64
Hello, Foo! This is izalith. Have a good day.

smn hello --name 'Foo' night
Darwin izalith 23.3.0 Darwin Kernel Version 23.3.0: Wed Dec 20 21:30:59 PST 2023; root:xnu-10002.81.5~7/RELEASE_ARM64_T6030 arm64
Hello, Foo! This is izalith. Have a good night.
```

`obj` is basically just a normal "typeless" key/value dictionary, so use it carefully.

## Aliases

Command aliases can be created by using the `add_command` method on any defined 
Click Command or Group, including the root tome:
```python
#!/usr/bin/env python3
from smn import Context, pass_context, tome


@tome.group("sl", short_help="Run sapling SCM")
def sapling() -> None:
    pass


@sapling.command("pull-rebase", help="Pull repo and rebase current commit to latest")
@pass_context
def pull_rebase(ctx: Context) -> None:
    pass


# If name is not provided, it will just use the command's name (pull-rebase).
tome.add_command(pull_rebase, name="pull")

```

Now the `pull` command is bound to both `smn pull` and `smn sl pull-rebase`:
```sh
smn --smn-help
Commands
  ...
  pull         Pull repo and rebase current commit to latest
  sl           Run sapling SCM

smn sl --smn-help
Commands:
  ...
  pull  Pull repo and rebase current commit to latest
```

## Entrypoints

Many tomes work based on the concept of an "entrypoint". To give an example, here 
is a tome for the sapling SCM, which includes an entrypoint, as well as an 
additional command `smn sl pull-rebase`, which is a macro that performs `sl pull` 
and `sl rebase -d remote/main`:

```python
#!/usr/bin/env python3
from typing import Tuple

import click

from smn import Context, pass_context, tome
from smn.utils import Defaultgroup


@tome.group(
    name="sl", cls=DefaultGroup, default_if_no_args=True, short_help="Run sapling SCM"
)
def sapling() -> None:
    pass


@sapling.command(
    "smn-enter",
    default=True,
    help="Run sapling (sl)",
    context_settings={"ignore_unknown_options": True},
)
@click.argument("command", nargs=-1, type=click.UNPROCESSED)
@pass_context
def smn_enter(ctx: Context, command: Tuple[str, ...]) -> None:
    ctx.run_entrypoint("sl", command)


@sapling.command(
    "pull-rebase", help="Pull repo and rebase current commit to latest"
)
@pass_context
def pull_rebase(ctx: Context) -> None:
    ctx.run("sl pull", pty=True)
    ctx.run("sl rebase -d remote/main", pty=True, warn=True)


# Also register "pull" to the root tome.
tome.add_command(pull_rebase)

```

This makes invocation of the `smn sl` tome with no matching command behave as a 
transparent entrypoint into the `sl` binary itself. When combined with a shell 
alias, this effectively allows for "patching" other tools to provide additional 
commands:
```sh
alias sl='smn sl'
sl pull       
pulling from https://github.com/adammillerio/smn.git
sl pull-rebase
pulling from https://github.com/adammillerio/smn.git
abort: uncommitted changes
```

Entrypoints and default tome commands are always named `smn-run`, so they are 
clearly identifiable and do not collide with subcommands of the entrypoint.They 
can also be run like any other command. Pass the `--smn-help` option at any time 
to override entrypoint behavior and view tome information:
```sh
smn sl --help
Sapling SCM

sl COMMAND [OPTIONS]

smn sl --smn-help
Commands:
  pull-rebase  Pull repo and rebase current commit to latest
  run          Run sapling (sl)
```

There are a few important Click behavioral changes made here to facilitate this:
* A custom `DefaultGroup` click.Group class is used. This provides default command 
  functionality.
	* If the group is invoked with no arguments, then the default command will 
      be run.
* The run command is created with `default=True`, indicating it is the default 
  command for this group when no commands are matched.
* The context for run is configured with `ignore_unknown_options=True`. This causes 
  click to forward all options it does not recognize from here on as arguments. 
  This is required for the transparent passthrough of arguments in commands like 
  `smn sl --help`.
* The run command is configured with `nargs=-1` and `type=click.UNPROCESSED`. 
  This instructs click to pass through all arguments exactly as received with no 
  string processing.

## Standardizing Commands

Standardizing commands can be done by a combination of a combined 
options/arguments/context decorator as well as a pass through function to be used 
in the command definition itself. For example, to make a standard command for 
controlling lights via the `hass-cli`:

```python
from typing import TypeVar


TAny = TypeVar("TAny")


def toggle_command(ctx: Context, entity_id: str) -> None:
    ctx.run(
        f"hass-cli service call homeassistant.toggle --arguments entity_id={entity_id}"
    )

def light_on_command(ctx: Context, entity_id: str, level: int) -> None:
    arguments = f"entity_id={entity_id}"

    if level:
        # Brightness is 0-255 in HA, but 0-100 is more intuitive in a CLI.
        arguments += f",brightness={ceil(level * 2.55)}"

    ctx.run(f"hass-cli service call light.turn_on --arguments {arguments}")


light_command_kwargs = {
    "help": "light control",
    "epilog": "Toggle light(s) state, or set to a specific level from 0-100",
}


def light_options(func: Callable[..., TAny]) -> Callable[..., TAny]:
    func = pass_context(func)
    func = click.argument("level", type=int, required=False)(func)

    return func


def light_command(entity_id: str, ctx: Context, level: int) -> None:
    if not level:
        toggle_command(ctx, entity_id)
    else:
        light_on_command(ctx, entity_id, level)
```

Then just define each light related command using the shared functionality:

```python
@tome.group("kitchen", short_help="kitchen")
def kitchen() -> None:
    pass


@kitchen.command("lights", **light_command_kwargs)
@light_options
def home_kitchen_lights(*args: Any, **kwargs: Any) -> None:
    light_command("light.kitchen_lights", *args, **kwargs)


@tome.group("living", short_help="kitchen")
def living() -> None:
    pass


@living.command("lights", **light_command_kwargs)
@light_options
def home_living_lights(*args: Any, **kwargs: Any) -> None:
    light_command("light.living_room_lights", *args, **kwargs)
```

Now `smn kitchen lights` and `smn living lights` share the same inputs and 
functionality. It will either toggle the light state if no level is provided, or 
set the light level to a value provided from 0-100: `smn kitchen lights 50`

## Longform Command Help

To provide longform command help, a docstring can be provided:

```python
@sapling.command("pull-rebase", help="Pull repo and rebase current commit to latest")
@pass_context
def pull_rebase(ctx: Context) -> None:
    """Pull repo and rebase current commit to latest

    This will pull the latest remote repository information using the sapling CLI
    and then attempt to rebase the current working copy against remote/main.
    """

```

The first line, `Pull repo and rebase current commit to latest` will become the 
command short help, while the rest will be shown when the command is run with 
`--smn-help`. This can also be set via `help` during `@click.command` decoration, 
but this will override any docstring that is present.

Alternatively, there is also the `epilog` argument to `@click.command`, which will 
print the provided string after all of the click generated help text is provided. 
This can be useful as an alternative for providing a standard set of command help, 
as shown in the standardizing example above.
