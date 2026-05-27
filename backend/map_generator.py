import copy
import json
import os
import random

from hex_grid import get_hex_distance, get_neighbors


DEFAULT_MAP = {
  "name": "Default Octagon",
  "gridSize": 8,
  "players": {
    1: {
      "basePos": {"x": 0, "z": 0},
      "startingCrystals": 100,
      "baseHp": 100,
      "maxBaseHp": 100
    },
    2: {
      "basePos": {"x": 7, "z": 7},
      "startingCrystals": 100,
      "baseHp": 100,
      "maxBaseHp": 100
    }
  },
  "resources": [
    {"x": 2, "z": 2, "gold": 200},
    {"x": 5, "z": 5, "gold": 200},
    {"x": 2, "z": 5, "gold": 200},
    {"x": 5, "z": 2, "gold": 200},
    {"x": 0, "z": 4, "gold": 200},
    {"x": 4, "z": 0, "gold": 200},
    {"x": 7, "z": 3, "gold": 200},
    {"x": 3, "z": 7, "gold": 200}
  ],
  "startingUnits": [
    {"type": "worker", "owner": 1, "x": 1, "z": 0},
    {"type": "worker", "owner": 2, "x": 6, "z": 7}
  ]
}


def initalize_map():
  return copy.deepcopy(DEFAULT_MAP)


def load_random_map_settings():
  settings_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "map.json")
  defaults = {
    "width": {"target": 8, "min": 6, "max": 12},
    "height": {"target": 8, "min": 6, "max": 12},
    "numResources": {"target": 8, "min": 0, "max": 20},
    "numObsticale": {"target": 6, "min": 0, "max": 20},
    "randomPlayer": {"target": False, "min": False, "max": True}
  }
  try:
    with open(settings_path, "r") as f:
      settings = json.load(f)
  except FileNotFoundError:
    return defaults

  return {**defaults, **settings}


def setting_target(settings, key, fallback=None):
  value = settings.get(key, fallback)
  if isinstance(value, dict):
    target = value.get("target", fallback)
    min_value = value.get("min")
    max_value = value.get("max")
    if isinstance(target, bool):
      return target
    if min_value is not None and target < min_value:
      return min_value
    if max_value is not None and target > max_value:
      return max_value
    return target
  return value


def manhattan_distance(a, b):
  return abs(a["x"] - b["x"]) + abs(a["z"] - b["z"])


def generate_random_map():
  settings = load_random_map_settings()
  if "gridSize" in settings:
    grid_size = setting_target(settings, "gridSize")
    width, height = grid_size if isinstance(grid_size, list) else (grid_size, grid_size)
  else:
    width = setting_target(settings, "width", 8)
    height = setting_target(settings, "height", 8)
  width = int(width)
  height = int(height)
  if width != height:
    raise ValueError("Only square maps are currently supported by the game engine")

  num_resources = int(setting_target(settings, "numResources", 8))
  num_obstacles = int(setting_target(settings, "numObsticale", setting_target(settings, "numObstacles", 0)))
  player_configs = generate_player_configs(width, height, bool(setting_target(settings, "randomPlayer", False)))
  obstacles = generate_obstacles(width, height, player_configs, num_obstacles)
  resources = generate_balanced_resources(width, height, player_configs, num_resources, obstacles)

  return {
    "name": "RandomMap",
    "gridSize": width,
    "players": player_configs,
    "obstacles": obstacles,
    "resources": resources,
    "startingUnits": generate_starting_units(width, player_configs)
  }


def generate_player_configs(width, height, random_player):
  if not random_player:
    return {
      1: {
        "basePos": {"x": 0, "z": 0},
        "startingCrystals": 100,
        "baseHp": 100,
        "maxBaseHp": 100
      },
      2: {
        "basePos": {"x": width - 1, "z": height - 1},
        "startingCrystals": 100,
        "baseHp": 100,
        "maxBaseHp": 100
      }
    }

  all_cells = [{"x": x, "z": z} for x in range(width) for z in range(height)]
  for _ in range(500):
    p1 = random.choice(all_cells)
    p2 = random.choice(all_cells)
    if p1 == p2:
      continue
    if manhattan_distance(p1, p2) < width + height - 4:
      continue
    return {
      1: {
        "basePos": p1,
        "startingCrystals": 100,
        "baseHp": 100,
        "maxBaseHp": 100
      },
      2: {
        "basePos": p2,
        "startingCrystals": 100,
        "baseHp": 100,
        "maxBaseHp": 100
      }
    }

  return copy.deepcopy(DEFAULT_MAP["players"])


def generate_obstacles(width, height, player_configs, num_obstacles):
  if num_obstacles <= 0:
    return []

  candidates = obstacle_candidates(width, height, player_configs)
  if len(candidates) < num_obstacles:
    raise ValueError("Not enough valid obstacle cells for requested numObsticale")

  for _ in range(2000):
    selected = random.sample(candidates, num_obstacles)
    if bases_are_connected(width, player_configs, selected):
      return [{"x": cell["x"], "z": cell["z"]} for cell in selected]

  raise ValueError("Could not generate obstacles while preserving a path between bases")


def obstacle_candidates(width, height, player_configs):
  bases = [player["basePos"] for player in player_configs.values()]
  candidates = []
  for x in range(width):
    for z in range(height):
      if any(base["x"] == x and base["z"] == z for base in bases):
        continue
      if any(get_hex_distance(x, z, base["x"], base["z"]) <= 1 for base in bases):
        continue
      candidates.append({"x": x, "z": z})
  return candidates


def bases_are_connected(width, player_configs, obstacles):
  base_positions = [player["basePos"] for player in player_configs.values()]
  if len(base_positions) < 2:
    return True

  blocked = {(cell["x"], cell["z"]) for cell in obstacles}
  start = (base_positions[0]["x"], base_positions[0]["z"])
  target = (base_positions[1]["x"], base_positions[1]["z"])
  queue = [start]
  visited = {start}

  while queue:
    x, z = queue.pop(0)
    if (x, z) == target:
      return True

    for nx, nz in get_neighbors(x, z, width):
      if (nx, nz) in blocked or (nx, nz) in visited:
        continue
      visited.add((nx, nz))
      queue.append((nx, nz))

  return False


def generate_balanced_resources(width, height, player_configs, num_resources, obstacles=None):
  candidates = resource_candidates(width, height, player_configs, obstacles or [])
  if len(candidates) < num_resources:
    raise ValueError("Not enough valid resource cells for requested numResources")

  for _ in range(2000):
    selected = random.sample(candidates, num_resources)
    if resource_distance_diff(selected, player_configs) <= 3:
      return [
        {"x": cell["x"], "z": cell["z"], "gold": 200}
        for cell in selected
      ]

  best = min(
    (random.sample(candidates, num_resources) for _ in range(500)),
    key=lambda cells: resource_distance_diff(cells, player_configs)
  )
  if resource_distance_diff(best, player_configs) > 3:
    raise ValueError("Could not generate a resource layout balanced within a Manhattan distance difference of 3")
  return [
    {"x": cell["x"], "z": cell["z"], "gold": 200}
    for cell in best
  ]


def resource_candidates(width, height, player_configs, obstacles):
  bases = [player["basePos"] for player in player_configs.values()]
  blocked = {(cell["x"], cell["z"]) for cell in obstacles}
  candidates = []
  for x in range(width):
    for z in range(height):
      if (x, z) in blocked:
        continue
      if any(base["x"] == x and base["z"] == z for base in bases):
        continue
      if any(get_hex_distance(x, z, base["x"], base["z"]) <= 2 for base in bases):
        continue
      candidates.append({"x": x, "z": z})
  return candidates


def resource_distance_diff(resources, player_configs):
  p1_base = player_configs[1]["basePos"]
  p2_base = player_configs[2]["basePos"]
  p1_total = sum(manhattan_distance(p1_base, resource) for resource in resources)
  p2_total = sum(manhattan_distance(p2_base, resource) for resource in resources)
  return abs(p1_total - p2_total)


def generate_starting_units(width, player_configs):
  units = []
  for owner, player in player_configs.items():
    base = player["basePos"]
    spawn = first_spawn_cell(width, base)
    units.append({"type": "worker", "owner": owner, "x": spawn["x"], "z": spawn["z"]})
  return units


def first_spawn_cell(width, base):
  for x, z in get_neighbors(base["x"], base["z"], width):
    return {"x": x, "z": z}
  return {"x": base["x"], "z": base["z"]}
