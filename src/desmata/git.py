from pathlib import Path
from medina.tool import Tool, MajorMinorPatch
from typing import cast
from logging import Logger

class Git(Tool):
    _repo_name: str | None = None
    _project_root: Path | None = None
    _version: MajorMinorPatch | None = None

    def __init__(self, log: Logger):
        super().__init__(name="git", log=log)

    @property
    def repo_name(self) -> str:
        if not Git._repo_name:
            Git._repo_name = self.project_root.stem
        return Git._repo_name

    @property
    def project_root(self) -> Path:
        if not Git._project_root:
            result = self.run("rev-parse", "--show-toplevel", tolerate_err=True)
            if result.exit_code:
                raise EnvironmentError(f"git failed with code: {result.exit_code}")
            Git._project_root = Path(result.stdout.strip())
            Git._project_root.resolve()
        return Git._project_root

    @property
    def version(self) -> MajorMinorPatch:
        if not Git._version:
            Git._version = cast(MajorMinorPatch, tuple(map(int, self("version").split(" ")[2].split("."))))
        return Git._version

    def check(self) -> None:
        min_ver = (2, 0, 0)
        if not min_ver <= self.version:
            raise EnvironmentError(f"{self.name} is at {self.version} but {min_ver} is required")

    def ignore(self, it: Path, root: None | Path = None) -> None:
        """
        Adds the indicated file to the project's .gitignore file,
        if it's not already there.  Used to prevent secrets from
        ending up in source control.
        """
        if not root:
            root = self.project_root
        gitignore = root / ".gitignore"
        gitignore.touch()
        relpath = str(it.relative_to(root))
        lines = gitignore.read_text().splitlines()
        if relpath not in lines:
            gitignore.write_text("\n".join([*lines, relpath]))

    def current_commit(self, short: bool = False) -> str:
        length = ["--short"] if short else []
        return self(*["rev-parse", *length, "HEAD"]).strip()

    def is_dirty(self) -> bool:
        status = self("status", "--porcelain").strip()
        return status != ""
