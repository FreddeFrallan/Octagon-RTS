#!/usr/bin/env python3
import argparse

from protocol import BotHttpServer
from strategy import StrategicBot


def main():
  parser = argparse.ArgumentParser(description="Run the Octagon-RTS strategic Python bot.")
  parser.add_argument("--host", default="127.0.0.1", help="Host/interface to bind. Default: 127.0.0.1")
  parser.add_argument("--port", type=int, default=8788, help="Port to bind. Default: 8788")
  parser.add_argument("--name", default="Python Strategic Bot", help="Bot name shown in the lobby.")
  parser.add_argument("--max-actions", type=int, default=6, help="Maximum orders to send per strategy tick. Default: 6")
  args = parser.parse_args()

  bot = StrategicBot(name=args.name, max_actions_per_tick=args.max_actions)
  print(f"{bot.name} listening on http://{args.host}:{args.port}")
  BotHttpServer(args.host, args.port, bot).serve_forever()


if __name__ == "__main__":
  main()
