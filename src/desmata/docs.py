"""
This module provides the ability to view and generate desmata's docs.

It is called by a pre-commit hook to ensure that the docs at 
[polyose.github.io/desmata](https://polyose.github.io/desmata) stay up
to date with the code.

A user which already has desmata might also use these to view the docs.
This way they're not separated from the docs even if they're on a separate
network partition than github.io

To do this run:

$ desmata docs view

...and click the link.
"""

import sys
from pathlib import Path

import click
from pdoc import pdoc

import desmata
from desmata.config import AppContext
from shutil import rmtree


def generate(app: AppContext, out: Path | None = None):
    """
    Generate docs for the current version of desmata.

    :param out: Put them here.  Defaults to $PWD/docs.
    """

    repo = Path.cwd()
    git = repo / ".git"
    if not out:
        out = repo / "docs"

        # is user at the root of a desmata repo?
        checks = {out: out.exists(), git: git.exists(), repo: repo.name == "desmata"}
        app.log.debug(f"is $PWD the root of a desmata repo? {checks}")
        if not all(checks.values()):
            # no, be cautious
            if not click.confirm(f"This will create/overwrite {out.resolve()} continue?", default=True):
                app.log.info("User Cancelled")
                sys.exit(0)
        else:
            # yes, clobber outdated docs with new ones
            rmtree(out)
            out.mkdir(parents=True)
            

    pdoc(Path(desmata.__file__), output_directory=out)
    app.log.info(f"generated docs in {out.resolve()}")

def view(app: AppContext):
    """
    Generates docs in the cache directory and prints a URL so the user can
    browse them.
    """
    cached_docs = app.home.cache / "docs"
    cached_docs.mkdir(exist_ok=True)
    generate(app, cached_docs)
    print(f"file://{cached_docs.resolve()}/index.html")
    
