{
  inputs = {
    flake-utils.url = "github:numtide/flake-utils";
    nixpkgs.url = "github:nixos/nixpkgs?ref=23.11";
    poetry2nix = {
      url = "github:nix-community/poetry2nix";
      inputs.nixpkgs.follows = "nixpkgs";
    };
    pre-commit-hooks.url = "github:cachix/pre-commit-hooks.nix";
  };

  outputs = { self, nixpkgs, flake-utils, poetry2nix, pre-commit-hooks }:
    flake-utils.lib.eachDefaultSystem (system:
      let
        inherit (poetry2nix.lib.mkPoetry2Nix { inherit pkgs; })
          mkPoetryApplication;
        pkgs = import nixpkgs { inherit system; };

        desmata-poetry = mkPoetryApplication { projectDir = ./.; };
      in
      {

        checks = {
          pre-commit-check = pre-commit-hooks.lib.${system}.run {
            src = ./.;
            hooks = {
              nixpkgs-fmt.enable = true;
              ruff.enable = true;
              gen-docs = {
                enable = true;
                name = "Generate Docs";
                entry = "nix run .#desmata -- docs generate";
                files = "src/desmata/.*$";
                language = "system";
                pass_filenames = false;
              };
            };
          };
        };

        apps = rec {
          desmata = {
            type = "app";
            program = "${desmata-poetry}/bin/desmata";
          };

          dsm = {
            type = "app";
            program = "${desmata-poetry}/bin/desmata";
          };

          default = desmata;
        };

        packages = rec {
          desmata = desmata-poetry;
          default = desmata;
        };

        devShells.default = pkgs.mkShell {
          inputsFrom = [ desmata-poetry ];
          packages = [
            pkgs.just
            pkgs.poetry
            pkgs.python311Packages.pylsp-mypy
          ];
          inherit (self.checks.${system}.pre-commit-check) shellHook;

        };
      });
}
