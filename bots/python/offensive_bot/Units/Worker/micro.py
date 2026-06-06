from GeneralStrategy.settings import (
  BuildPhase,
  POWER_TOWER_TYPE,
  UNIT_COSTS,
  WORKER_RESOURCE_ENEMY_DANGER_RADIUS,
  WORKER_RESOURCE_ENEMY_DANGER_WEIGHT,
  WORKER_RESOURCE_TOWER_DANGER,
  WORKER_SAFE_RESOURCE_ENEMY_DISTANCE
)


GATHER_SPREAD_RADIUS = 4
GATHER_SPREAD_WEIGHT = 4
GATHER_RESERVED_TILE_PENALTY = 1000


def plan_worker_orders(bot, current, state):
  workers = bot.own_units(state, "worker", stationary=True)
  all_workers = bot.own_units(state, "worker")
  enemies = bot.enemy_units(state)
  resources = bot.resource_cells(state)
  orders = []
  assigned_workers = set()
  planned_tower_tiles = set()
  planned_worker_tiles = set()
  reserved_gather_tiles = {
    worker_destination(worker)
    for worker in all_workers
    if worker.get("isMoving") and worker.get("targetX") is not None and worker.get("targetZ") is not None
  }

  player = state["players"][str(current["playerId"])]
  if bot.build_strategy_phase(state) == BuildPhase.MID_GAME and player.get("crystals", 0) >= UNIT_COSTS[POWER_TOWER_TYPE]:
    for order in bot.plan_power_tower_orders(current, state, workers, enemies, planned_tower_tiles):
      worker_id = bot.order_unit_id(order)
      if worker_id:
        assigned_workers.add(worker_id)
      orders.append(order)

  for worker in sorted(workers, key=lambda unit: unit["id"]):
    if worker["id"] in assigned_workers:
      continue

    other_worker_tiles = {
      worker_destination(other)
      for other in all_workers
      if other["id"] != worker["id"]
    }
    reserved_tiles = reserved_gather_tiles | planned_worker_tiles | other_worker_tiles

    for target in bot.choose_resource_targets(worker, state, resources, enemies, reserved_tiles):
      move = bot.choose_worker_step(worker, state, target, enemies, reserved_tiles)
      if move:
        orders.append(bot.move_order(worker["id"], move[0], move[1]))
        planned_worker_tiles.add(move)
        reserved_gather_tiles.add(move)
        break
      if target:
        reserved_gather_tiles.add((worker["x"], worker["z"]))
        break

  return orders


def worker_destination(worker):
  if worker.get("isMoving") and worker.get("targetX") is not None and worker.get("targetZ") is not None:
    return worker["targetX"], worker["targetZ"]
  return worker["x"], worker["z"]


def choose_resource_targets(bot, worker, state, resources, enemies, reserved_tiles=None):
  if not resources:
    return []

  reserved_tiles = reserved_tiles or set()
  avoid_enemy_towers = bot.strategy_instance.micro_value("worker", "avoidEnemyTowers", True)

  def score(cell):
    distance = bot.hex_distance(worker["x"], worker["z"], cell["x"], cell["z"])
    danger_radius = bot.strategy_instance.micro_value("worker", "resourceEnemyDangerRadius", WORKER_RESOURCE_ENEMY_DANGER_RADIUS)
    danger_weight = bot.strategy_instance.micro_value("worker", "resourceEnemyDangerWeight", WORKER_RESOURCE_ENEMY_DANGER_WEIGHT)
    tower_danger_value = bot.strategy_instance.micro_value("worker", "resourceTowerDanger", WORKER_RESOURCE_TOWER_DANGER)
    danger = max(0, danger_radius - bot.nearest_enemy_distance(cell["x"], cell["z"], enemies))
    tower_danger = tower_danger_value if bot.is_enemy_power_tower_zone(state, cell["x"], cell["z"]) else 0
    richness = cell["gold"] / max(1, cell["maxGold"])
    goals = bot.adjacent_passable_cells(state, cell["x"], cell["z"], avoid_enemy_towers=avoid_enemy_towers)
    spread = min((gather_tile_crowding(bot, goal, reserved_tiles) for goal in goals), default=0)
    return distance + danger * danger_weight + tower_danger + spread - richness

  return sorted(resources, key=score)


def choose_worker_step(bot, worker, state, target, enemies, reserved_tiles=None):
  current_enemy_distance = bot.nearest_enemy_distance(worker["x"], worker["z"], enemies)
  safe_resource_enemy_distance = bot.strategy_instance.micro_value(
    "worker",
    "safeResourceEnemyDistance",
    WORKER_SAFE_RESOURCE_ENEMY_DISTANCE
  )
  resource_adjacent_distance = bot.strategy_instance.micro_value("worker", "resourceAdjacentDistance", 1)
  avoid_enemy_towers = bot.strategy_instance.micro_value("worker", "avoidEnemyTowers", True)
  reserved_tiles = reserved_tiles or set()

  if (
    target
    and bot.hex_distance(worker["x"], worker["z"], target["x"], target["z"]) == resource_adjacent_distance
    and current_enemy_distance > safe_resource_enemy_distance
    and not bot.is_enemy_power_tower_zone(state, worker["x"], worker["z"])
    and gather_tile_crowding(bot, (worker["x"], worker["z"]), reserved_tiles) == 0
  ):
    return None

  if target:
    goals = bot.adjacent_passable_cells(state, target["x"], target["z"], avoid_enemy_towers=avoid_enemy_towers)
    goals = sorted(goals, key=lambda goal: (
      gather_tile_crowding(bot, goal, reserved_tiles),
      bot.hex_distance(worker["x"], worker["z"], goal[0], goal[1]),
      goal[1],
      goal[0]
    ))
    for goal in goals:
      if goal in reserved_tiles and goal != (worker["x"], worker["z"]):
        continue
      step = bot.step_towards_any(state, worker, {goal}, avoid_enemy_towers=avoid_enemy_towers)
      if step and step not in reserved_tiles:
        return step
      if step is None and (worker["x"], worker["z"]) == goal and goal not in reserved_tiles:
        return None
    return None

  return bot.safest_passable_neighbor(state, worker, enemies, avoid_enemy_towers=avoid_enemy_towers)


def gather_tile_crowding(bot, tile, reserved_tiles):
  if tile in reserved_tiles:
    return GATHER_RESERVED_TILE_PENALTY
  if not reserved_tiles:
    return 0
  return sum(
    max(0, GATHER_SPREAD_RADIUS - bot.hex_distance(tile[0], tile[1], reserved[0], reserved[1])) * GATHER_SPREAD_WEIGHT
    for reserved in reserved_tiles
  )
