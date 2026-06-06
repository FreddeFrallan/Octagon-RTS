#!/usr/bin/env python3
import argparse
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[4]
BACKEND = ROOT / "backend"
BOT_ROOT = Path(__file__).resolve().parents[1]

for path in (str(BACKEND), str(BOT_ROOT)):
  if path not in sys.path:
    sys.path.insert(0, path)

from offline_simulation.runner import run_offline_simulation
from strategy import create_offline_bot


def parse_args():
  parser = argparse.ArgumentParser(description="Run offensive bot self-play through backend offline simulation.")
  parser.add_argument("--ticks", type=int, default=10000, help="Maximum ticks to simulate. Default: 10000")
  return parser.parse_args()


def main():
  args = parse_args()
  result = run_offline_simulation(
    player_count=2,
    bot_factories=[create_offline_bot, create_offline_bot],
    max_ticks=args.ticks
  )

  print(f"time={result.elapsed_seconds:.3f}s")
  print(f"ticks={result.ticks}")
  print(f"winner={result.room.winner}")


if __name__ == "__main__":
  main()
