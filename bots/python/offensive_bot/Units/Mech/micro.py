from GeneralStrategy.settings import POWER_TOWER_TYPE, BuildPhase, SquadGoal, SquadType
from Squads.MechSquad.squad import MechSquad


def plan_worker_hunter_order(bot, state, squad, base_target):
  virtual_unit = squad.to_virtual_unit()
  if not virtual_unit:
    return None

  worker_target = bot.enemy_worker_target(state, virtual_unit)
  if worker_target:
    step = bot.step_towards_any(state, virtual_unit, {(worker_target["x"], worker_target["z"])}, avoid_enemy_towers=True)
    if step:
      return bot.move_order(squad.unit_ids, step[0], step[1])

  return bot.plan_mech_squad_order(state, squad, base_target)


def plan_mech_squad_order(bot, state, squad, base_target):
  if not base_target:
    return None

  virtual_unit = squad.to_virtual_unit()
  if not virtual_unit:
    return None

  nearby_enemy_max_steps = bot.strategy_instance.micro_value("mech", "nearbyEnemyMaxSteps", 3)
  avoid_enemy_towers = bot.strategy_instance.micro_value("mech", "avoidEnemyTowers", True)
  nearby_enemy = bot.nearby_mech_attack_target(state, virtual_unit, max_steps=nearby_enemy_max_steps)
  if nearby_enemy:
    step = bot.step_towards_any(state, virtual_unit, {(nearby_enemy["x"], nearby_enemy["z"])}, avoid_enemy_towers=avoid_enemy_towers)
    if step:
      return bot.move_order(squad.unit_ids, step[0], step[1])

  blocking_enemy = bot.enemy_in_way(state, virtual_unit, {(base_target["x"], base_target["z"])})
  if blocking_enemy:
    return bot.move_order(squad.unit_ids, blocking_enemy["x"], blocking_enemy["z"])

  base_standoff_distance = bot.strategy_instance.micro_value("mech", "baseStandoffDistance", 1)
  step = bot.step_towards(
    state,
    virtual_unit,
    base_target["x"],
    base_target["z"],
    keep_distance=base_standoff_distance,
    avoid_enemy_towers=avoid_enemy_towers
  )
  if step:
    return bot.move_order(squad.unit_ids, step[0], step[1])
  return None


def enemy_in_way(bot, state, unit, goals):
  avoid_enemy_towers = bot.strategy_instance.micro_value("mech", "avoidEnemyTowers", True)
  blocker_adjacent_distance = bot.strategy_instance.micro_value("mech", "blockerAdjacentDistance", 1)
  best_step = bot.step_towards_any(state, unit, goals, avoid_enemy_towers=avoid_enemy_towers)
  if not best_step:
    return None

  candidates = [
    enemy for enemy in bot.enemy_units(state)
    if enemy["type"] != POWER_TOWER_TYPE
    and not enemy.get("isMoving")
    and bot.hex_distance(unit["x"], unit["z"], enemy["x"], enemy["z"]) == blocker_adjacent_distance
  ]
  if not candidates:
    return None

  return min(
    candidates,
    key=lambda enemy: (
      bot.hex_distance(enemy["x"], enemy["z"], best_step[0], best_step[1]),
      bot.unit_priority(enemy),
      enemy.get("hp", 999)
    )
  )


def nearby_mech_attack_target(bot, state, mech, max_steps=3):
  candidates = []
  for enemy in bot.enemy_units(state):
    if enemy["type"] == POWER_TOWER_TYPE:
      continue
    avoid_enemy_towers = bot.strategy_instance.micro_value("mech", "avoidEnemyTowers", True)
    path_steps = bot.path_distance(state, mech, enemy["x"], enemy["z"], max_steps, avoid_enemy_towers=avoid_enemy_towers)
    if path_steps is None:
      continue
    candidates.append((path_steps, bot.unit_priority(enemy), enemy.get("hp", 999), enemy.get("id", ""), enemy))

  if not candidates:
    return None
  return min(candidates, key=lambda candidate: candidate[:4])[4]


def enemy_worker_target(bot, state, unit):
  workers = bot.enemy_units(state, "worker")
  if not workers:
    return None
  return min(workers, key=lambda worker: (
    bot.path_distance(
      state,
      unit,
      worker["x"],
      worker["z"],
      avoid_enemy_towers=bot.strategy_instance.micro_value("mech", "avoidEnemyTowers", True)
    ) or 999,
    bot.hex_distance(unit["x"], unit["z"], worker["x"], worker["z"]),
    worker.get("hp", 999),
    worker.get("id", "")
  ))


def build_squads(bot, state, phase):
  squads = []
  assigned_mechs = set()
  stationary_mechs = bot.own_units(state, "mech", stationary=True)
  stationary_artillery = bot.own_units(state, "artillery", stationary=True)
  sneaky_artillery_count = max(1, bot.strategy_instance.squad_value("sneakyArtillery", "artilleryCount", 1))
  sneaky_mech_escort_count = max(1, bot.strategy_instance.squad_value("sneakyArtillery", "mechEscortCount", 1))

  for artillery_group in unit_chunks(stationary_artillery, sneaky_artillery_count):
    available_escorts = [unit for unit in stationary_mechs if unit["id"] not in assigned_mechs]
    escorts = closest_units(artillery_group[0], available_escorts, sneaky_mech_escort_count, bot)
    if len(escorts) < sneaky_mech_escort_count:
      break
    assigned_mechs.update(mech["id"] for mech in escorts)
    squads.append({
      "type": SquadType.SNEAKY_ARTILLERY,
      "units": artillery_group + escorts,
      "goal": SquadGoal.FLANK_BASE
    })

  available_mechs = [
    mech for mech in stationary_mechs
    if mech["id"] not in assigned_mechs
  ]
  goal = SquadGoal.ENEMY_WORKERS if phase == BuildPhase.EARLY_GAME else SquadGoal.ENEMY_BASE
  mech_squad_size = max(1, bot.strategy_instance.squad_value("mech", "minimumUnits", MechSquad.minimum_units))
  for chunk in unit_chunks(available_mechs, mech_squad_size):
    squad = MechSquad(chunk, goal)
    if len(chunk) >= mech_squad_size:
      squads.append(squad)
      assigned_mechs.update(squad.unit_ids)
  return squads


def allocated_unit_ids(squads):
  allocated = set()
  for squad in squads:
    if isinstance(squad, dict):
      allocated.update(unit["id"] for unit in squad["units"])
    else:
      allocated.update(squad.unit_ids)
  return allocated


def closest_units(origin, units, count, bot):
  return sorted(
    units,
    key=lambda unit: (
      bot.hex_distance(origin["x"], origin["z"], unit["x"], unit["z"]),
      unit["id"]
    )
  )[:count]


def unit_chunks(units, squad_size):
  ordered = sorted(units, key=lambda unit: (unit["z"], unit["x"], unit["id"]))
  for idx in range(0, len(ordered), squad_size):
    chunk = ordered[idx:idx + squad_size]
    if len(chunk) >= squad_size:
      yield chunk
