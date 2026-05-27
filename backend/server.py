# server.py
# Entry point for the Octagon-RTS authoritative multiplayer server.

import os
import threading

from api.handler import GameRequestHandler
from net import create_server, get_local_ip
from simulation.loop import game_loop_thread


def main():
  host = os.environ.get("HOST", "0.0.0.0")
  port = int(os.environ.get("PORT", "8000"))
  local_ip = get_local_ip()

  logic_thread = threading.Thread(target=game_loop_thread, daemon=True)
  logic_thread.start()

  print("="*60)
  print("OCTO-COMMAND Authoritative Multiplayer Game Server starting...")
  print(f"Server is running locally at: http://localhost:{port}")
  if host in ("0.0.0.0", "::"):
    print(f"Local Network IP: http://{local_ip}:{port}")
    print("Ask your friend on the same network to join using the network IP!")
  else:
    print(f"Bound to: {host}:{port}")
  print("="*60)

  server = create_server(host, port, GameRequestHandler)
  try:
    server.serve_forever()
  except KeyboardInterrupt:
    print("\nServer shutting down.")
    server.server_close()


if __name__ == '__main__':
  main()
