import time

from GeneralStrategy.settings import (
  ARTILLERY_ESCORT_DISTANCE,
  ARTILLERY_MAX_RANGE,
  ARTILLERY_MIN_RANGE,
  ARTILLERY_SHELL_FLIGHT_SECONDS,
  ArtilleryCombatBehavior,
  POWER_TOWER_TYPE,
  UnitTacticalState
)


def plan_sneaky_artillery_order(bot, state, squad, base_target):
  if not base_target:
    return None

  artillery_units = [unit for unit in squad["units"] if unit["type"] == "artillery"]
  mech_units = [unit for unit in squad["units"] if unit["type"] == "mech"]
  if not artillery_units or not mech_units:
    return None

  combat_orders = []
  for artillery in artillery_units:
    if (
      bot.unit_tactical_state(state, artillery) == UnitTacticalState.COMBAT
      and bot.artillery_state_behaviors[UnitTacticalState.COMBAT] == ArtilleryCombatBehavior.STRATEGIC_AIM_THEN_COOLDOWN_RETREAT
      and bot.artillery_is_reloading(artillery)
    ):
      retreat_order = bot.artillery_combat_retreat_order(state, artillery)
      if retreat_order:
        combat_orders.append(retreat_order)
        continue

    tower_target = bot.artillery_power_tower_target(state, artillery)
    if tower_target:
      combat_orders.append(bot.attack_order(artillery["id"], tower_target["x"], tower_target["z"]))
      continue

    blocking_target = bot.artillery_target_in_way(state, artillery, bot.sneaky_artillery_goals(state, artillery, base_target))
    if blocking_target:
      combat_orders.append(bot.attack_order(artillery["id"], blocking_target["x"], blocking_target["z"]))
      continue

    min_range = bot.strategy_instance.micro_value("artillery", "minRange", ARTILLERY_MIN_RANGE)
    max_range = bot.strategy_instance.micro_value("artillery", "maxRange", ARTILLERY_MAX_RANGE)
    distance_to_base = bot.hex_distance(artillery["x"], artillery["z"], base_target["x"], base_target["z"])
    if min_range <= distance_to_base <= max_range and bot.is_flank_position(state, artillery, base_target):
      combat_orders.append(bot.attack_order(artillery["id"], base_target["x"], base_target["z"]))

  if combat_orders:
    return combat_orders[0] if len(combat_orders) == 1 else combat_orders

  lead_artillery = artillery_units[0]
  goals = bot.sneaky_artillery_goals(state, lead_artillery, base_target)
  orders = []
  for artillery in artillery_units:
    artillery_step = bot.step_towards_any(state, artillery, goals)
    if artillery_step:
      orders.append(bot.move_order(artillery["id"], artillery_step[0], artillery_step[1]))

  mech_goals = goals
  escort_distance = bot.strategy_instance.micro_value("artillery", "escortDistance", ARTILLERY_ESCORT_DISTANCE)
  if any(bot.hex_distance(mech["x"], mech["z"], lead_artillery["x"], lead_artillery["z"]) > escort_distance for mech in mech_units):
    mech_goals = {(lead_artillery["x"], lead_artillery["z"])} | bot.adjacent_passable_cells(
      state,
      lead_artillery["x"],
      lead_artillery["z"],
      avoid_enemy_towers=bot.strategy_instance.micro_value("artillery", "avoidEnemyTowers", True)
    )

  for mech in mech_units:
    blocking_enemy = bot.enemy_in_way(state, mech, mech_goals)
    if blocking_enemy:
      orders.append(bot.move_order(mech["id"], blocking_enemy["x"], blocking_enemy["z"]))
      continue

    mech_step = bot.step_towards_any(
      state,
      mech,
      mech_goals,
      avoid_enemy_towers=bot.strategy_instance.micro_value("artillery", "avoidEnemyTowers", True)
    )
    if mech_step:
      orders.append(bot.move_order(mech["id"], mech_step[0], mech_step[1]))

  return orders


def artillery_target_in_way(bot, state, artillery, goals):
  best_step = bot.step_towards_any(state, artillery, goals)
  if not best_step:
    return None

  candidates = []
  for enemy in bot.enemy_units(state):
    target_square = bot.artillery_target_square(state, artillery, enemy)
    if not target_square:
      continue
    target_x, target_z = target_square
    candidates.append((
      bot.hex_distance(target_x, target_z, best_step[0], best_step[1]),
      bot.artillery_target_priority(enemy),
      enemy.get("hp", 999),
      enemy.get("id", ""),
      enemy,
      target_square
    ))

  if not candidates:
    return None

  _, _, _, _, target, target_square = min(candidates, key=lambda candidate: candidate[:4])
  target_x, target_z = target_square
  return {**target, "x": target_x, "z": target_z}


def artillery_power_tower_target(bot, state, artillery):
  targets = [
    tower for tower in bot.enemy_units(state, POWER_TOWER_TYPE, stationary=True)
    if bot.is_valid_artillery_target(state, artillery, tower["x"], tower["z"])
  ]
  if not targets:
    return None
  return min(targets, key=lambda tower: (
    bot.hex_distance(artillery["x"], artillery["z"], tower["x"], tower["z"]),
    tower.get("hp", 999),
    tower.get("id", "")
  ))


def artillery_is_reloading(bot, artillery):
  if artillery.get("attackWillLand") is not None:
    return True

  last_attack_time = artillery.get("lastAttackTime") or 0
  attack_cooldown = artillery.get("attackCooldown") or 0
  if last_attack_time <= 0 or attack_cooldown <= 0:
    return False

  now_ms = int(bot.order_time() * 1000) if hasattr(bot, "order_time") else int(time.time() * 1000)
  return now_ms - last_attack_time < attack_cooldown


def artillery_combat_retreat_order(bot, state, artillery):
  retreat_threat_distance = bot.strategy_instance.micro_value("artillery", "retreatThreatDistance", 2)
  threat = bot.nearby_enemy_mech(state, artillery, max_distance=retreat_threat_distance)
  if not threat:
    return None

  avoid_enemy_towers = bot.strategy_instance.micro_value("artillery", "avoidEnemyTowers", True)
  candidates = bot.passable_neighbors(state, artillery["x"], artillery["z"], avoid_enemy_towers=avoid_enemy_towers)
  if not candidates:
    candidates = bot.passable_neighbors(state, artillery["x"], artillery["z"])
  if not candidates:
    return None

  current_threat_distance = bot.hex_distance(artillery["x"], artillery["z"], threat["x"], threat["z"])
  enemies = bot.enemy_units(state)
  best = max(candidates, key=lambda coord: (
    nearest_enemy_mech_distance_at(bot, state, coord[0], coord[1]),
    bot.nearest_enemy_distance(coord[0], coord[1], enemies),
    0 if bot.is_enemy_power_tower_zone(state, coord[0], coord[1]) else 1
  ))

  if nearest_enemy_mech_distance_at(bot, state, best[0], best[1]) <= current_threat_distance:
    return None
  return bot.move_order(artillery["id"], best[0], best[1])


def nearby_enemy_mech(bot, state, unit, max_distance=2):
  mechs = [
    enemy for enemy in bot.enemy_units(state, "mech")
    if bot.hex_distance(unit["x"], unit["z"], enemy["x"], enemy["z"]) <= max_distance
  ]
  if not mechs:
    return None
  return min(mechs, key=lambda enemy: (
    bot.hex_distance(unit["x"], unit["z"], enemy["x"], enemy["z"]),
    enemy.get("hp", 999),
    enemy.get("id", "")
  ))


def nearest_enemy_mech_distance(bot, state, unit):
  return nearest_enemy_mech_distance_at(bot, state, unit["x"], unit["z"])


def nearest_enemy_mech_distance_at(bot, state, x, z):
  mechs = bot.enemy_units(state, "mech")
  if not mechs:
    return 99
  return min(bot.hex_distance(x, z, mech["x"], mech["z"]) for mech in mechs)


def artillery_target_priority(bot, enemy):
  if enemy["type"] == POWER_TOWER_TYPE:
    return bot.strategy_instance.micro_value("artillery", "enemyPowerTowerPriority", -1)
  return bot.unit_priority(enemy)


def artillery_target_square(bot, state, artillery, target_unit):
  current = (target_unit["x"], target_unit["z"])
  if not target_unit.get("isMoving"):
    if bot.is_valid_artillery_target(state, artillery, current[0], current[1]):
      return current
    return None

  destination = bot.artillery_target_destination(target_unit)
  if not destination:
    return None

  shell_flight_seconds = bot.strategy_instance.micro_value("artillery", "shellFlightSeconds", ARTILLERY_SHELL_FLIGHT_SECONDS)
  now = bot.order_time() if hasattr(bot, "order_time") else time.time()
  impact_time_ms = int((now + shell_flight_seconds) * 1000)
  arrival_time_ms = bot.target_arrival_time_ms(target_unit)
  if arrival_time_ms is None or impact_time_ms < arrival_time_ms:
    return None

  if bot.is_valid_artillery_target(state, artillery, destination[0], destination[1]):
    return destination
  return None


def target_arrival_time_ms(bot, target_unit):
  move_end_time = target_unit.get("moveEndTime")
  if move_end_time is not None:
    return move_end_time

  move_start_time = target_unit.get("moveStartTime")
  move_speed = target_unit.get("moveSpeed")
  if move_start_time is None or not move_speed:
    return None

  return move_start_time + int(1500 / move_speed)


def artillery_target_destination(bot, target_unit):
  if target_unit.get("targetX") is not None and target_unit.get("targetZ") is not None:
    return target_unit["targetX"], target_unit["targetZ"]

  tracker = bot.unit_tracker.get(target_unit["id"], {})
  direction = bot.target_direction(target_unit, tracker)
  if not direction:
    return None
  return target_unit["x"] + direction[0], target_unit["z"] + direction[1]


def target_direction(bot, target_unit, tracker):
  if target_unit.get("isMoving") and target_unit.get("targetX") is not None and target_unit.get("targetZ") is not None:
    dx = target_unit["targetX"] - target_unit["x"]
    dz = target_unit["targetZ"] - target_unit["z"]
    if dx != 0 or dz != 0:
      return bot.normalize_step(dx, dz)

  return tracker.get("last_direction")


def is_valid_artillery_target(bot, state, artillery, x, z):
  width = state.get("gridWidth", state["gridSize"])
  height = state.get("gridHeight", state["gridSize"])
  if x < 0 or x >= width or z < 0 or z >= height:
    return False
  min_range = bot.strategy_instance.micro_value("artillery", "minRange", ARTILLERY_MIN_RANGE)
  max_range = bot.strategy_instance.micro_value("artillery", "maxRange", ARTILLERY_MAX_RANGE)
  return min_range <= bot.hex_distance(artillery["x"], artillery["z"], x, z) <= max_range


def sneaky_artillery_goals(bot, state, artillery, base_target):
  attack_goals = bot.flank_attack_goals(state, artillery, base_target)
  if attack_goals:
    return attack_goals
  return bot.flank_lane_goals(state, artillery, base_target)


def flank_attack_goals(bot, state, artillery, base_target):
  return {
    (x, z)
    for x, z in bot.all_passable_cells(state)
      if bot.strategy_instance.micro_value("artillery", "minRange", ARTILLERY_MIN_RANGE) <= bot.hex_distance(x, z, base_target["x"], base_target["z"]) <= bot.strategy_instance.micro_value("artillery", "maxRange", ARTILLERY_MAX_RANGE)
    and bot.is_flank_coord(state, z, artillery, base_target)
  }


def flank_lane_goals(bot, state, artillery, base_target):
  lane_z = bot.flank_lane_z(state, artillery, base_target)
  return {
    (x, z)
    for x, z in bot.all_passable_cells(state)
    if z == lane_z
  }


def is_flank_position(bot, state, unit, base_target):
  return bot.is_flank_coord(state, unit["z"], unit, base_target)


def is_flank_coord(bot, state, z, unit, base_target):
  lane_z = bot.flank_lane_z(state, unit, base_target)
  if lane_z == 0:
    return z <= max(0, base_target["z"] - 1)
  return z >= min(state.get("gridHeight", state["gridSize"]) - 1, base_target["z"] + 1)


def flank_lane_z(bot, state, unit, base_target):
  height = state.get("gridHeight", state["gridSize"])
  if unit["z"] <= base_target["z"]:
    return 0
  return height - 1
