from desmata.tool import Tool, MajorMinorPatch, Cmd
from typing import cast
from logging import Logger
from pathlib import Path


class Nix(Tool):
    _version: MajorMinorPatch | None = None
    _flakes_enabled: bool | None = None

    def __init__(self, cwd: Path, log: Logger):
        def flakes_and_cmd(cmd: Cmd) -> Cmd:
            return [
                *["--extra-experimental-features", "nix-command"],
                *["--extra-experimental-features", "flakes"],
                *cmd,
            ]

        super().__init__(name="nix", cmd_filter=flakes_and_cmd, cwd=cwd, log=log)

    def build(
        self, output_name: str, path_suffix: str
    ) -> Path:
        return (
            Path(
                self(
                    "build",
                    f".#{output_name}",
                    "--print-out-paths",
                    "--no-link",
                ).strip()
            )
            / path_suffix
        )

    def get_nar_sha256_hex(self, path: Path) -> str:
        raise NotImplementedError()

    @property
    def version(self) -> MajorMinorPatch:
        if not Nix._version:
            Nix._version = cast(
                MajorMinorPatch,
                tuple(map(int, self("--version").split(" ")[-1].split("."))),
            )
        return Nix._version

    def check(self) -> None:
        min_ver = (2, 0, 0)
        if not min_ver <= self.version:
            raise EnvironmentError(f"{self.name} is at {self.version} but {min_ver} is required")

