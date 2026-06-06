import random
import time

from config import TECH_TREE_CONFIG, UNITS_CONFIG
from hex_grid import get_hex_distance, get_neighbors
from state import ROOMS, state_lock


def handle_action(data, now_ms=None):
  room_id = data.get("roomId")
  player_id = data.get("playerId")
  action_type = data.get("action")
  args = data.get("args", {})

  with state_lock:
    if room_id not in ROOMS:
      return None, "Room not found"

    room = ROOMS[room_id]
    if room.status != "playing":
      return None, "Game not running"

    success, error_msg = apply_action(room, player_id, action_type, args, now_ms=now_ms)

  if success:
    return {"success": True}, None
  return None, error_msg or "Unknown action error"


def apply_action(room, player_id, action_type, args, now_ms=None):
  if action_type == "move":
    return move_units(room, player_id, args, now_ms=now_ms)
  if action_type == "build":
    return build_unit(room, player_id, args)
  if action_type == "buildTower":
    return build_power_tower(room, player_id, args)
  if action_type == "upgrade":
    return buy_upgrade(room, player_id, args)
  if action_type == "attack":
    return set_artillery_target(room, player_id, args)
  if action_type == "stop":
    return stop_artillery(room, player_id, args)
  return False, "Unknown action error"


def move_units(room, player_id, args, now_ms=None):
  unit_ids = args.get("unitIds", [])
  tx = args.get("toX")
  tz = args.get("toZ")

  for uid in unit_ids:
    if uid not in room.units:
      return False, "Unit does not exist"
    unit = room.units[uid]
    if unit.owner != player_id:
      return False, "You don't own this unit"
    if unit.isMoving:
      return False, "Unit is already traveling"
    if unit.stationary or unit.moveSpeed <= 0:
      return False, f"{unit.type} cannot move"

    neighbors = get_neighbors(unit.x, unit.z, room.grid_width, room.grid_height)
    if (tx, tz) not in neighbors:
      return False, "Invalid coordinate target"

    can_enter, error_msg = can_unit_enter_cell(room, unit, tx, tz)
    if not can_enter:
      return False, error_msg

  if now_ms is None:
    now_ms = int(time.time() * 1000)
  for uid in unit_ids:
    unit = room.units[uid]
    unit.isMoving = True
    unit.moveStartX = unit.x
    unit.moveStartZ = unit.z
    unit.targetX = tx
    unit.targetZ = tz
    unit.moveStartTime = now_ms
    duration = int(1500 / unit.moveSpeed) if unit.moveSpeed > 0 else 1500
    unit.moveEndTime = now_ms + duration
    unit.hasSnappedToTarget = False
    unit.isGathering = False
    unit.attackTargetX = None
    unit.attackTargetZ = None

  room.log(f"{room.players[player_id]['name']} ordered {len(unit_ids)} unit(s) to [{tx}, {tz}]")
  return True, ""


def build_unit(room, player_id, args):
  utype = args.get("unitType")
  unit_config = UNITS_CONFIG.get(utype)
  if not unit_config:
    return False, "Unknown unit type"
  if unit_config.get("builtBy") == "worker":
    return False, f"{unit_config.get('name', utype)} must be built by workers"

  cost = unit_config.get("cost", 50)
  player = room.players[player_id]

  if player["crystals"] < cost:
    return False, "Insufficient Gold"
  if player["baseHp"] <= 0:
    return False, "Base is destroyed"

  base_pos = player["basePos"]
  bx, bz = base_pos["x"], base_pos["z"]
  spawn_spots = []
  for tx, tz in get_neighbors(bx, bz, room.grid_width, room.grid_height):
    if can_unit_type_enter_cell(room, utype, tx, tz)[0]:
      spawn_spots.append((tx, tz))

  if not spawn_spots:
    return False, "No open adjacent spawning ground around base"

  player["crystals"] -= cost
  sx, sz = random.choice(spawn_spots)
  room.spawn_unit(utype, player_id, sx, sz)
  room.log(f"{player['name']} spawned {utype} at [{sx}, {sz}].", "build")
  return True, ""


def build_power_tower(room, player_id, args):
  tower_type = "powerTower"
  tower_config = UNITS_CONFIG.get(tower_type)
  if not tower_config:
    return False, "PowerTower is not configured"

  worker_id = args.get("workerId")
  if not worker_id:
    unit_ids = args.get("unitIds", [])
    worker_id = unit_ids[0] if unit_ids else None
  if not worker_id or worker_id not in room.units:
    return False, "Worker does not exist"

  worker = room.units[worker_id]
  if worker.owner != player_id:
    return False, "You don't own this worker"
  if worker.type != "worker":
    return False, "PowerTower must be built by a worker"
  if worker.isMoving:
    return False, "Worker is already traveling"

  player = room.players[player_id]
  if player["baseHp"] <= 0:
    return False, "Base is destroyed"

  cost = tower_config.get("cost", 50)
  if player["crystals"] < cost:
    return False, "Insufficient Gold"

  cell_type = room.grid[worker.x][worker.z].type
  if cell_type in ("base", "obstacle", "resource"):
    return False, "Cannot build PowerTower on blocked terrain"

  if any(unit.type == tower_type and unit.x == worker.x and unit.z == worker.z for unit in room.units.values()):
    return False, "A PowerTower already exists on this tile"

  player["crystals"] -= cost
  room.spawn_unit(tower_type, player_id, worker.x, worker.z)
  room.log(f"{player['name']} built PowerTower at [{worker.x}, {worker.z}].", "build")
  return True, ""


def buy_upgrade(room, player_id, args):
  upgrade_name = args.get("upgradeName")
  if upgrade_name not in TECH_TREE_CONFIG:
    return False, "Unknown tech upgrade"

  upgrade = TECH_TREE_CONFIG[upgrade_name]
  upgrade_type = upgrade.get("type", "UnitStat")
  if upgrade_type == "UnitStat":
    target_unit = upgrade.get("targetUnit")
    target_property = upgrade.get("targetProperty")
    if not target_unit or not target_property:
      return False, "Invalid tech upgrade"
  elif upgrade_type == "PassiveIncome":
    if upgrade.get("valueIncrease", 0) <= 0:
      return False, "Invalid passive income upgrade"
  else:
    return False, "Unknown tech upgrade type"

  player = room.players[player_id]
  if player["baseHp"] <= 0:
    return False, "Base is destroyed"

  cost = room.get_upgrade_cost(player_id, upgrade_name)
  if player["crystals"] < cost:
    return False, "Insufficient Gold"

  player["crystals"] -= cost
  upgrades = player.setdefault("techUpgrades", {})
  upgrades[upgrade_name] = upgrades.get(upgrade_name, 0) + 1

  if upgrade_type == "UnitStat":
    for unit in room.units.values():
      if unit.owner == player_id and unit.type == target_unit:
        room.apply_upgrade_to_unit(unit, upgrade)

    room.log(
      f"{player['name']} upgraded {target_unit} {target_property} "
      f"to level {upgrades[upgrade_name]}.",
      "build"
    )
  elif upgrade_type == "PassiveIncome":
    room.log(
      f"{player['name']} upgraded passive income "
      f"to level {upgrades[upgrade_name]}.",
      "build"
    )
  return True, ""


def can_unit_enter_cell(room, unit, tx, tz):
  return can_unit_type_enter_cell(room, unit.type, tx, tz)


def can_unit_type_enter_cell(room, unit_type, tx, tz):
  cell_type = room.grid[tx][tz].type
  if cell_type in ('base', 'obstacle', 'resource'):
    return False, "Cannot enter blocked terrain"
  return True, ""


def set_artillery_target(room, player_id, args):
  unit_ids = args.get("unitIds", [])
  tx = args.get("toX")
  tz = args.get("toZ")

  artillery_units = []
  for uid in unit_ids:
    if uid in room.units:
      unit = room.units[uid]
      if unit.type == 'artillery' and unit.owner == player_id and not unit.isMoving:
        dist = get_hex_distance(unit.x, unit.z, tx, tz)
        art_config = UNITS_CONFIG.get("artillery", {})
        min_range = art_config.get("minRange", 1)
        max_range = art_config.get("maxRange", 2)
        if min_range <= dist <= max_range:
          artillery_units.append(unit)

  if not artillery_units:
    return False, "No stationary artillery units in range selected"

  for unit in artillery_units:
    unit.attackTargetX = tx
    unit.attackTargetZ = tz
  return True, ""


def stop_artillery(room, player_id, args):
  unit_ids = args.get("unitIds", [])

  valid = False
  for uid in unit_ids:
    if uid in room.units:
      unit = room.units[uid]
      if unit.type == 'artillery' and unit.owner == player_id:
        unit.attackTargetX = None
        unit.attackTargetZ = None
        valid = True

  if not valid:
    return False, "No active artillery units selected"

  room.log(f"{room.players[player_id]['name']} stopped artillery fire.")
  return True, ""
