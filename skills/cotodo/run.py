#!/usr/bin/env python3
"""Entry point for non-pip installs (npx skills / curl / manual)."""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from cotodo.cli import main

main()
