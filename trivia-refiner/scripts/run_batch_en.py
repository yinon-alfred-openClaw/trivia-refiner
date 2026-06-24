#!/usr/bin/env python3
"""Compatibility wrapper for the unified trivia refiner runner."""

from run_batch import main
import sys


if __name__ == "__main__":
    if "--lang" not in sys.argv:
        sys.argv.extend(["--lang", "en"])
    main()
