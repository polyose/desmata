from abc import ABC, abstractmethod
from inspect import getcurrentframe, getfile
from logging import Logger
from pathlib import Path, PurePath
from datetime import datetime

from desmata.nix import Nix
from desmata.git import Git
from desmata.config import Home
from desmata.tool import tweaked

from pydantic import BaseModel


class ClosureItem(BaseModel):
    """
    A closure is a collection of directories and files which are not part of a
    cell, but which the cell depends on. Desmata populates these dependencies
    before [setup()](desmata.cell.CellBase.setup) is called.
    """

    id: str
    """
    A string which uniquely identifies the intended content of a ClosureItem.
    If nix is used, this corresponds with the nix store path.
    Otherwise this might be something like "jq-1.7.1-linux-amd64".

    These are used to expose the stability of the cell-closure relationship.
    If your closures are stable, 
    
    The intent is that these can be used as globally unique, human readable
    names.  Desmata can be configured to gossip metadataabout the actual
    bits that end up in these directories (hashes mostly). Comparing these 
    hashes with your peers may help identify cases where:
    
    1. builds aren't repeatable
    2. someone has sneaked malware into a dependency
    3. the correspondence between id and content is ambiguous for some other
       reason

    This gives users more information than they typically have when deciding 
    whether to trust the correspondence between a name and a set of bits.
    """

    # pathlib.Path is not supported by pydantic
    # so we store a pure path here
    _path: PurePath

    @property
    def path(self) -> Path:
        """
        Where on the local filesystem is this external dir?
        """
        return Path(self._path)

    @staticmethod
    def from_nix_store(path: Path) -> "ClosureItem":
        """
        Creates a closure item from a nix store path.

        Typically a filename makes a bad closure item ID because the same file
        might be named differently by different peers.  This would waste space
        by causing desmata to store two copies of it.  Nix is an exception
        because nix store paths are expected to be the same if they contain the
        same file.
        """
        return ClosureItem(id=path.name, _path=path)


class Closure(BaseModel, ABC):

    items: list[ClosureItem]

    @abstractmethod
    def __init__(self, log: Logger):
        """
        This is where you resolve your cell's dependencies.
        """
        raise NotImplementedError()

    def enclose(self, *items: ClosureItem):
        """
        Call this from the closure's __init__ function once the closure items
        have been populated in the local filesystem.
        """
        items = items
        calling_file = getfile(getcurrentframe().f_back)
        self._name = Path(calling_file).resolve().name



    @property
    def relative_inputs(self) -> list[PurePath]:
        """
        A list of paths, relative to desmata.py, which are required to build
        this cell's Closure.
        """
        return [PurePath("./flake.nix"), PurePath("./flake.lock")]

    @property
    def inputs(self) -> list[Path]:
        """
        Which files in this cell does its closure depend on?

        A typical nix flake will copy the entire repository into the nix store
        and use it as an input to build the closure. Desmata differes here.
        Instead it uses hard links to place only the files that are explicitly
        listed as closure inputs into a repo of their own, and then uses that to
        build the closure.  This makes it easier to be explicit about when the
        closure should change and what it should include.

        Desmata makes it possible to share both cells and closures with your
        peers, but these two are kept separate, and are only shared if
        configured to do so.  This makes it possible to store secrets in a cell,
        which is kept private, but to leave pars of the closure public.
        """
        return [Path(_path) for _path in self.relative_inputs]

    @property
    def name(self):
        """
        If you let some bits name themselves, they might tell you a misleading
        one. To prevent this, Desmata instead asks you to name the  cell. You
        do this when you decide where to put it. The parent  directory from
        desmata.py determines the cell's name.

        When referencing cells which are not on your machine, desmata prefixes
        the cell with the user's name (it's also up to you to associate names
        with the keys of users that you trust).

        So if you want to install a cell which your friend Alice has stored in
        a folder called foo, you can use `Alice.foo` to refer to it.  If your
        name is Bob, and you store it in a directory called bar, then your local
        name for the cell is Bob.bar

        If Alice is browsing cells, she will see that Alice.foo and Bob.bar are
        references to the same cell (unless one of you has since made changes
        to the cell).

        This is a strange design choice, but globally unique names are high
        value targets for corruption, and Desmata's approach to resisting
        corruption is to avoid creating high value targets in the first place.

        If you're not interested in trusting people and you'd rather trust
        package names instead, consider using pretty much any other mechanism
        for sharing data. Exploring the consequences of this design decision
        is the purpose of this project.
        """
        return Path(self.desmata_py).parent.name

    @property
    def id(self):
        raise NotImplementedError(
            """
        A cell's ID is a hash of its contents.  We will use IPFS CID's for this.
        """
        )

    @property
    def nucleus_id(self):
        """
        A cell's "nucleus" is all of the directories that it contains.  This
        does not include the non-directory files in the cell's top level
        directory, these are called the "membrane".  If that's an
        uncomfortable word, don't worry, it's the last biology metaphor.

        Nucleus files should be ones that are unlikely to change, even if a
        cell is shared between users.  Membrane files should be simple and
        easy to audit.

        The idea here is that if you have a nucleus which you already trust,
        browsing its membranes is a way of seeing how your peers are using that
        nucleus. Cell authors are encouraged to provide documentation
        and example usage, but the nucleus/membrane split is there so that you
        can get additional guidance from your peers.

        This also ensures that the same nucleus ends up in the hands of a wide
        variety of peers.  Auditing the contents of a nucleus may require more
        time than auding a membrane, but since nuclei change infrequently,
        their audits may benefit a wider audience.

        Desmata's philosophy here is that most people do not trust bits because
        they have audited them.  Instead, users trust bits because they trust
        somebody, who trusts somebody... who actually has audited those bits
        (perhaps this is the original author of those bits, perhaps not).  If
        the trust graph that emerges from such a commuity of users is large and
        well connected, then users can potentially have high confidence that
        those bits are trustworthy.

        Trust graphs like this grow informally whenever one user tells another
        user the name of a package that they like to use.  Desmata intends to
        mediate this trust more expicitly so that it can help a wider audience.

        When packages are resolved by name, there is a disconnect between
        the community trust which ensures that the named package is trustworthy,
        and the actual bits which end up on a user's machine.  Perhaps you
        installed a package with a trustworthy name, but somehow (by accident
        or by maliciousness) you ended up with bits which are not trustworthy.

        The mathy solution here is that users should communicate via
        cryptographic hashes instead of in names, but that's not how real
        humans work.  Desmata is a sort of compromise here. It gives up on
        the convenience of a globally unique name, but it also limits the degree
        to which users need to communicate in terms of cryptographc hashes.
        Instead, if Bob wants to trust Alice's packaged called foo, bob trusts
        Alice.foo.  Desmata propagates this trust in terms of public keys and
        cryptographic hashes, but the experience remains relatively user
        friendly for Bob and Alice.
        """
        raise NotImplementedError()

    items: list[ClosureItem]

    def __init__(self, *items: ClosureItem, desmata_py: str):
        self.desmata_py = desmata_py
        items = items


Closure.__doc__ = """
A cell on its own is unlikely to be useful. It probably needs other stuff too.

For ianstance, if the cell contains a C program, you'll likely need a C compiler
to use it. If the cell knows how to get the appropriate compiler, then the
compiler is in that cell's *closure*. This is intended to align with the concept
of a nix closure because by default desmata cells use nix for this.

Desmata aims to make it possible for you to get the right closure for your
device and to share it with peers who might need the same closure.  It also
tries to make it easier to know which closures (and which cells) are
trustworthy.

Thcere are a variety of reasons that peers may disagree about which closures
correspond with a cell. For instance, suppose that the closure uses a C
compiler to generate some machine code. If you and a peer are using devices with
differing system architectures, you will end up with different machine code.

Another reason for closure disgreement is that separate attempts to build the
same seoftware accidentally result in different bits due to the inclusion of a
timestamp or use of some nondeterministic computation by the build toolchain.
Perhaps subtle differences are introduced based on how many processor cores
or how much memory the builder has.

These differences are not hazardous on their own, but they encourage the idea
that software with the same name might legitimately be distributed via artifacts
of slightly different composition. That's a problematic idea because it
interferes with the attempts to build consensus about which closures are
trustworthy and which are malicious.

Desmata cannot identify malicious software directly, but when used by a
sufficiently vigilant community it can help you know whether you're about to
use the same software that your peers know and trust, or whether you're about
to use software that has never been seen by any of your peers before. The latter
case deserves some scrutiny, especially if you expected to be using something
repuatble.

Whether the metadata that Desmata makes available actually indicates anything
about trustworthyness depends on which peers you configure it to trust,
and whether they are actually trustworthy (and whether *their* peers are
trustworthy).
"""


def is_same_file(a: Path, b: Path) -> bool:
    """
    Closure inputs are a subset of the overall cell.
    Desmata creates hardlinks between...
        - /some/path/{cellname}
        - $XDG_DATA_HOME/desmata/cells/some-path-{cellname}

    ...so that the scope for `nix build` is explicitly defined in the cell
    class and not implicity defined by whatever happens to be lying around
    at the time.

    This function is used to keep the two places in sync.

    :return: True if the given paths represent the same file
    """
    a_stat = a.stat()
    b_stat = b.stat()
    return (a_stat.st_ino == b_stat.st_ino) and (a_stat.st_dev == b_stat.st_dev)


class Cell(ABC):
    "see docstring at the end of this module"

    config_path: Path
    cell_path: Path
    nix: Nix
    git: Git
    log: Logger
    home: Home

    def closure_inputs(self) -> list[str]:
        """
        A list of files, local to the cell, which are considered by whatever
        cell-provided automation runs in setup().

        :returns: A list of filenames which are expected to be in the same
                  directory as desmata.py, by default these are flake.nix and
                  flake.lock.
        """
        return ["flake.nix", "flake.lock"]

    def __init__(self, home: Home, git: Git, nix: Nix, log: Logger):
        self.nix = nix
        self.git = git
        self.log = log
        self.home = home

        # create a place for desmata to track the evolution of this cell
        file = getfile(self.__class__)
        self.project_path = Path(file).parent.resolve()
        self.cell_name = self.project_path.stem
        self.config_path = (
            home.data
            / "cells"
            / str(self.project_path.parent).replace("/", "_")
            / self.cell_name
        )

        # Make a git repo for only the closure inputs
        cell_git = tweaked(git, cwd=self.config_path)
        if not self.config_path.exists():
            git_init = True
        self.config_path.mkdir(exist_ok=True, parents=True)
        if git_init:
            cell_git("init")

        # dicts filename -> Path object
        proj_desired = {
            x: self.project_path / x
            for x in self.closure_inputs()
            if (self.project_path / x).exists()
        }
        config_actual = {x.name: x for x in self.config_path.glob("*")}

        # Process removals
        for key in set(config_actual) - set(proj_desired):
            if ".git" not in key:
                removed = config_actual[key]
                self.log.debug(f"removing {str(removed.resolve())}")
                removed.unlink()

        # Process additions
        for key in set(proj_desired) - set(config_actual):
            p = proj_desired[key]
            s = self.config_path / key
            self.log.debug(f"linking {str(s.resolve())}->{p.resolve()}")
            s.hardlink_to(p)

        # Fix mismatches
        config_actual = {x.name: x for x in self.config_path.glob("*")}
        for key in set(config_actual).intersection(proj_desired):
            p = proj_desired[key]
            s = self.config_path / key
            if not is_same_file(p, s):
                self.log.debug(f"relinking {str(s.resolve())}->{p.resolve()}")
                s.unlink()
                s.hardlink_to(p)

        # Update the config git dir.
        # 'nix build' (presumably part of the cell's setup() function) takes
        # the state of this git repo as a signal for whether it should rebuild.
        cell_git("add", "-A")
        cell_git("commit", "-m", datetime.now().isoformat())

        # todo: call get_closure and make it a parameter to setup

        # Let the cell build what it needs
        self.setup()

    @abstractmethod
    def setup(self):
        """
        Called by cell.__init__() so that the cell subclass can prepare itself
        for use.
        """
        raise NotImplementedError()

    def get_closure(self) -> Closure:
        # Currently, we're just letting the nix store cache this stuff
        # in a future version, we'll want to caputre the cell's Closure
        # so that we can gossip it with our peers.
        raise NotImplementedError("")


Cell.__doc__ = """
"""
