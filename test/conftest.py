from pytest import fixture
from logging import Logger
from desmata.cli.common import cli_logger

@fixture
def test_logger() -> Logger:
    return cli_logger(verbose=True)
    
