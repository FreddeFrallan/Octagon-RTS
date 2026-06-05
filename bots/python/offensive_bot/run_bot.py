#!/usr/bin/env python3
import argparse

from protocol import BotHttpServer
from strategy import OffensiveBot


def non_negative_int(value):
  try:
    parsed = int(value)
  except ValueError as exc:
    raise argparse.ArgumentTypeError("value must be a whole number") from exc

  if parsed < 0:
    raise argparse.ArgumentTypeError("value must be zero or higher")

  return parsed


def main():
  parser = argparse.ArgumentParser(description="Run the Octagon-RTS offensive Python bot.")
  parser.add_argument("--host", default="127.0.0.1", help="Host/interface to bind. Default: 127.0.0.1")
  parser.add_argument("--port", type=int, default=8789, help="Port to bind. Default: 8789")
  parser.add_argument("--name", default="Python Offensive Bot", help="Bot name shown in the lobby.")
  parser.add_argument("--max-actions", type=int, default=8, help="Maximum orders to send per strategy tick. Default: 8")
  parser.add_argument("--min-workers", type=non_negative_int, default=1, help="Minimum workers to keep before pure attack spending. Default: 1")
  parser.add_argument("--max-workers", type=non_negative_int, default=5, help="Maximum workers to build. Default: 5")
  parser.add_argument("--quiet", action="store_true", help="Suppress strategy action logs.")
  args = parser.parse_args()
  if args.max_workers < args.min_workers:
    parser.error("--max-workers must be greater than or equal to --min-workers")

  bot = OffensiveBot(
    name=args.name,
    max_actions_per_tick=args.max_actions,
    verbose=not args.quiet,
    min_workers=args.min_workers,
    max_workers=args.max_workers
  )
  print(f"{bot.name} listening on http://{args.host}:{args.port} (workers {args.min_workers}-{args.max_workers}, then attack)")
  BotHttpServer(args.host, args.port, bot).serve_forever()


if __name__ == "__main__":
  main()
