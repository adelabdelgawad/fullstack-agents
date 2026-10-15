#!/usr/bin/env python3
"""Manage the Markdown task list for this session."""
from pathlib import Path
import sys

if not Path(__file__).with_name("task_tracking.py").is_file():
    sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "plugins/fullstack-agents/scripts/lib"))
from task_tracking import main

if __name__ == "__main__":
    raise SystemExit(main())
