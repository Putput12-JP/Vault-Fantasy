"""Run one SmartStake recorder pass under a shared lock, so the NBA and NFL launchd jobs never overlap.

  python3 smartstake_run_locked.py nba|nfl

The API allows about 10 snapshot pages a minute across the key, so two passes at once would just throttle each other.
A job that fires while the other is mid-pass waits its turn here instead of being skipped.
"""
import fcntl
import os
import subprocess
import sys
from pathlib import Path

lg = sys.argv[1]
here = Path(__file__).resolve().parent
lock = open(Path.home() / ".config" / "smartstake" / "run.lock", "w")
fcntl.flock(lock, fcntl.LOCK_EX)
sys.exit(subprocess.call([sys.executable, str(here / "smartstake_record.py"), "--league", lg, "--once"], cwd=str(here.parent)))
