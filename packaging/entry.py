"""PyInstaller entry point for the frozen `opengeneral` binary.

Kept tiny on purpose: it only wires multiprocessing for frozen builds and hands
off to the normal CLI. `sys.frozen` is set by PyInstaller, which the service
layer uses to choose `<binary> daemon run` over `<python> -m opengeneral.daemon`.
"""

from __future__ import annotations

import multiprocessing

from opengeneral.cli import main

if __name__ == "__main__":
    multiprocessing.freeze_support()
    main()
