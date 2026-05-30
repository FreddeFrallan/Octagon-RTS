import copy
import json
import os
import random

import numpy as np

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


PLAYER_DEFAULTS = {
  1: {"basePos": {"x": 0, "z": 0}, "startingCrystals": 100, "baseHp": 100, "maxBaseHp": 100},
  2: {"basePos": {"x": 7, "z": 7}, "startingCrystals": 100, "baseHp": 100, "maxBaseHp": 100},
  3: {"basePos": {"x": 7, "z": 0}, "startingCrystals": 100, "baseHp": 100, "maxBaseHp": 100},
  4: {"basePos": {"x": 0, "z": 7}, "startingCrystals": 100, "baseHp": 100, "maxBaseHp": 100}
}


def initalize_map(player_count=2):
  map_data = copy.deepcopy(DEFAULT_MAP)
  player_count = max(2, min(int(player_count), 4))
  map_data["players"] = {
    player_id: copy.deepcopy(PLAYER_DEFAULTS[player_id])
    for player_id in range(1, player_count + 1)
  }
  map_data["startingUnits"] = generate_starting_units(
    map_data["gridSize"],
    map_data["gridSize"],
    map_data["players"]
  )
  return map_data


def load_random_map_settings():
  settings_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "map.json")
  defaults = {
    "width": {"target": 8, "min": 6, "max": 12},
    "height": {"target": 8, "min": 6, "max": 12},
    "numResources": {"target": 8, "min": 0, "max": 20},
    "numObsticale": {"target": 6, "min": 0, "max": 20},
    "randomPlayer": {"target": False, "options": [False, True]},
    "fogOfWar": {"target": False, "options": [False, True]}
  }
  try:
    with open(settings_path, "r") as f:
      settings = json.load(f)
  except FileNotFoundError:
    return defaults

  return {**defaults, **settings}


def save_random_map_settings(settings):
  settings_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "map.json")
  normalized = validate_random_map_settings(settings)
  with open(settings_path, "w") as f:
    json.dump(normalized, f, indent=2)
    f.write("\n")
  return normalized


def validate_random_map_settings(settings):
  defaults = load_random_map_settings()
  normalized = {}

  for key, default_value in defaults.items():
    value = settings.get(key, default_value)
    if not isinstance(value, dict):
      value = {"target": value}

    if "options" in default_value:
      options = value.get("options", default_value["options"])
      target = value.get("target", default_value["target"])
      if target not in options:
        target = default_value["target"]
      normalized[key] = {"target": target, "options": options}
      continue

    min_value = value.get("min", default_value["min"])
    max_value = value.get("max", default_value["max"])
    target = value.get("target", default_value["target"])
    if target < min_value:
      target = min_value
    if target > max_value:
      target = max_value
    normalized[key] = {"target": target, "min": min_value, "max": max_value}

  return normalized


def setting_target(settings, key, fallback=None):
  value = settings.get(key, fallback)
  if isinstance(value, dict):
    target = value.get("target", fallback)
    options = value.get("options")
    if options is not None:
      return target if target in options else options[0]
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


def generate_random_map(player_count=2):
  settings = load_random_map_settings()
  if "gridSize" in settings:
    grid_size = setting_target(settings, "gridSize")
    width, height = grid_size if isinstance(grid_size, list) else (grid_size, grid_size)
  else:
    width = setting_target(settings, "width", 8)
    height = setting_target(settings, "height", 8)
  width = int(width)
  height = int(height)

  num_resources = int(setting_target(settings, "numResources", 8))
  num_obstacles = int(setting_target(settings, "numObsticale", setting_target(settings, "numObstacles", 0)))
  player_count = max(2, min(int(player_count), 4))
  player_configs = generate_player_configs(width, height, bool(setting_target(settings, "randomPlayer", False)), player_count)
  obstacles = generate_obstacles(width, height, player_configs, num_obstacles)
  resources = generate_balanced_resources(width, height, player_configs, num_resources, obstacles)
  fog_of_war = bool(setting_target(settings, "fogOfWar", False))

  return {
    "name": "CustomMap",
    "fogOfWar": fog_of_war,
    "gridSize": width,
    "gridWidth": width,
    "gridHeight": height,
    "players": player_configs,
    "obstacles": obstacles,
    "resources": resources,
    "startingUnits": generate_starting_units(width, height, player_configs)
  }


def generate_player_configs(width, height, random_player, player_count=2):
  positions = farthest_cell_set(width, height, player_count)
  if not random_player:
    return {
      player_id: {
        "basePos": positions[player_id - 1],
        "startingCrystals": 100,
        "baseHp": 100,
        "maxBaseHp": 100
      }
      for player_id in range(1, player_count + 1)
    }

  all_cells = [{"x": x, "z": z} for x in range(width) for z in range(height)]
  for _ in range(500):
    positions = random.sample(all_cells, player_count)
    if min_pair_distance(positions) < max(3, min(width, height) // 2):
      continue
    return {
      player_id: {
        "basePos": positions[player_id - 1],
        "startingCrystals": 100,
        "baseHp": 100,
        "maxBaseHp": 100
      }
      for player_id in range(1, player_count + 1)
    }

  return generate_player_configs(width, height, False, player_count)


def min_pair_distance(cells):
  best = None
  for i, first in enumerate(cells):
    for second in cells[i + 1:]:
      distance = get_hex_distance(first["x"], first["z"], second["x"], second["z"])
      best = distance if best is None else min(best, distance)
  return best or 0


def farthest_cell_set(width, height, count):
  cells = [{"x": x, "z": z} for x in range(width) for z in range(height)]
  selected = [cells[0]]
  while len(selected) < count:
    candidate = max(
      (cell for cell in cells if cell not in selected),
      key=lambda cell: min(get_hex_distance(cell["x"], cell["z"], other["x"], other["z"]) for other in selected)
    )
    selected.append(candidate)
  return [{"x": cell["x"], "z": cell["z"]} for cell in selected]


def generate_obstacles(width, height, player_configs, num_obstacles):
  if num_obstacles <= 0:
    return []

  candidates = obstacle_candidates(width, height, player_configs)
  if len(candidates) < num_obstacles:
    raise ValueError("Not enough valid obstacle cells for requested numObsticale")

  for _ in range(10):
    selected = []
    available = list(candidates)

    while len(selected) < num_obstacles:
      placed = False
      for _ in range(20):
        if not available:
          break

        candidate = random.choice(available)
        available.remove(candidate)
        next_selected = selected + [candidate]
        if bases_are_connected(width, height, player_configs, next_selected):
          selected.append(candidate)
          placed = True
          break

      if not placed:
        break

    if len(selected) == num_obstacles:
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


def bases_are_connected(width, height, player_configs, obstacles):
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

    for nx, nz in get_neighbors(x, z, width, height):
      if (nx, nz) in blocked or (nx, nz) in visited:
        continue
      visited.add((nx, nz))
      queue.append((nx, nz))

  return False


def generate_balanced_resources(width, height, player_configs, num_resources, obstacles=None):
  candidates = resource_candidates(width, height, player_configs, obstacles or [])
  if len(candidates) < num_resources:
    raise ValueError("Not enough valid resource cells for requested numResources")

  distance_vectors = resource_distance_vectors(candidates, player_configs)
  random_count = num_resources // 2
  greedy_count = num_resources - random_count
  best = None
  best_loss = None

  for _ in range(100):
    available = list(candidates)
    selected = random.sample(available, random_count) if random_count else []
    selected_total = sum_resource_vectors(selected, distance_vectors)
    selected_coords = {(cell["x"], cell["z"]) for cell in selected}
    available = [
      cell for cell in available
      if (cell["x"], cell["z"]) not in selected_coords
    ]

    for _ in range(greedy_count):
      candidate = min(
        available,
        key=lambda cell: resource_distance_loss(
          selected_total + distance_vectors[cell_coord(cell)]
        )
      )
      selected.append(candidate)
      selected_total = selected_total + distance_vectors[cell_coord(candidate)]
      available.remove(candidate)

    loss = resource_distance_loss(selected_total)
    if best is None or loss < best_loss:
      best = selected
      best_loss = loss
      if best_loss == 0:
        break

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


def cell_coord(cell):
  return cell["x"], cell["z"]


def resource_distance_vectors(candidates, player_configs):
  players = list(player_configs.values())
  return {
    cell_coord(cell): np.array([
      manhattan_distance(player["basePos"], cell)
      for player in players
    ], dtype=np.int16)
    for cell in candidates
  }


def sum_resource_vectors(resources, distance_vectors):
  if not resources:
    vector_length = len(next(iter(distance_vectors.values()), []))
    return np.zeros(vector_length, dtype=np.int32)
  return np.sum(
    np.array([distance_vectors[cell_coord(cell)] for cell in resources], dtype=np.int32),
    axis=0
  )


def resource_distance_loss(total_distances):
  if total_distances.size == 0:
    return 0
  return int(np.max(total_distances) - np.min(total_distances))


def resource_distance_diff(resources, player_configs):
  candidates = resources if resources else [{"x": 0, "z": 0}]
  distance_vectors = resource_distance_vectors(candidates, player_configs)
  return resource_distance_loss(sum_resource_vectors(resources, distance_vectors))


def generate_starting_units(width, height, player_configs):
  units = []
  for owner, player in player_configs.items():
    base = player["basePos"]
    spawn = first_spawn_cell(width, height, base)
    units.append({"type": "worker", "owner": owner, "x": spawn["x"], "z": spawn["z"]})
  return units


def first_spawn_cell(width, height, base):
  for x, z in get_neighbors(base["x"], base["z"], width, height):
    return {"x": x, "z": z}
  return {"x": base["x"], "z": base["z"]}
