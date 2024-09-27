{ lib
, buildPythonPackage
, fetchPypi
, setuptools
, wheel
, pkgs ? import <nixpkgs> {}
}:

buildPythonPackage rec {
  pname = "fmpsdk";
  version = "20240330.0";

  src = fetchPypi {
    inherit pname version;
    hash = "sha256-KemOoGz8Zsb0TxKHRBltVYDBW0af1fvCjfA7RMQ1/oo=";
  };

  # do not run tests
  doCheck = false;

  buildInputs = [
    pkgs.python311Packages.python-dotenv
    pkgs.python311Packages.poetry-core
    pkgs.python311Packages.requests
  ];

  propogatedBuildInputs = [
    pkgs.python311Packages.python-dotenv
    pkgs.python311Packages.poetry-core
    pkgs.python311Packages.requests
  ];

  # specific to buildPythonPackage, see its reference
  pyproject = true;
  build-system = [
    setuptools
    wheel
  ];
}

