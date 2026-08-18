#!/usr/bin/env python3
"""First job on a live Ray cluster. No extra Python packages."""

from __future__ import annotations

import os
import socket


def main() -> None:
    print("hello from ray")
    print(f"host={socket.gethostname()}")
    print(f"cwd={os.getcwd()}")


if __name__ == "__main__":
    main()
