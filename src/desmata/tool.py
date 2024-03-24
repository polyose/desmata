import json
import os
import re
import subprocess
import sys
from collections.abc import Callable
from dataclasses import dataclass, field
from logging import Logger
from textwrap import indent
from typing import Any, TypeAlias, TypeVar
from unittest.mock import Mock
from pathlib import Path
from copy import deepcopy


ManifestObjects: TypeAlias = list[dict[str, Any]]
MajorMinorPatch: TypeAlias = tuple[int, int, int]

# dont print more than...
max_lines = 15
max_chars = 240  # per line


def short(line: str) -> str:
    """
    Don't overwhelm the user with text, truncate lines with '...'
    """
    if len(line) < max_chars:
        return line
    else:
        return line[: max_chars - 100] + "..." + line[-100:]


def pretty(it: str | None, prefix: str = "") -> str:
    """
    Don't overwhelm the user with text, omit lines with '...'
    """
    if it is None or it.strip() == "":
        return ""
    else:
        lines = [x for x in it.splitlines() if x.strip() != ""]
        if len(lines) < max_lines:
            return indent("\n".join(map(short, lines)), prefix=prefix)
        return indent(
            "\n".join(map(short, [*lines[: max_lines - 5], "...", *lines[-5:]])),
            prefix=prefix,
        )


def env_pretty(inner: dict[str, str], outer: dict[str, str]) -> dict[str, str]:
    """
    Only log env vars if they differ from the enclosing environment.
    """
    show = {}
    for k, v in inner.items():
        if k == "KUBECONFIG":
            try:
                outer_v = outer[k]
            except KeyError:
                show[k] = v
            else:
                if v != outer_v:
                    show[k] = v
    return show


def log_pretty(it: str) -> str:
    return short(re.sub(r"\s*\n\s*", ";", it.strip() or ""))


def too_long(it: str | None) -> bool:
    lines = (it or "").splitlines()
    if len(lines) >= max_lines:
        return True
    if any(len(x) > max_chars for x in lines):
        return True
    return False


# be nonspecific about how custom cmd and env filters come up with Cmds and EnvVars
Cmd: TypeAlias = str | list[str]
EnvVars: TypeAlias = dict[str, str]


@dataclass
class PendingCommand:
    cmd: list[str]
    stdin: str
    env: dict[str, str]
    outer_env: dict[str, str]
    kwargs: dict[str, str] = field(default_factory=dict)

    def check(self) -> None:
        """
        Raises ValueError if any keys or values are not strings
        """
        nonstr = {
            k: v
            for k, v in self.env.items()
            if not isinstance(k, str) or not isinstance(v, str)
        }
        if nonstr:
            raise ValueError("invalid env vars:", nonstr)

    def __str__(self) -> str:
        d = {
            "cmd": self.cmd,
            "env": env_pretty(self.env, self.outer_env),
            "stdin": log_pretty(self.stdin)
            if not too_long(self.stdin)
            else f"{len(self.stdin.splitlines())} lines",
            **self.kwargs,
        }
        if not d["env"]:
            del d["env"]
        return json.dumps({"pending...": d})


@dataclass
class CompletedCommand:
    stdout: str
    exit_code: int

    def long_stdout(self) -> bool:
        lines = self.stdout.splitlines()
        if len(lines) >= max_lines:
            return True
        if any(len(x) > max_chars for x in lines):
            return True
        return False

    def __str__(self) -> str:
        return json.dumps(
            {
                "completed.": {
                    "stdout": log_pretty(self.stdout)
                    if not too_long(self.stdout)
                    else f"{len(self.stdout.splitlines())} lines",
                    "exit_code": self.exit_code,
                }
            }
        )


@dataclass
class Tool:
    """
    A helper for running commands. You can bind a fixed context when you initialize this
    class (i.e. the things that do not change between calls).  The interesting parts
    can be supplied on a per-call basis.

        # fixed context
        kubectl = Tool(name="kubectl",
                       env_filter = lambda e: dict(e, KUBECONFIG="/some/path"),
                       cmd_filter = lambda c: ["-n", "mynamespace", *c])

        # dynamic context
        kubectl(["get", "pods"])
    """

    log: Logger
    name: str
    path: Path | None = None
    cwd: Path | str | None = None
    cmd_filter: Callable[[Cmd], Cmd] | None = None
    env_filter: Callable[[EnvVars], EnvVars] | None = None
    show_stdin: bool = True
    show_stdout: bool = True

    def _print(self, string: str, prefix: str = "") -> None:
        if self.show_stdin or self.show_stdout:
            print(pretty(string, prefix=prefix), file=sys.stderr)

    def _print_stdin(self, string: str | None) -> None:
        if self.show_stdout and string and string.strip():
            self._print(string, prefix=f"  {self.name}<<  ")

    def _print_stdout(self, string: str) -> None:
        if self.show_stdout and string and string.strip():
            self._print(string, prefix=f"  {self.name}>>  ")

    def _build_cmd(self, *args: str) -> list[str]:
        if self.path:
            self.path.resolve()
            assert self.path.exists()
            name = str(self.path.absolute())
        else:
            name = self.name

        suffix = self.cmd_filter(list(args)) if self.cmd_filter else list(args)
        if isinstance(suffix, str):
            suffix = [suffix]
        return [name, *suffix]

    def get_popen_kwargs(self, **kwargs: Any) -> dict[str, Any]:
        """
        subprocess.Popen args can be bound to the tool object, or provided at
        call time via **kwargs.  Call this to move them to kwargs from the
        object and provide any other handling specific to that kwarg.
        """

        try:
            cwd = kwargs["cwd"]
        except KeyError:
            cwd = self.cwd
            if isinstance(self.cwd, Path):
                kwargs["cwd"] = str(self.cwd.resolve())
            else:
                kwargs["cwd"] = self.cwd

        if cwd and isinstance(cwd, Path):
            kwargs["cwd"] = str(cwd.resolve())

        return kwargs

    def run(
        self,
        *args: str,
        env_extras: EnvVars = {},
        stdin: str | None = None,
        tolerate_err: bool = True,
        no_log: bool = False,
        no_stdout: bool = False,
        no_stdin: bool = False,
        **kwargs: Any,
    ) -> CompletedCommand:
        logfunc = self.log.getChild(self.name).debug
        if no_log:
            logfunc = Mock()

        # build cmd
        cmd = self._build_cmd(*args)

        # finalize Popen kwargs
        popen_kwargs = self.get_popen_kwargs(**kwargs)

        # build env
        outer_env = dict(os.environ)
        env = self.env_filter(outer_env.copy()) if self.env_filter else outer_env
        env.update(env_extras)

        # communicate attempt
        pending = PendingCommand(
            cmd=cmd, env=env, stdin=stdin or "", outer_env=outer_env, kwargs=popen_kwargs
        )
        logfunc(pending)
        pending.check()
        if not no_stdin:
            self._print_stdin(stdin)

        # pass stderr though, handle stdin and stdout explicitly
        process = subprocess.Popen(
            cmd,
            env=env,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=sys.stderr,
            text=True,
            **popen_kwargs,
        )

        # run it, provide stdin, get stdout
        stdout, _ = process.communicate(input=stdin)

        # communicate results
        completed = CompletedCommand(stdout, exit_code=process.returncode)
        logfunc(completed)
        if not no_stdout:
            if completed.long_stdout():
                self._print_stdout(stdout)
            self._print("\n")

        if not tolerate_err and completed.exit_code != 0:
            raise subprocess.CalledProcessError(completed.exit_code, cmd, output=stdout)

        return completed

    def __call__(
        self,
        *args: str,
        env_extras: EnvVars = {},
        stdin: str | None = None,
        tolerate_err: bool = False,
        no_log: bool = False,
        **kwargs: Any,
    ) -> str:
        """
        Like run() except only return stdout
        """
        return self.run(
            *args,
            env_extras=env_extras,
            stdin=stdin,
            tolerate_err=tolerate_err,
            no_log=no_log,
            **kwargs,
        ).stdout


SpecificTool = TypeVar("SpecificTool", bound="Tool")


def tweaked(tool: SpecificTool, **tweaks) -> SpecificTool:
    tweaked = deepcopy(tool)
    tweaked.__dict__.update(tweaks)
    return tweaked
