from desmata.config import Home, AppContext
from logging import getLogger
from .samples.greeter.desmata import Greeter, GreeterDeps
from pytest import fixture
from pathlib import Path


@fixture(scope="function")
def ac(tmp_path) -> AppContext:
    return AppContext(home=Home.sandbox(tmp_path), log=getLogger(Path(__file__).name))


def test_install(ac):
    closure = GreeterDeps(ac.log)
    cell = Greeter(closure, ac.log)
    print(cell.greet())
