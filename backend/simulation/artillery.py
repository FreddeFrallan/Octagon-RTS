from config import UNITS_CONFIG, get_artillery_shell_flight_ms
from hex_grid import get_hex_distance
from simulation.combat import is_attack_ready


def resolve_artillery_impact(room, impact):
  tx = impact["toX"]
  tz = impact["toZ"]
  damage = impact["damage"]
  attacker_owner = impact["attackerOwner"]
  target_cell = room.grid[tx][tz]

  hit_base = False
  base_owner = 0
  if target_cell.type == 'base':
    hit_base = True
    base_owner = target_cell.owner
    base_player = room.players[base_owner]
    base_player["baseHp"] = max(0, base_player["baseHp"] - damage)
    room.log(f"💥 Artillery shell impacts Base at [{tx}, {tz}] dealing {damage} damage!", "combat")

    if base_player["baseHp"] <= 0:
      room.log(f"Base of {base_player['name']} destroyed!")
      room.status = "gameover"
      room.winner = attacker_owner

  targets_here = [tu for tu in room.units.values() if tu.x == tx and tu.z == tz and not tu.isMoving]
  hit_any_unit = False
  first_target_owner = 0
  for victim in list(targets_here):
    if first_target_owner == 0:
      first_target_owner = victim.owner
    victim.hp -= damage
    hit_any_unit = True
    room.log(f"💥 Artillery blast impacts [{tx}, {tz}] dealing {damage} damage to {room.players[victim.owner]['name']}'s {victim.type.upper()}!", "combat")
    if victim.hp <= 0:
      room.log(f"💀 {room.players[victim.owner]['name']}'s {victim.type.upper()} destroyed by artillery blast!", "combat")
      room.units.pop(victim.id, None)

  if not hit_base and not hit_any_unit:
    room.log(f"💥 Artillery shell impacts empty cell [{tx}, {tz}]")

  room.add_event({
    "type": "artillery_impact",
    "toX": tx,
    "toZ": tz,
    "damage": damage if (hit_base or hit_any_unit) else 0,
    "isBase": hit_base,
    "targetOwner": base_owner if hit_base else first_target_owner
  })


def resolve_artillery_impacts(room, now_ms):
  pending_impacts = []
  for impact in room.pending_artillery_impacts:
    if now_ms >= impact["impactTime"]:
      resolve_artillery_impact(room, impact)
    else:
      pending_impacts.append(impact)
  room.pending_artillery_impacts = pending_impacts


def update_artillery(room, now_ms):
  for unit in list(room.units.values()):
    if unit.type == 'artillery' and not unit.isMoving and unit.attackTargetX is not None and unit.attackTargetZ is not None:
      if is_attack_ready(unit, now_ms):
        tx = unit.attackTargetX
        tz = unit.attackTargetZ

        dist = get_hex_distance(unit.x, unit.z, tx, tz)
        art_config = UNITS_CONFIG.get("artillery", {})
        min_range = art_config.get("minRange", 1)
        max_range = art_config.get("maxRange", 2)
        if dist < min_range or dist > max_range:
          unit.attackTargetX = None
          unit.attackTargetZ = None
          continue

        unit.lastAttackTime = now_ms
        damage = art_config.get("attack", 16)
        shell_flight_ms = get_artillery_shell_flight_ms()
        room.pending_artillery_impacts.append({
          "attackerOwner": unit.owner,
          "toX": tx,
          "toZ": tz,
          "damage": damage,
          "impactTime": now_ms + shell_flight_ms
        })
        room.log(f"💥 Artillery fires at [{tx}, {tz}]", "combat")

        room.add_event({
          "type": "artillery_shell",
          "fromX": unit.x, "fromZ": unit.z,
          "toX": tx, "toZ": tz,
          "flightTime": shell_flight_ms
        })
