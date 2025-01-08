let
  pkgs = import <nixpkgs> {};
  python = pkgs.python3.override {
    self = python;
    packageOverrides = pyfinal: pyprev: {
     finnhub-python = pyfinal.callPackage ./finnhub-python.nix { };
     fmpsdk = pyfinal.callPackage ./fmpsdk.nix { };
     pyxirr = pyfinal.callPackage ./pyxirr.nix { };
    };
  };
in pkgs.mkShell {
  packages = [
    (python.withPackages (python-pkgs: [
      python-pkgs.black
      python-pkgs.pandas
      python-pkgs.plotly
      python-pkgs.requests
      python-pkgs.streamlit
      python-pkgs.pyxirr
      python-pkgs.yfinance
      python-pkgs.numpy
      python-pkgs.finnhub-python
      python-pkgs.unidecode
      python-pkgs.requests-cache
    ]))
  ];
}
