import random
import time

from config import UNITS_CONFIG
from hex_grid import get_hex_distance, get_neighbors
from state import ROOMS, state_lock


def handle_action(data):
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

    if action_type == "move":
      success, error_msg = move_units(room, player_id, args)
    elif action_type == "build":
      success, error_msg = build_unit(room, player_id, args)
    elif action_type == "attack":
      success, error_msg = set_artillery_target(room, player_id, args)
    elif action_type == "stop":
      success, error_msg = stop_artillery(room, player_id, args)
    else:
      success = False
      error_msg = "Unknown action error"

  if success:
    return {"success": True}, None
  return None, error_msg or "Unknown action error"


def move_units(room, player_id, args):
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

    neighbors = get_neighbors(unit.x, unit.z, room.grid_size)
    if (tx, tz) not in neighbors:
      return False, "Invalid coordinate target"

    if room.grid[tx][tz].type in ('base', 'obstacle'):
      return False, "Cannot enter blocked terrain"

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
  cost = UNITS_CONFIG.get(utype, {}).get("cost", 50)
  player = room.players[player_id]

  if player["crystals"] < cost:
    return False, "Insufficient Gold"
  if player["baseHp"] <= 0:
    return False, "Base is destroyed"

  base_pos = player["basePos"]
  bx, bz = base_pos["x"], base_pos["z"]
  spawn_spots = []
  for tx, tz in get_neighbors(bx, bz, room.grid_size):
    if room.grid[tx][tz].type not in ('base', 'obstacle'):
      spawn_spots.append((tx, tz))

  if not spawn_spots:
    return False, "No open adjacent spawning ground around base"

  player["crystals"] -= cost
  sx, sz = random.choice(spawn_spots)
  room.spawn_unit(utype, player_id, sx, sz)
  room.log(f"{player['name']} spawned {utype} at [{sx}, {sz}].", "build")
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
