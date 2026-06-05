import json
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


class OffensiveBot:
  def __init__(self, name="Python Offensive Bot", max_actions_per_tick=8, verbose=True, min_workers=1, max_workers=5):
    self.name = name
    self.max_actions_per_tick = max_actions_per_tick
    self.verbose = verbose
    self.min_workers = max(0, min_workers)
    self.max_workers = max(self.min_workers, max_workers)
    self.session = None
    self.session_lock = threading.Lock()
    self.thread = None
    self.stop_event = threading.Event()
    self.worker_spend = 0
    self.combat_spend = 0
    self.unit_tracker = {}
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
      self.unit_tracker = {}
      self.last_unit_orders = {}
      self.last_artillery_targets = {}
      self.combat_build_toggle = 0

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
        self.update_unit_tracker(state)
        self.play_tick(current, state)
      except (urllib.error.URLError, TimeoutError, KeyError, json.JSONDecodeError) as e:
        self.log(f"tick skipped: {type(e).__name__}: {e}")

      time.sleep(current.get("pollMs", 200) / 1000)

  def fetch_state(self, current):
    return get_json(
      f"{current['gameServer']}/api/state"
      f"?roomId={current['roomId']}&playerId={current['playerId']}&events=0"
    )

  def update_unit_tracker(self, state):
    now = time.time()
    seen_unit_ids = set()

    for unit_id, unit in state.get("units", {}).items():
      seen_unit_ids.add(unit_id)
      current_pos = (unit["x"], unit["z"])
      previous = self.unit_tracker.get(unit_id)

      if not previous:
        self.unit_tracker[unit_id] = {
          "last_pos": current_pos,
          "stationary_since": now if not unit.get("isMoving") else None,
          "last_direction": None
        }
        continue

      last_pos = previous["last_pos"]
      direction = previous.get("last_direction")
      if current_pos != last_pos:
        direction = (current_pos[0] - last_pos[0], current_pos[1] - last_pos[1])
        stationary_since = now if not unit.get("isMoving") else None
      elif unit.get("isMoving"):
        stationary_since = None
      else:
        stationary_since = previous.get("stationary_since") or now

      self.unit_tracker[unit_id] = {
        "last_pos": current_pos,
        "stationary_since": stationary_since,
        "last_direction": direction
      }

    for unit_id in list(self.unit_tracker):
      if unit_id not in seen_unit_ids:
        self.unit_tracker.pop(unit_id, None)

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
    elif self.try_upgrade(current, state):
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

    own = self.own_units(state)
    worker_count = sum(1 for unit in own if unit["type"] == "worker")
    if worker_count < self.min_workers and crystals >= UNIT_COSTS["worker"]:
      return "worker"

    combat_choice = self.choose_combat_build(state, crystals)
    if combat_choice:
      return combat_choice

    if worker_count < self.max_workers and crystals >= UNIT_COSTS["worker"]:
      return "worker"
    return None

  def choose_combat_build(self, state, crystals):
    own = self.own_units(state)
    mech_count = sum(1 for unit in own if unit["type"] == "mech")
    artillery_count = sum(1 for unit in own if unit["type"] == "artillery")

    if mech_count >= 1 and artillery_count < 1 and crystals >= UNIT_COSTS["artillery"]:
      self.combat_build_toggle += 1
      return "artillery"

    if mech_count < 2 and crystals >= UNIT_COSTS["mech"]:
      self.combat_build_toggle += 1
      return "mech"

    if crystals >= UNIT_COSTS["mech"]:
      self.combat_build_toggle += 1
      return "mech"

    return None

  def try_upgrade(self, current, state):
    player = state["players"][str(current["playerId"])]
    crystals = player["crystals"]
    if player["baseHp"] <= 0:
      return False

    upgrade_name = self.choose_upgrade(state, crystals, player.get("techUpgrades", {}))
    if not upgrade_name:
      return False

    return self.action(current, "upgrade", {"upgradeName": upgrade_name})

  def choose_upgrade(self, state, crystals, owned_levels):
    tech_tree = state.get("techTree", {})
    if not self.own_units(state, "mech"):
      return None

    property_priority = {"moveSpeed": 0, "maxHp": 1}
    candidates = []
    for name, upgrade in tech_tree.items():
      if upgrade.get("targetUnit") != "mech":
        continue
      if upgrade.get("targetProperty") not in property_priority:
        continue

      level = owned_levels.get(name, 0)
      cost = upgrade.get("initialCost", 0) + level * upgrade.get("costIncrease", 0)
      if cost > crystals:
        continue

      candidates.append((
        level,
        property_priority.get(upgrade.get("targetProperty"), 99),
        cost,
        name
      ))

    if not candidates:
      return None
    return min(candidates)[3]

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
    base_target = self.enemy_base_target(current, state)
    if not base_target:
      return []

    orders = []
    for squad in self.build_squads(state):
      order = self.plan_squad_order(state, squad, base_target)
      if isinstance(order, list):
        orders.extend(order)
      elif order:
        orders.append(order)

    return orders

  def build_squads(self, state):
    squads = []
    assigned_mechs = set()
    stationary_mechs = self.own_units(state, "mech", stationary=True)
    stationary_artillery = self.own_units(state, "artillery", stationary=True)

    for artillery in stationary_artillery:
      mech = self.closest_unit(artillery, [unit for unit in stationary_mechs if unit["id"] not in assigned_mechs])
      if not mech:
        break
      assigned_mechs.add(mech["id"])
      squads.append({
        "type": "SneakyArtillery",
        "units": [artillery, mech],
        "goal": "flank_base"
      })

    for mech in self.own_units(state, "mech", stationary=True):
      if mech["id"] in assigned_mechs:
        continue
      squads.append({
        "type": "mech",
        "units": [mech],
        "goal": "enemy_base"
      })
    return squads

  def plan_squad_order(self, state, squad, base_target):
    if squad["type"] == "SneakyArtillery":
      return self.plan_sneaky_artillery_order(state, squad, base_target)
    if squad["type"] == "mech":
      return self.plan_mech_squad_order(state, squad, base_target)
    return None

  def plan_mech_squad_order(self, state, squad, base_target):
    if not base_target:
      return None

    leader = squad["units"][0]
    nearby_enemy = self.nearby_mech_attack_target(state, leader, max_steps=3)
    if nearby_enemy:
      step = self.step_towards_any(state, leader, {(nearby_enemy["x"], nearby_enemy["z"])})
      if step:
        return self.move_order(leader["id"], step[0], step[1])

    blocking_enemy = self.enemy_in_way(state, leader, {(base_target["x"], base_target["z"])})
    if blocking_enemy:
      return self.move_order(leader["id"], blocking_enemy["x"], blocking_enemy["z"])

    step = self.step_towards(state, leader, base_target["x"], base_target["z"], keep_distance=1)
    if step:
      unit_ids = [unit["id"] for unit in squad["units"]]
      return self.move_order(unit_ids, step[0], step[1])
    return None

  def plan_sneaky_artillery_order(self, state, squad, base_target):
    if not base_target:
      return None

    artillery = next((unit for unit in squad["units"] if unit["type"] == "artillery"), None)
    mech = next((unit for unit in squad["units"] if unit["type"] == "mech"), None)
    if not artillery or not mech:
      return None

    blocking_target = self.artillery_target_in_way(state, artillery, self.sneaky_artillery_goals(state, artillery, base_target))
    if blocking_target:
      return self.attack_order(artillery["id"], blocking_target["x"], blocking_target["z"])

    distance_to_base = hex_distance(artillery["x"], artillery["z"], base_target["x"], base_target["z"])
    if 1 <= distance_to_base <= 2 and self.is_flank_position(state, artillery, base_target):
      return self.attack_order(artillery["id"], base_target["x"], base_target["z"])

    goals = self.sneaky_artillery_goals(state, artillery, base_target)
    orders = []
    artillery_step = self.step_towards_any(state, artillery, goals)
    if artillery_step:
      orders.append(self.move_order(artillery["id"], artillery_step[0], artillery_step[1]))

    mech_goals = goals
    if hex_distance(mech["x"], mech["z"], artillery["x"], artillery["z"]) > 1:
      mech_goals = {(artillery["x"], artillery["z"])} | self.adjacent_passable_cells(state, artillery["x"], artillery["z"])
    blocking_enemy = self.enemy_in_way(state, mech, mech_goals)
    if blocking_enemy:
      orders.append(self.move_order(mech["id"], blocking_enemy["x"], blocking_enemy["z"]))
      return orders

    mech_step = self.step_towards_any(state, mech, mech_goals)
    if mech_step:
      orders.append(self.move_order(mech["id"], mech_step[0], mech_step[1]))

    return orders

  def enemy_in_way(self, state, unit, goals):
    best_step = self.step_towards_any(state, unit, goals)
    if not best_step:
      return None

    candidates = [
      enemy for enemy in self.enemy_units(state)
      if not enemy.get("isMoving") and hex_distance(unit["x"], unit["z"], enemy["x"], enemy["z"]) == 1
    ]
    if not candidates:
      return None

    return min(
      candidates,
      key=lambda enemy: (
        hex_distance(enemy["x"], enemy["z"], best_step[0], best_step[1]),
        unit_priority(enemy),
        enemy.get("hp", 999)
      )
    )

  def nearby_mech_attack_target(self, state, mech, max_steps=3):
    candidates = []
    for enemy in self.enemy_units(state):
      path_steps = self.path_distance(state, mech, enemy["x"], enemy["z"], max_steps)
      if path_steps is None:
        continue
      candidates.append((path_steps, unit_priority(enemy), enemy.get("hp", 999), enemy))

    if not candidates:
      return None
    return min(candidates)[3]

  def artillery_target_in_way(self, state, artillery, goals):
    best_step = self.step_towards_any(state, artillery, goals)
    if not best_step:
      return None

    candidates = [
      enemy for enemy in self.enemy_units(state)
      if 1 <= hex_distance(artillery["x"], artillery["z"], enemy["x"], enemy["z"]) <= 2
    ]
    if not candidates:
      return None

    target = min(
      candidates,
      key=lambda enemy: (
        hex_distance(enemy["x"], enemy["z"], best_step[0], best_step[1]),
        unit_priority(enemy),
        enemy.get("hp", 999)
      )
    )
    target_x, target_z = self.artillery_target_square(state, artillery, target)
    return {**target, "x": target_x, "z": target_z}

  def artillery_target_square(self, state, artillery, target_unit):
    current = (target_unit["x"], target_unit["z"])
    tracker = self.unit_tracker.get(target_unit["id"], {})
    stationary_since = tracker.get("stationary_since")

    if stationary_since is not None and time.time() - stationary_since >= 2:
      return current

    direction = self.target_direction(target_unit, tracker)
    if direction:
      predicted = (current[0] + direction[0], current[1] + direction[1])
      if self.is_valid_artillery_target(state, artillery, predicted[0], predicted[1]):
        return predicted

    return current

  def target_direction(self, target_unit, tracker):
    if target_unit.get("isMoving") and target_unit.get("targetX") is not None and target_unit.get("targetZ") is not None:
      dx = target_unit["targetX"] - target_unit["x"]
      dz = target_unit["targetZ"] - target_unit["z"]
      if dx != 0 or dz != 0:
        return self.normalize_step(dx, dz)

    return tracker.get("last_direction")

  def normalize_step(self, dx, dz):
    return (
      0 if dx == 0 else (1 if dx > 0 else -1),
      0 if dz == 0 else (1 if dz > 0 else -1)
    )

  def is_valid_artillery_target(self, state, artillery, x, z):
    width = state.get("gridWidth", state["gridSize"])
    height = state.get("gridHeight", state["gridSize"])
    if x < 0 or x >= width or z < 0 or z >= height:
      return False
    return 1 <= hex_distance(artillery["x"], artillery["z"], x, z) <= 2

  def sneaky_artillery_goals(self, state, artillery, base_target):
    attack_goals = self.flank_attack_goals(state, artillery, base_target)
    if attack_goals:
      return attack_goals
    return self.flank_lane_goals(state, artillery, base_target)

  def flank_attack_goals(self, state, artillery, base_target):
    return {
      (x, z)
      for x, z in self.all_passable_cells(state)
      if 1 <= hex_distance(x, z, base_target["x"], base_target["z"]) <= 2
      and self.is_flank_coord(state, z, artillery, base_target)
    }

  def flank_lane_goals(self, state, artillery, base_target):
    lane_z = self.flank_lane_z(state, artillery, base_target)
    return {
      (x, z)
      for x, z in self.all_passable_cells(state)
      if z == lane_z
    }

  def is_flank_position(self, state, unit, base_target):
    return self.is_flank_coord(state, unit["z"], unit, base_target)

  def is_flank_coord(self, state, z, unit, base_target):
    lane_z = self.flank_lane_z(state, unit, base_target)
    if lane_z == 0:
      return z <= max(0, base_target["z"] - 1)
    return z >= min(state.get("gridHeight", state["gridSize"]) - 1, base_target["z"] + 1)

  def flank_lane_z(self, state, unit, base_target):
    height = state.get("gridHeight", state["gridSize"])
    if unit["z"] <= base_target["z"]:
      return 0
    return height - 1

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

  def closest_unit(self, unit, units):
    if not units:
      return None
    return min(units, key=lambda candidate: hex_distance(unit["x"], unit["z"], candidate["x"], candidate["z"]))

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

  def path_distance(self, state, unit, target_x, target_z, max_steps=None):
    start = (unit["x"], unit["z"])
    target = (target_x, target_z)
    if start == target:
      return 0

    visited = {start}
    queue = deque([(start, 0)])
    while queue:
      (x, z), distance = queue.popleft()
      if max_steps is not None and distance >= max_steps:
        continue

      for nx, nz in self.passable_neighbors(state, x, z):
        coord = (nx, nz)
        if coord in visited:
          continue
        next_distance = distance + 1
        if coord == target:
          return next_distance
        visited.add(coord)
        queue.append((coord, next_distance))

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

  def move_order(self, unit_ids, x, z):
    if isinstance(unit_ids, str):
      unit_ids = [unit_ids]
    return {
      "action": "move",
      "args": {"unitIds": unit_ids, "toX": x, "toZ": z}
    }

  def attack_order(self, unit_id, x, z):
    return {
      "action": "attack",
      "args": {"unitIds": [unit_id], "toX": x, "toZ": z}
    }

  def log(self, message):
    if self.verbose:
      print(f"[{self.name}] {message}", flush=True)
