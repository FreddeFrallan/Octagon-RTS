import random

from config import UNITS_CONFIG
from hex_grid import get_hex_distance


def is_attack_ready(unit, now_ms):
  return now_ms - unit.lastAttackTime >= unit.attackCooldown


def is_unit_in_attack_range(attacker, target):
  config = UNITS_CONFIG.get(attacker.type, {})
  min_range = config.get("minRange", 0)
  max_range = config.get("maxRange", 0)
  distance = get_hex_distance(attacker.x, attacker.z, target.x, target.z)
  return min_range <= distance <= max_range


def resolve_close_combat(room, now_ms):
  attackers = list(room.units.values())
  random.shuffle(attackers)

  for attacker in attackers:
    if attacker.id not in room.units:
      continue
    if attacker.attack <= 0:
      continue
    if attacker.type == "artillery":
      continue
    if not is_attack_ready(attacker, now_ms):
      continue

    opponents = [
      unit for unit in room.units.values()
      if unit.owner != attacker.owner and is_unit_in_attack_range(attacker, unit)
    ]
    if not opponents:
      continue

    target = random.choice(opponents)
    target.hp -= attacker.attack
    attacker.lastAttackTime = now_ms
    room.log(
      f"{room.players[attacker.owner]['name']}'s {attacker.type.upper()} deals {attacker.attack} damage "
      f"to {room.players[target.owner]['name']}'s {target.type.upper()} "
      f"(HP: {max(0, target.hp)}/{target.maxHp})",
      "combat"
    )
    room.add_event({
      "type": "combat_hit",
      "x": target.x,
      "z": target.z,
      "damage": attacker.attack,
      "targetOwner": target.owner
    })

    if target.hp <= 0:
      room.log(f"💀 {room.players[target.owner]['name']}'s {target.type.upper()} was destroyed in battle!", "combat")
      room.units.pop(target.id, None)
