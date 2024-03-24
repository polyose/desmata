from logging import Logger

from desmata.interface import Cell, Closure, ClosureItem
from desmata.nix import Nix
from desmata.tool import Tool


class GreeterDeps(Closure):

    hello: ClosureItem
    cowsay: ClosureItem

    def __init__(self, log: Logger):
        nix = Nix(log)
        self.hello = ClosureItem.from_nix_store(nix.build("hello", "/bin/hello"))
        self.cowsay = ClosureItem.from_nix_store(nix.build("cowsay", "/bin/cowsay"))
        super().enclose(self.hello)


class Hello(Tool):

    def __init__(self, closure: GreeterDeps, log: Logger):
        super().__init__(name="hello", path=closure.hello.path, log=log)

    def world(self) -> str:
        return self("World!")

class Cowsay(Tool):
    
    def __init__(self, closure: GreeterDeps, log: Logger):
        super().__init__(name="cowsay", path=closure.cowsay.path, log=log)

    def stegosaurus(self, message: str) -> str:
        return self("-f", "stegosaurus", message)
        

class Greeter(Cell):

    hello: Hello
    cowsay: Cowsay

    def __init__(self, closure: GreeterDeps, log: Logger):
        self.hello = Hello(closure, log)
        self.cowsay = Cowsay(closure, log)

    def greet(self) -> None:
        return self.cowsay(self.hello.world())
