import json
import math
import threading
import time
import urllib.error
import urllib.request

UNIT_COSTS = {
  "worker": 50,
  "mech": 100,
  "artillery": 80
}

COMBAT_TYPES = {"mech", "artillery"}


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


def offset_to_cube(col, row):
  x = col - (row - (row & 1)) // 2
  z = row
  y = -x - z
  return x, y, z


def hex_distance(ax, az, bx, bz):
  acx, acy, acz = offset_to_cube(ax, az)
  bcx, bcy, bcz = offset_to_cube(bx, bz)
  return max(abs(acx - bcx), abs(acy - bcy), abs(acz - bcz))


def neighbors(x, z, grid_size=8):
  if z % 2 == 0:
    coords = [(x-1, z), (x+1, z), (x-1, z-1), (x, z-1), (x-1, z+1), (x, z+1)]
  else:
    coords = [(x-1, z), (x+1, z), (x, z-1), (x+1, z-1), (x, z+1), (x+1, z+1)]
  return [(nx, nz) for nx, nz in coords if 0 <= nx < grid_size and 0 <= nz < grid_size]


def unit_priority(unit):
  if unit["type"] == "worker":
    return 0
  if unit["type"] == "artillery":
    return 1
  if unit["type"] == "mech":
    return 2
  return 3


class StrategicBot:
  def __init__(self, name="Python Strategic Bot", max_actions_per_tick=6, verbose=True):
    self.name = name
    self.max_actions_per_tick = max_actions_per_tick
    self.verbose = verbose
    self.session = None
    self.session_lock = threading.Lock()
    self.thread = None
    self.stop_event = threading.Event()
    self.worker_spend = 0
    self.combat_spend = 0
    self.last_unit_orders = {}
    self.last_artillery_targets = {}
    self.combat_build_toggle = 0

  def start_session(self, payload):
    with self.session_lock:
      self.session = {
        "gameServer": payload["gameServer"],
        "roomId": payload["roomId"],
        "playerId": payload["playerId"],
        "pollMs": payload.get("pollMs", 200)
      }
      self.worker_spend = 0
      self.combat_spend = 0
      self.last_unit_orders = {}
      self.last_artillery_targets = {}

    self.stop_event.clear()
    if not self.thread or not self.thread.is_alive():
      self.thread = threading.Thread(target=self.loop, daemon=True)
      self.thread.start()

  def stop_session(self):
    with self.session_lock:
      self.session = None
    self.stop_event.set()

  def current_session(self):
    with self.session_lock:
      return dict(self.session) if self.session else None

  def loop(self):
    while not self.stop_event.is_set():
      current = self.current_session()
      if not current:
        time.sleep(0.2)
        continue

      try:
        state = self.fetch_state(current)
        self.play_tick(current, state)
      except (urllib.error.URLError, TimeoutError, KeyError, json.JSONDecodeError) as e:
        self.log(f"tick skipped: {type(e).__name__}: {e}")

      time.sleep(current.get("pollMs", 200) / 1000)

  def fetch_state(self, current):
    return get_json(
      f"{current['gameServer']}/api/state"
      f"?roomId={current['roomId']}&playerId={current['playerId']}&events=0"
    )

  def action(self, current, action_name, args):
    try:
      result = post_json(f"{current['gameServer']}/api/action", {
        "roomId": current["roomId"],
        "playerId": current["playerId"],
        "action": action_name,
        "args": args
      })
      success = result.get("success", False)
      if success:
        self.log(f"{action_name} {args}")
      return success
    except urllib.error.HTTPError as e:
      message = e.reason
      try:
        payload = json.loads(e.read().decode("utf-8"))
        message = payload.get("error", message)
      except (json.JSONDecodeError, UnicodeDecodeError):
        pass
      self.log(f"{action_name} rejected: {message}")
      return False

  def play_tick(self, current, state):
    if state.get("status") != "playing":
      return
    state["localPlayerId"] = current["playerId"]

    actions_sent = 0
    if self.try_build(current, state):
      actions_sent += 1

    economy_orders = self.plan_worker_orders(current, state)
    combat_orders = self.plan_combat_orders(current, state)

    for order in self.interleave_orders(economy_orders, combat_orders):
      if actions_sent >= self.max_actions_per_tick:
        break
      if self.send_order(current, order):
        actions_sent += 1

  def interleave_orders(self, economy_orders, combat_orders):
    max_len = max(len(economy_orders), len(combat_orders))
    for idx in range(max_len):
      if idx < len(economy_orders):
        yield economy_orders[idx]
      if idx < len(combat_orders):
        yield combat_orders[idx]

  def send_order(self, current, order):
    if order["action"] == "move":
      unit_id = order["args"]["unitIds"][0]
      to_x = order["args"]["toX"]
      to_z = order["args"]["toZ"]
      key = (to_x, to_z)
      last_key, last_time = self.last_unit_orders.get(unit_id, (None, 0))
      if last_key == key and time.time() - last_time < 0.8:
        return False
      if self.action(current, "move", order["args"]):
        self.last_unit_orders[unit_id] = (key, time.time())
        return True
      return False

    if order["action"] == "attack":
      unit_id = order["args"]["unitIds"][0]
      target = (order["args"]["toX"], order["args"]["toZ"])
      if self.last_artillery_targets.get(unit_id) == target:
        return False
      if self.action(current, "attack", order["args"]):
        self.last_artillery_targets[unit_id] = target
        return True
      return False

    return self.action(current, order["action"], order["args"])

  def try_build(self, current, state):
    player = state["players"][str(current["playerId"])]
    crystals = player["crystals"]
    if player["baseHp"] <= 0:
      return False

    unit_type = self.choose_build(state, crystals)
    if not unit_type:
      return False

    if self.action(current, "build", {"unitType": unit_type}):
      if unit_type == "worker":
        self.worker_spend += UNIT_COSTS[unit_type]
      else:
        self.combat_spend += UNIT_COSTS[unit_type]
      return True
    return False

  def choose_build(self, state, crystals):
    if crystals < min(UNIT_COSTS.values()):
      return None

    total_spend = self.worker_spend + self.combat_spend
    worker_ratio = self.worker_spend / total_spend if total_spend else 0

    if worker_ratio < 0.5 and crystals >= UNIT_COSTS["worker"]:
      return "worker"

    combat_choice = self.choose_combat_build(state, crystals)
    if combat_choice:
      return combat_choice

    if crystals >= UNIT_COSTS["worker"] and worker_ratio < 0.6:
      return "worker"
    return None

  def choose_combat_build(self, state, crystals):
    own = self.own_units(state)
    mech_count = sum(1 for unit in own if unit["type"] == "mech")
    artillery_count = sum(1 for unit in own if unit["type"] == "artillery")

    if artillery_count < max(1, math.ceil(mech_count / 2)) and crystals >= UNIT_COSTS["artillery"]:
      return "artillery"

    if self.combat_build_toggle % 3 == 2 and crystals >= UNIT_COSTS["artillery"]:
      self.combat_build_toggle += 1
      return "artillery"

    if crystals >= UNIT_COSTS["mech"]:
      self.combat_build_toggle += 1
      return "mech"

    if crystals >= UNIT_COSTS["artillery"]:
      return "artillery"
    return None

  def own_units(self, state, unit_type=None, stationary=False):
    units = [
      unit for unit in state.get("units", {}).values()
      if unit["owner"] == state["localPlayerId"]
    ]
    if unit_type:
      units = [unit for unit in units if unit["type"] == unit_type]
    if stationary:
      units = [unit for unit in units if not unit["isMoving"]]
    return units

  def enemy_units(self, state, unit_type=None, stationary=False):
    units = [
      unit for unit in state.get("units", {}).values()
      if unit["owner"] != state["localPlayerId"]
    ]
    if unit_type:
      units = [unit for unit in units if unit["type"] == unit_type]
    if stationary:
      units = [unit for unit in units if not unit["isMoving"]]
    return units

  def plan_worker_orders(self, current, state):
    workers = self.own_units(state, "worker", stationary=True)
    enemies = self.enemy_units(state)
    resources = self.resource_cells(state)
    orders = []

    for worker in workers:
      target = self.choose_resource_target(worker, state, resources, enemies)
      move = self.choose_worker_step(worker, state, target, enemies)
      if move:
        orders.append(self.move_order(worker["id"], move[0], move[1]))

    return orders

  def choose_resource_target(self, worker, state, resources, enemies):
    if not resources:
      return None

    def score(cell):
      distance = hex_distance(worker["x"], worker["z"], cell["x"], cell["z"])
      danger = max(0, 4 - self.nearest_enemy_distance(cell["x"], cell["z"], enemies))
      richness = cell["gold"] / max(1, cell["maxGold"])
      return distance + danger * 2 - richness

    return min(resources, key=score)

  def choose_worker_step(self, worker, state, target, enemies):
    grid = state["grid"]
    current_cell = grid[worker["x"]][worker["z"]]
    current_enemy_distance = self.nearest_enemy_distance(worker["x"], worker["z"], enemies)

    if current_cell["type"] == "resource" and current_cell["gold"] > 0 and current_enemy_distance > 2:
      return None

    candidates = self.passable_neighbors(state, worker["x"], worker["z"])
    if not candidates:
      return None

    current_resource_distance = hex_distance(worker["x"], worker["z"], target["x"], target["z"]) if target else 0

    def score(coord):
      x, z = coord
      enemy_distance = self.nearest_enemy_distance(x, z, enemies)
      resource_distance = hex_distance(x, z, target["x"], target["z"]) if target else 0
      progress = current_resource_distance - resource_distance
      resource_bonus = 3 if grid[x][z]["type"] == "resource" and grid[x][z]["gold"] > 0 else 0
      danger_penalty = max(0, 4 - enemy_distance) * 3
      safety_bonus = min(enemy_distance, 6) * 0.3
      return progress * 5 - resource_distance + resource_bonus + safety_bonus - danger_penalty

    best = max(candidates, key=score)
    best_resource_distance = hex_distance(best[0], best[1], target["x"], target["z"]) if target else 0
    if current_enemy_distance <= 2 or not target or best_resource_distance <= current_resource_distance:
      return best
    return None

  def plan_combat_orders(self, current, state):
    enemies = self.enemy_units(state)
    if not enemies and not self.enemy_base_position(current):
      return []

    orders = []
    for artillery in self.own_units(state, "artillery", stationary=True):
      order = self.plan_artillery_order(current, state, artillery, enemies)
      if order:
        orders.append(order)

    for mech in self.own_units(state, "mech", stationary=True):
      order = self.plan_mech_order(current, state, mech, enemies)
      if order:
        orders.append(order)

    return orders

  def plan_artillery_order(self, current, state, artillery, enemies):
    target = self.best_unit_target(artillery, enemies)
    base_target = self.enemy_base_position(current)

    in_range_targets = [
      enemy for enemy in enemies
      if 1 <= hex_distance(artillery["x"], artillery["z"], enemy["x"], enemy["z"]) <= 2
    ]
    if in_range_targets:
      target = self.best_unit_target(artillery, in_range_targets)
      return self.attack_order(artillery["id"], target["x"], target["z"])

    if base_target:
      base_distance = hex_distance(artillery["x"], artillery["z"], base_target[0], base_target[1])
      if 1 <= base_distance <= 2:
        return self.attack_order(artillery["id"], base_target[0], base_target[1])

    pursuit_target = target or ({"x": base_target[0], "z": base_target[1]} if base_target else None)
    if pursuit_target:
      step = self.step_towards(state, artillery, pursuit_target["x"], pursuit_target["z"], keep_distance=2)
      if step:
        return self.move_order(artillery["id"], step[0], step[1])
    return None

  def plan_mech_order(self, current, state, mech, enemies):
    target = self.best_unit_target(mech, enemies)
    if target:
      step = self.step_towards(state, mech, target["x"], target["z"], keep_distance=0)
      if step:
        return self.move_order(mech["id"], step[0], step[1])

    base_target = self.enemy_base_position(current)
    if base_target:
      step = self.step_towards(state, mech, base_target[0], base_target[1], keep_distance=1)
      if step:
        return self.move_order(mech["id"], step[0], step[1])
    return None

  def best_unit_target(self, unit, enemies):
    if not enemies:
      return None
    return min(
      enemies,
      key=lambda enemy: (
        unit_priority(enemy),
        hex_distance(unit["x"], unit["z"], enemy["x"], enemy["z"]),
        enemy["hp"]
      )
    )

  def step_towards(self, state, unit, target_x, target_z, keep_distance=0):
    current_distance = hex_distance(unit["x"], unit["z"], target_x, target_z)
    candidates = self.passable_neighbors(state, unit["x"], unit["z"])
    if not candidates:
      return None

    def score(coord):
      x, z = coord
      distance = hex_distance(x, z, target_x, target_z)
      if keep_distance and distance < keep_distance:
        return -100
      return -abs(distance - keep_distance) if current_distance <= keep_distance else -distance

    best = max(candidates, key=score)
    best_distance = hex_distance(best[0], best[1], target_x, target_z)
    if keep_distance:
      if current_distance == keep_distance:
        return None
      if abs(best_distance - keep_distance) < abs(current_distance - keep_distance):
        return best
      return None

    if best_distance < current_distance or best_distance == 0:
      return best
    return None

  def resource_cells(self, state):
    cells = []
    for row in state["grid"]:
      for cell in row:
        if cell["type"] == "resource" and cell["gold"] > 0:
          cells.append(cell)
    return cells

  def passable_neighbors(self, state, x, z):
    grid = state["grid"]
    return [
      (nx, nz) for nx, nz in neighbors(x, z, state["gridSize"])
      if grid[nx][nz]["type"] not in ("base", "obstacle")
    ]

  def nearest_enemy_distance(self, x, z, enemies):
    if not enemies:
      return 99
    return min(hex_distance(x, z, enemy["x"], enemy["z"]) for enemy in enemies)

  def enemy_base_position(self, current):
    return (7, 7) if current["playerId"] == 1 else (0, 0)

  def move_order(self, unit_id, x, z):
    return {
      "action": "move",
      "args": {"unitIds": [unit_id], "toX": x, "toZ": z}
    }

  def attack_order(self, unit_id, x, z):
    return {
      "action": "attack",
      "args": {"unitIds": [unit_id], "toX": x, "toZ": z}
    }

  def log(self, message):
    if self.verbose:
      print(f"[{self.name}] {message}", flush=True)
