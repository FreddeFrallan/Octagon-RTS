#!/usr/bin/env python3
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import argparse
import json
import threading
import time
import urllib.error
import urllib.request

BOT_NAME = "Python Worker Bot"
BOT_HOST = "127.0.0.1"
BOT_PORT = 8787

session = None
session_lock = threading.Lock()
bot_thread = None
stop_event = threading.Event()


def read_json(handler):
  length = int(handler.headers.get("Content-Length", 0))
  if length == 0:
    return {}
  return json.loads(handler.rfile.read(length).decode("utf-8"))


def post_json(url, payload):
  data = json.dumps(payload).encode("utf-8")
  req = urllib.request.Request(
    url,
    data=data,
    headers={"Content-Type": "application/json"},
    method="POST"
  )
  with urllib.request.urlopen(req, timeout=2) as res:
    return json.loads(res.read().decode("utf-8"))


def get_json(url):
  with urllib.request.urlopen(url, timeout=2) as res:
    return json.loads(res.read().decode("utf-8"))


def action(action_name, args):
  with session_lock:
    current = dict(session) if session else None
  if not current:
    return

  return post_json(f"{current['gameServer']}/api/action", {
    "roomId": current["roomId"],
    "playerId": current["playerId"],
    "action": action_name,
    "args": args
  })


def own_units(state, unit_type=None):
  player_id = state["localPlayerId"]
  units = [
    unit for unit in state.get("units", {}).values()
    if unit["owner"] == player_id and not unit["isMoving"]
  ]
  if unit_type:
    units = [unit for unit in units if unit["type"] == unit_type]
  return units


def neighbors(x, z, grid_size=8, grid_height=None):
  if grid_height is None:
    grid_height = grid_size
  if z % 2 == 0:
    coords = [(x-1, z), (x+1, z), (x-1, z-1), (x, z-1), (x-1, z+1), (x, z+1)]
  else:
    coords = [(x-1, z), (x+1, z), (x, z-1), (x+1, z-1), (x, z+1), (x+1, z+1)]
  return [(nx, nz) for nx, nz in coords if 0 <= nx < grid_size and 0 <= nz < grid_height]


def pick_worker_move(state):
  workers = own_units(state, "worker")
  if not workers:
    return None

  grid = state["grid"]
  for worker in workers:
    for nx, nz in neighbors(worker["x"], worker["z"], state.get("gridWidth", state["gridSize"]), state.get("gridHeight", state["gridSize"])):
      cell = grid[nx][nz]
      if cell["type"] == "resource" and cell["gold"] > 0:
        return worker["id"], nx, nz

  worker = workers[0]
  for nx, nz in neighbors(worker["x"], worker["z"], state.get("gridWidth", state["gridSize"]), state.get("gridHeight", state["gridSize"])):
    if grid[nx][nz]["type"] not in ("base", "obstacle"):
      return worker["id"], nx, nz
  return None


def bot_loop():
  while not stop_event.is_set():
    with session_lock:
      current = dict(session) if session else None

    if not current:
      time.sleep(0.2)
      continue

    try:
      state = get_json(
        f"{current['gameServer']}/api/state?roomId={current['roomId']}&playerId={current['playerId']}&events=0"
      )
      state["localPlayerId"] = current["playerId"]

      player = state["players"][str(current["playerId"])]
      if player["crystals"] >= 50:
        action("build", {"unitType": "worker"})

      move = pick_worker_move(state)
      if move:
        unit_id, x, z = move
        action("move", {"unitIds": [unit_id], "toX": x, "toZ": z})
    except (urllib.error.URLError, TimeoutError, KeyError, json.JSONDecodeError):
      pass

    time.sleep(current.get("pollMs", 200) / 1000)


class BotHandler(BaseHTTPRequestHandler):
  def _send(self, status, payload):
    body = json.dumps(payload).encode("utf-8")
    self.send_response(status)
    self.send_header("Access-Control-Allow-Origin", "*")
    self.send_header("Access-Control-Allow-Methods", "POST, OPTIONS")
    self.send_header("Access-Control-Allow-Headers", "Content-Type")
    self.send_header("Content-Type", "application/json")
    self.send_header("Content-Length", str(len(body)))
    self.end_headers()
    self.wfile.write(body)

  def do_OPTIONS(self):
    self._send(200, {"ok": True})

  def do_POST(self):
    global session, bot_thread
    payload = read_json(self)

    if payload.get("protocol") != "octagon-rts-bot-v1":
      self._send(400, {"error": "Unsupported bot protocol"})
      return

    if self.path == "/handshake":
      self._send(200, {"ok": True, "name": BOT_NAME})
      return

    if self.path == "/session":
      with session_lock:
        session = {
          "gameServer": payload["gameServer"],
          "roomId": payload["roomId"],
          "playerId": payload["playerId"],
          "pollMs": payload.get("pollMs", 200)
        }
      stop_event.clear()
      if not bot_thread or not bot_thread.is_alive():
        bot_thread = threading.Thread(target=bot_loop, daemon=True)
        bot_thread.start()
      self._send(200, {"ok": True, "name": BOT_NAME})
      return

    if self.path == "/stop":
      with session_lock:
        session = None
      self._send(200, {"ok": True})
      return

    self._send(404, {"error": "Not found"})

  def log_message(self, fmt, *args):
    return


if __name__ == "__main__":
  parser = argparse.ArgumentParser(description="Run the Octagon-RTS example Python bot.")
  parser.add_argument("--host", default=BOT_HOST, help=f"Host/interface to bind. Default: {BOT_HOST}")
  parser.add_argument("--port", type=int, default=BOT_PORT, help=f"Port to bind. Default: {BOT_PORT}")
  parser.add_argument("--name", default=BOT_NAME, help=f"Bot name shown in the lobby. Default: {BOT_NAME}")
  args = parser.parse_args()

  BOT_NAME = args.name
  print(f"{BOT_NAME} listening on http://{args.host}:{args.port}")
  ThreadingHTTPServer((args.host, args.port), BotHandler).serve_forever()
