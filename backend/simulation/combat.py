import random


def is_attack_ready(unit, now_ms):
  return now_ms - unit.lastAttackTime >= unit.attackCooldown


def resolve_close_combat(room, now_ms):
  attackers = list(room.units.values())
  random.shuffle(attackers)

  for attacker in attackers:
    if attacker.id not in room.units:
      continue
    if not is_attack_ready(attacker, now_ms):
      continue

    opponents = [
      unit for unit in room.units.values()
      if unit.owner != attacker.owner and unit.x == attacker.x and unit.z == attacker.z
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
