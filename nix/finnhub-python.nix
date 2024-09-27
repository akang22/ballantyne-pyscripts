{ lib
, buildPythonPackage
, fetchPypi
, setuptools
, wheel
, pkgs ? import <nixpkgs> {}
}:

buildPythonPackage rec {
  pname = "finnhub-python";
  version = "2.4.20";

  src = fetchPypi {
    inherit pname version;
    hash = "sha256-sgf6k2CA1Im1BFyq4uYCujTQ4mMTMQ/z2NUFlC8ku84=";
  };

  # do not run tests
  doCheck = false;

  buildInputs = [
    pkgs.python311Packages.requests
  ];

  propogatedBuildInputs = [
    pkgs.python311Packages.requests
  ];

  # specific to buildPythonPackage, see its reference
  pyproject = true;
  build-system = [
    setuptools
    wheel
  ];
}

