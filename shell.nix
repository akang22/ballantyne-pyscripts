let
  pkgs = import <nixpkgs> {};
  python = pkgs.python3.override {
    self = python;
    packageOverrides = pyfinal: pyprev: {
     finnhub-python = pyfinal.callPackage ./finnhub-python.nix { };
    };
  };
in pkgs.mkShell {
  packages = [
    (python.withPackages (python-pkgs: [
      python-pkgs.pandas
      python-pkgs.plotly
      python-pkgs.requests
      python-pkgs.streamlit
      python-pkgs.yfinance
      python-pkgs.numpy
      python-pkgs.finnhub-python
      python-pkgs.unidecode
    ]))
  ];
}
