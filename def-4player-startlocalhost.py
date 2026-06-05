#!/usr/bin/env python3
import argparse
import os
import signal
import subprocess
import sys
import time
from pathlib import Path


ROOT = Path(__file__).resolve().parent


def port(value):
  try:
    parsed = int(value)
  except ValueError as exc:
    raise argparse.ArgumentTypeError("port must be a number") from exc

  if parsed < 1 or parsed > 65535:
    raise argparse.ArgumentTypeError("port must be between 1 and 65535")
  if parsed < 1024:
    raise argparse.ArgumentTypeError("port must be 1024 or higher for local development")

  return parsed


def start_process(command, env=None):
  return subprocess.Popen(command, cwd=ROOT, env=env)


def stop_process(process):
  if process.poll() is not None:
    return

  process.terminate()
  try:
    process.wait(timeout=5)
  except subprocess.TimeoutExpired:
    process.kill()
    process.wait()


def main():
  parser = argparse.ArgumentParser(
    description="Start Octagon-RTS locally with four strategic bots."
  )
  parser.add_argument("app_port", type=port, help="Port for the main application server.")
  parser.add_argument("bot_one_port", type=port, help="Port for the first strategy bot.")
  parser.add_argument("bot_two_port", type=port, help="Port for the second strategy bot.")
  parser.add_argument("bot_three_port", type=port, help="Port for the third strategy bot.")
  parser.add_argument("bot_four_port", type=port, help="Port for the fourth strategy bot.")
  args = parser.parse_args()

  bot_ports = [
    args.bot_one_port,
    args.bot_two_port,
    args.bot_three_port,
    args.bot_four_port
  ]
  ports = [args.app_port, *bot_ports]
  if len(set(ports)) != len(ports):
    parser.error("app_port and all bot ports must be unique")

  bot_command = [
    sys.executable,
    str(ROOT / "bots" / "python" / "strategic_bot" / "run_bot.py"),
    "--host",
    "127.0.0.1",
  ]
  bots = [
    start_process(
      bot_command + ["--port", str(bot_port), "--name", f"Python Strategic Bot {index}"]
    )
    for index, bot_port in enumerate(bot_ports, start=1)
  ]

  server_env = os.environ.copy()
  server_env.setdefault("HOST", "127.0.0.1")
  server_env["PORT"] = str(args.app_port)
  server = None

  def shutdown(signum=None, frame=None):
    if server is not None and server.poll() is None:
      server.terminate()
    for bot in bots:
      stop_process(bot)

  signal.signal(signal.SIGINT, shutdown)
  signal.signal(signal.SIGTERM, shutdown)

  try:
    for index, bot_port in enumerate(bot_ports, start=1):
      print(f"Started strategy bot {index} at http://localhost:{bot_port}")

    time.sleep(0.3)
    for index, bot in enumerate(bots, start=1):
      exit_code = bot.poll()
      if exit_code is not None:
        print(f"Strategy bot {index} exited early with code {exit_code}", file=sys.stderr)
        return exit_code

    print(f"Starting Octagon-RTS at http://localhost:{args.app_port}")
    server = start_process([sys.executable, str(ROOT / "backend" / "server.py")], env=server_env)
    return server.wait()
  finally:
    shutdown()


if __name__ == "__main__":
  raise SystemExit(main())
