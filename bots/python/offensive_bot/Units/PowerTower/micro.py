from GeneralStrategy.settings import (
  BuildPhase,
  POWER_TOWER_TYPE,
  POWER_TOWER_WORKER_SAFE_DISTANCE,
  UNIT_COSTS,
  WorkerTacticalState
)


def should_reserve_for_power_tower(bot, state, crystals):
  if bot.build_strategy_phase(state) != BuildPhase.MID_GAME:
    return False
  if bot.mid_base_power_towers_remaining(state) <= 0:
    return False
  if len(bot.own_units(state, POWER_TOWER_TYPE)) >= bot.max_power_towers:
    return False
  if not bot.own_units(state, "worker"):
    return False

  if crystals < UNIT_COSTS[POWER_TOWER_TYPE]:
    return False
  if active_building_tower_assignment(bot, state):
    return True
  return bool(bot.own_units(state, "worker", stationary=True))


def mid_base_power_towers_remaining(bot, state):
  player = state["players"][str(state["localPlayerId"])]
  base_pos = player["basePos"]
  base = (base_pos["x"], base_pos["z"])
  return max(0, bot.mid_base_power_towers - len(bot.power_towers_near_base(state, base)))


def plan_power_tower_orders(bot, current, state, workers, enemies, planned_tower_tiles):
  existing_towers = bot.own_units(state, POWER_TOWER_TYPE)
  if len(existing_towers) >= bot.max_power_towers:
    clear_building_tower_states(bot)
    return []

  goals = bot.power_tower_goals(current, state)
  if not goals:
    clear_building_tower_states(bot)
    return []

  orders = []
  assigned_workers = set()
  player = state["players"][str(current["playerId"])]
  base_pos = player["basePos"]
  base = (base_pos["x"], base_pos["z"])
  base_tower_count = len(bot.power_towers_near_base(state, base))
  needed = min(
    bot.mid_base_power_towers - base_tower_count,
    bot.max_power_towers - len(existing_towers)
  )
  needed = min(needed, 1)

  if needed <= 0:
    clear_building_tower_states(bot)
    return []

  active_assignment = active_building_tower_assignment(bot, state)
  if active_assignment:
    worker, goal = active_assignment
    if goal in planned_tower_tiles or not bot.is_valid_power_tower_tile(state, goal[0], goal[1]):
      clear_worker_building_tower_state(bot, worker["id"])
      return []
    order = worker_tower_order(bot, state, worker, goal)
    planned_tower_tiles.add(goal)
    return [order] if order else []

  for goal in goals:
    if goal in planned_tower_tiles:
      continue
    if not bot.is_valid_power_tower_tile(state, goal[0], goal[1]):
      continue

    worker = bot.closest_available_worker(workers, goal, assigned_workers, enemies)
    if not worker:
      continue

    order = worker_tower_order(bot, state, worker, goal)
    if order:
      set_worker_building_tower_state(bot, worker["id"], goal)
      orders.append(order)
      planned_tower_tiles.add(goal)
      assigned_workers.add(worker["id"])
      break

  return orders


def worker_tower_order(bot, state, worker, goal):
  if worker.get("isMoving"):
    return None

  if (worker["x"], worker["z"]) == goal:
    set_worker_building_tower_state(bot, worker["id"], goal)
    return bot.build_tower_order(worker["id"])

  step = bot.step_towards_any(state, worker, {goal})
  if step:
    set_worker_building_tower_state(bot, worker["id"], goal)
    return bot.move_order(worker["id"], step[0], step[1])

  return None


def active_building_tower_assignment(bot, state):
  own_workers = {
    worker["id"]: worker
    for worker in bot.own_units(state, "worker")
  }
  for worker_id, tracked in list(bot.unit_tracker.items()):
    if tracked.get("worker_state") != WorkerTacticalState.BUILDING_TOWER.value:
      continue

    worker = own_workers.get(worker_id)
    goal = tracked.get("tower_goal")
    if not worker or not goal:
      clear_worker_building_tower_state(bot, worker_id)
      continue

    goal = tuple(goal)
    if not bot.is_valid_power_tower_tile(state, goal[0], goal[1]):
      clear_worker_building_tower_state(bot, worker_id)
      continue

    return worker, goal
  return None


def set_worker_building_tower_state(bot, worker_id, goal):
  tracked = bot.unit_tracker.setdefault(worker_id, {})
  tracked["worker_state"] = WorkerTacticalState.BUILDING_TOWER.value
  tracked["tower_goal"] = tuple(goal)


def clear_worker_building_tower_state(bot, worker_id):
  tracked = bot.unit_tracker.get(worker_id)
  if not tracked:
    return
  tracked.pop("worker_state", None)
  tracked.pop("tower_goal", None)


def clear_building_tower_states(bot):
  for worker_id, tracked in list(bot.unit_tracker.items()):
    if tracked.get("worker_state") == WorkerTacticalState.BUILDING_TOWER.value:
      clear_worker_building_tower_state(bot, worker_id)


def power_tower_goals(bot, current, state):
  player = state["players"][str(current["playerId"])]
  base_pos = player["basePos"]
  base = (base_pos["x"], base_pos["z"])
  return bot.base_power_tower_goals(state, base)


def needs_defensive_power_tower(bot, state):
  if bot.defensive_power_towers <= 0:
    return False

  player = state["players"][str(state["localPlayerId"])]
  base_pos = player["basePos"]
  base = (base_pos["x"], base_pos["z"])
  return len(bot.defensive_power_towers_near_base(state, base)) < bot.defensive_power_towers


def defensive_power_towers_near_base(bot, state, base):
  return bot.power_towers_near_base(state, base)


def power_towers_near_base(bot, state, base):
  return [
    tower for tower in bot.own_units(state, POWER_TOWER_TYPE)
    if bot.hex_distance(tower["x"], tower["z"], base[0], base[1]) <= bot.defensive_power_tower_radius
  ]


def defensive_power_tower_goals(bot, state):
  player = state["players"][str(state["localPlayerId"])]
  base_pos = player["basePos"]
  base = (base_pos["x"], base_pos["z"])
  return [
    coord for coord in bot.base_power_tower_goals(state, base)
    if bot.hex_distance(coord[0], coord[1], base[0], base[1]) <= bot.defensive_power_tower_radius
  ]


def base_power_tower_goals(bot, state, base):
  preferred_distance = bot.strategy_instance.micro_value("powerTower", "basePreferredDistance", 2)
  return sorted(
    bot.all_passable_cells(state),
    key=lambda coord: (
      abs(bot.hex_distance(coord[0], coord[1], base[0], base[1]) - preferred_distance),
      bot.hex_distance(coord[0], coord[1], base[0], base[1]),
      coord[1],
      coord[0]
    )
  )


def center_power_tower_goals(bot, state, base):
  width = state.get("gridWidth", state["gridSize"])
  height = state.get("gridHeight", state["gridSize"])
  center_x = (width - 1) / 2
  center_z = (height - 1) / 2
  return sorted(
    bot.all_passable_cells(state),
    key=lambda coord: (
      abs(coord[0] - center_x) + abs(coord[1] - center_z),
      bot.hex_distance(coord[0], coord[1], base[0], base[1]),
      coord[1],
      coord[0]
    )
  )


def closest_available_worker(bot, workers, goal, assigned_workers, enemies):
  worker_safe_distance = bot.strategy_instance.micro_value(
    "powerTower",
    "workerSafeDistance",
    POWER_TOWER_WORKER_SAFE_DISTANCE
  )
  candidates = [
    worker for worker in workers
    if worker["id"] not in assigned_workers
    and bot.nearest_enemy_distance(worker["x"], worker["z"], enemies) > worker_safe_distance
  ]
  if not candidates:
    return None
  return min(candidates, key=lambda worker: (
    bot.hex_distance(worker["x"], worker["z"], goal[0], goal[1]),
    worker["id"]
  ))


def is_valid_power_tower_tile(bot, state, x, z):
  if not bot.is_passable_cell(state, x, z):
    return False
  return not any(
    unit["type"] == POWER_TOWER_TYPE and unit["x"] == x and unit["z"] == z
    for unit in state.get("units", {}).values()
  )
