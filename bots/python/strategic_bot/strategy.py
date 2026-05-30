import json
import math
import threading
import time
import urllib.error
import urllib.request
from collections import deque

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


def neighbors(x, z, grid_size=8, grid_height=None):
  if grid_height is None:
    grid_height = grid_size
  if z % 2 == 0:
    coords = [(x-1, z), (x+1, z), (x-1, z-1), (x, z-1), (x-1, z+1), (x, z+1)]
  else:
    coords = [(x-1, z), (x+1, z), (x, z-1), (x+1, z-1), (x, z+1), (x+1, z+1)]
  return [(nx, nz) for nx, nz in coords if 0 <= nx < grid_size and 0 <= nz < grid_height]


def unit_priority(unit):
  if unit["type"] == "worker":
    return 0
  if unit["type"] == "artillery":
    return 1
  if unit["type"] == "mech":
    return 2
  return 3


class StrategicBot:
  def __init__(self, name="Python Strategic Bot", max_actions_per_tick=6, verbose=True, worker_allocation=0.5):
    self.name = name
    self.max_actions_per_tick = max_actions_per_tick
    self.verbose = verbose
    self.worker_allocation = max(0.0, min(worker_allocation, 1.0))
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

    if worker_ratio < self.worker_allocation and crystals >= UNIT_COSTS["worker"]:
      return "worker"

    combat_choice = self.choose_combat_build(state, crystals)
    if combat_choice:
      return combat_choice

    if crystals >= UNIT_COSTS["worker"] and worker_ratio < min(self.worker_allocation + 0.1, 1.0):
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
      current_enemy_distance = self.nearest_enemy_distance(worker["x"], worker["z"], enemies)
      if current_enemy_distance > 2 and any(hex_distance(worker["x"], worker["z"], resource["x"], resource["z"]) == 1 for resource in resources):
        continue

      for target in self.choose_resource_targets(worker, state, resources, enemies):
        move = self.choose_worker_step(worker, state, target, enemies)
        if move:
          orders.append(self.move_order(worker["id"], move[0], move[1]))
          break

    return orders

  def choose_resource_targets(self, worker, state, resources, enemies):
    if not resources:
      return []

    def score(cell):
      distance = hex_distance(worker["x"], worker["z"], cell["x"], cell["z"])
      danger = max(0, 4 - self.nearest_enemy_distance(cell["x"], cell["z"], enemies))
      richness = cell["gold"] / max(1, cell["maxGold"])
      return distance + danger * 2 - richness

    return sorted(resources, key=score)

  def choose_worker_step(self, worker, state, target, enemies):
    current_enemy_distance = self.nearest_enemy_distance(worker["x"], worker["z"], enemies)

    if target and hex_distance(worker["x"], worker["z"], target["x"], target["z"]) == 1 and current_enemy_distance > 2:
      return None

    if target:
      return self.step_towards_any(state, worker, self.adjacent_passable_cells(state, target["x"], target["z"]))

    return self.safest_passable_neighbor(state, worker, enemies)

  def plan_combat_orders(self, current, state):
    enemies = self.enemy_units(state)
    base_target = self.enemy_base_target(current, state)
    if not enemies and not base_target:
      return []

    orders = []
    for artillery in self.own_units(state, "artillery", stationary=True):
      order = self.plan_artillery_order(current, state, artillery, enemies, base_target)
      if order:
        orders.append(order)

    for mech in self.own_units(state, "mech", stationary=True):
      order = self.plan_mech_order(current, state, mech, enemies, base_target)
      if order:
        orders.append(order)

    return orders

  def plan_artillery_order(self, current, state, artillery, enemies, base_target):
    in_range_targets = [
      enemy for enemy in enemies
      if 1 <= hex_distance(artillery["x"], artillery["z"], enemy["x"], enemy["z"]) <= 2
    ]
    if base_target and 1 <= hex_distance(artillery["x"], artillery["z"], base_target["x"], base_target["z"]) <= 2:
      in_range_targets.append(base_target)

    if in_range_targets:
      target = self.closest_target(artillery, in_range_targets)
      return self.attack_order(artillery["id"], target["x"], target["z"])

    pursuit_target = self.closest_target(artillery, enemies + ([base_target] if base_target else []))
    if pursuit_target:
      step = self.step_to_standoff(state, artillery, pursuit_target["x"], pursuit_target["z"], min_range=1, max_range=2)
      if step:
        return self.move_order(artillery["id"], step[0], step[1])
    return None

  def plan_mech_order(self, current, state, mech, enemies, base_target):
    target = self.closest_target(mech, enemies + ([base_target] if base_target else []))
    if target:
      keep_distance = 1 if target.get("type") == "base" else 0
      step = self.step_towards(state, mech, target["x"], target["z"], keep_distance=keep_distance)
      if step:
        return self.move_order(mech["id"], step[0], step[1])

    return None

  def closest_target(self, unit, targets):
    if not targets:
      return None
    return min(
      targets,
      key=lambda target: (
        hex_distance(unit["x"], unit["z"], target["x"], target["z"]),
        3 if target.get("type") == "base" else unit_priority(target),
        target.get("hp", 999)
      )
    )

  def step_towards(self, state, unit, target_x, target_z, keep_distance=0):
    if keep_distance:
      return self.step_to_standoff(state, unit, target_x, target_z, keep_distance, keep_distance)

    return self.step_towards_any(state, unit, {(target_x, target_z)})

  def step_to_standoff(self, state, unit, target_x, target_z, min_range, max_range):
    current_distance = hex_distance(unit["x"], unit["z"], target_x, target_z)
    if min_range <= current_distance <= max_range:
      return None

    goals = {
      (x, z)
      for x, z in self.all_passable_cells(state)
      if min_range <= hex_distance(x, z, target_x, target_z) <= max_range
    }
    return self.step_towards_any(state, unit, goals)

  def step_towards_any(self, state, unit, goals):
    if not goals:
      return None

    start = (unit["x"], unit["z"])
    if start in goals:
      return None

    visited = {start}
    queue = deque()
    for nx, nz in self.passable_neighbors(state, start[0], start[1]):
      first_step = (nx, nz)
      if first_step in goals:
        return first_step
      visited.add(first_step)
      queue.append((first_step, first_step))

    while queue:
      (x, z), first_step = queue.popleft()
      for nx, nz in self.passable_neighbors(state, x, z):
        coord = (nx, nz)
        if coord in visited:
          continue
        if coord in goals:
          return first_step
        visited.add(coord)
        queue.append((coord, first_step))

    return None

  def resource_cells(self, state):
    cells = []
    for row in state["grid"]:
      for cell in row:
        if cell["type"] == "resource" and cell["gold"] > 0:
          cells.append(cell)
    return cells

  def passable_neighbors(self, state, x, z):
    return [
      (nx, nz) for nx, nz in neighbors(x, z, state.get("gridWidth", state["gridSize"]), state.get("gridHeight", state["gridSize"]))
      if self.is_passable_cell(state, nx, nz)
    ]

  def adjacent_passable_cells(self, state, x, z):
    return {
      (nx, nz)
      for nx, nz in neighbors(x, z, state.get("gridWidth", state["gridSize"]), state.get("gridHeight", state["gridSize"]))
      if self.is_passable_cell(state, nx, nz)
    }

  def all_passable_cells(self, state):
    return [
      (x, z)
      for x in range(state.get("gridWidth", state["gridSize"]))
      for z in range(state.get("gridHeight", state["gridSize"]))
      if self.is_passable_cell(state, x, z)
    ]

  def is_passable_cell(self, state, x, z):
    return state["grid"][x][z]["type"] not in ("base", "obstacle", "resource")

  def safest_passable_neighbor(self, state, unit, enemies):
    candidates = self.passable_neighbors(state, unit["x"], unit["z"])
    if not candidates:
      return None
    return max(candidates, key=lambda coord: self.nearest_enemy_distance(coord[0], coord[1], enemies))

  def nearest_enemy_distance(self, x, z, enemies):
    if not enemies:
      return 99
    return min(hex_distance(x, z, enemy["x"], enemy["z"]) for enemy in enemies)

  def enemy_base_target(self, current, state):
    for player_id, player in state.get("players", {}).items():
      if int(player_id) != current["playerId"] and player.get("baseHp", 0) > 0:
        base_pos = player["basePos"]
        return {
          "type": "base",
          "x": base_pos["x"],
          "z": base_pos["z"],
          "hp": player.get("baseHp", 0)
        }
    return None

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
