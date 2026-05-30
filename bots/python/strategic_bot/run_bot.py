#!/usr/bin/env python3
import argparse

from protocol import BotHttpServer
from strategy import StrategicBot


def allocation_ratio(value):
  try:
    ratio = float(value)
  except ValueError as exc:
    raise argparse.ArgumentTypeError("allocation must be a number") from exc

  if ratio > 1:
    ratio = ratio / 100

  if ratio < 0 or ratio > 1:
    raise argparse.ArgumentTypeError("allocation must be between 0 and 1, or 0 and 100 percent")

  return ratio


def main():
  parser = argparse.ArgumentParser(description="Run the Octagon-RTS strategic Python bot.")
  parser.add_argument("--host", default="127.0.0.1", help="Host/interface to bind. Default: 127.0.0.1")
  parser.add_argument("--port", type=int, default=8788, help="Port to bind. Default: 8788")
  parser.add_argument("--name", default="Python Strategic Bot", help="Bot name shown in the lobby.")
  parser.add_argument("--max-actions", type=int, default=6, help="Maximum orders to send per strategy tick. Default: 6")
  parser.add_argument(
    "--worker-allocation",
    type=allocation_ratio,
    default=0.5,
    help="Share of build spending reserved for workers. Use 0.5 or 50 for the default 50/50 worker/attack split."
  )
  parser.add_argument("--quiet", action="store_true", help="Suppress strategy action logs.")
  args = parser.parse_args()

  bot = StrategicBot(
    name=args.name,
    max_actions_per_tick=args.max_actions,
    verbose=not args.quiet,
    worker_allocation=args.worker_allocation
  )
  attack_allocation = 1 - args.worker_allocation
  print(
    f"{bot.name} listening on http://{args.host}:{args.port} "
    f"(workers {args.worker_allocation:.0%} / attack {attack_allocation:.0%})"
  )
  BotHttpServer(args.host, args.port, bot).serve_forever()


if __name__ == "__main__":
  main()
