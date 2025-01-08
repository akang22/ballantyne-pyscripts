{ lib
, buildPythonPackage
, fetchPypi
, rustPlatform
, setuptools
, wheel
, pkgs ? import <nixpkgs> {}
}:

buildPythonPackage rec {
  pname = "pyxirr";
  version = "0.10.5";
  # format = "wheel";

  src = fetchPypi {
    inherit pname version;
    hash = "sha256-rUJlUecwz1jmraNXcoVS2eNnmp0mOBTg5SoVtPuiuAI=";
    # platform = "manylinux1_x86_64";
  };

  # do not run tests
  doCheck = false;

  cargoDeps = rustPlatform.fetchCargoTarball {
    inherit pname version src;
    hash = "sha256-q9ZBhSy0TFyFUacOudLAp0ZtipMX1TDY73DWiwfNC0U=";
  };

  nativeBuildInputs = with rustPlatform; [ cargoSetupHook maturinBuildHook ];

  buildInputs = [
  ];

  propogatedBuildInputs = [
  ];

  # specific to buildPythonPackage, see its reference
  pyproject = true;
  build-system = [
    setuptools
    wheel
  ];
}

