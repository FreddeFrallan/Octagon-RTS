from hex_grid import get_neighbors
from simulation.combat import is_attack_ready


def update_base_attacks(room, now_ms):
  for base_owner, player in room.players.items():
    base_pos = player["basePos"]
    bx, bz = base_pos["x"], base_pos["z"]
    base_player = room.players[base_owner]
    if base_player["baseHp"] <= 0:
      continue

    hostiles = []
    for tx, tz in get_neighbors(bx, bz, room.grid_width, room.grid_height):
      for unit in room.units.values():
        if unit.x == tx and unit.z == tz and unit.owner != base_owner and not unit.isMoving and is_attack_ready(unit, now_ms):
          defenders = [d for d in room.units.values() if d.x == tx and d.z == tz and d.owner == base_owner]
          if not defenders:
            hostiles.append(unit)

    if hostiles:
      for unit in hostiles:
        if base_player["baseHp"] <= 0:
          break
        base_player["baseHp"] = max(0, base_player["baseHp"] - unit.attack)
        unit.lastAttackTime = now_ms
        room.log(f"💥 {room.players[unit.owner]['name']}'s {unit.type.upper()} shells Base for {unit.attack} damage (Base HP: {base_player['baseHp']}/{base_player['maxBaseHp']})", "combat")
        room.add_event({
          "type": "combat_hit",
          "x": bx,
          "z": bz,
          "damage": unit.attack,
          "targetOwner": base_owner,
          "isBase": True,
          "attackerX": unit.x,
          "attackerZ": unit.z
        })

      if base_player["baseHp"] <= 0:
        room.log(f"Base of {base_player['name']} destroyed!")
        room.check_game_over()
