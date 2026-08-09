#!/usr/bin/env python3
"""Entry point that works from any directory: python3 run_jarvis.py ..."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from jarvis.cli import main  # noqa: E402

sys.exit(main())
