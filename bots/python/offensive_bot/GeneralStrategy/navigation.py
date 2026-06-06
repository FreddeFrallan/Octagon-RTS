from collections import deque

from GeneralStrategy.settings import ENEMY_POWER_TOWER_AVOID_RADIUS, POWER_TOWER_TYPE


def offset_to_cube(col, row):
  x = col - (row - (row & 1)) // 2
  z = row
  y = -x - z
  return x, y, z


def hex_distance(ax, az, bx, bz):
  acx, acy, acz = offset_to_cube(ax, az)
  bcx, bcy, bcz = offset_to_cube(bx, bz)
  return max(abs(acx - bcx), abs(acy - bcy), abs(acz - bcz))


def neighbors(x, z, grid_size=8, grid_height=None):
  if grid_height is None:
    grid_height = grid_size
  if z % 2 == 0:
    coords = [(x-1, z), (x+1, z), (x-1, z-1), (x, z-1), (x-1, z+1), (x, z+1)]
  else:
    coords = [(x-1, z), (x+1, z), (x, z-1), (x+1, z-1), (x, z+1), (x+1, z+1)]
  return [(nx, nz) for nx, nz in coords if 0 <= nx < grid_size and 0 <= nz < grid_height]


class NavigationMixin:
  def hex_distance(self, ax, az, bx, bz):
    return hex_distance(ax, az, bx, bz)

  def step_towards(self, state, unit, target_x, target_z, keep_distance=0, avoid_enemy_towers=False):
    if keep_distance:
      return self.step_to_standoff(
        state,
        unit,
        target_x,
        target_z,
        keep_distance,
        keep_distance,
        avoid_enemy_towers=avoid_enemy_towers
      )

    return self.step_towards_any(state, unit, {(target_x, target_z)}, avoid_enemy_towers=avoid_enemy_towers)

  def step_to_standoff(self, state, unit, target_x, target_z, min_range, max_range, avoid_enemy_towers=False):
    current_distance = hex_distance(unit["x"], unit["z"], target_x, target_z)
    if min_range <= current_distance <= max_range:
      return None

    goals = {
      (x, z)
      for x, z in self.all_passable_cells(state, avoid_enemy_towers=avoid_enemy_towers)
      if min_range <= hex_distance(x, z, target_x, target_z) <= max_range
    }
    return self.step_towards_any(state, unit, goals, avoid_enemy_towers=avoid_enemy_towers)

  def step_towards_any(self, state, unit, goals, avoid_enemy_towers=False):
    if not goals:
      return None

    start = (unit["x"], unit["z"])
    if start in goals:
      return None

    visited = {start}
    queue = deque()
    for nx, nz in self.passable_neighbors(state, start[0], start[1], avoid_enemy_towers=avoid_enemy_towers):
      first_step = (nx, nz)
      if first_step in goals:
        return first_step
      visited.add(first_step)
      queue.append((first_step, first_step))

    while queue:
      (x, z), first_step = queue.popleft()
      for nx, nz in self.passable_neighbors(state, x, z, avoid_enemy_towers=avoid_enemy_towers):
        coord = (nx, nz)
        if coord in visited:
          continue
        if coord in goals:
          return first_step
        visited.add(coord)
        queue.append((coord, first_step))

    return None

  def path_distance(self, state, unit, target_x, target_z, max_steps=None, avoid_enemy_towers=False):
    start = (unit["x"], unit["z"])
    target = (target_x, target_z)
    if start == target:
      return 0

    visited = {start}
    queue = deque([(start, 0)])
    while queue:
      (x, z), distance = queue.popleft()
      if max_steps is not None and distance >= max_steps:
        continue

      for nx, nz in self.passable_neighbors(state, x, z, avoid_enemy_towers=avoid_enemy_towers):
        coord = (nx, nz)
        if coord in visited:
          continue
        next_distance = distance + 1
        if coord == target:
          return next_distance
        visited.add(coord)
        queue.append((coord, next_distance))

    return None

  def passable_neighbors(self, state, x, z, avoid_enemy_towers=False):
    return [
      (nx, nz) for nx, nz in neighbors(x, z, state.get("gridWidth", state["gridSize"]), state.get("gridHeight", state["gridSize"]))
      if self.is_passable_cell(state, nx, nz)
      and (not avoid_enemy_towers or not self.is_enemy_power_tower_zone(state, nx, nz))
    ]

  def adjacent_passable_cells(self, state, x, z, avoid_enemy_towers=False):
    return {
      (nx, nz)
      for nx, nz in neighbors(x, z, state.get("gridWidth", state["gridSize"]), state.get("gridHeight", state["gridSize"]))
      if self.is_passable_cell(state, nx, nz)
      and (not avoid_enemy_towers or not self.is_enemy_power_tower_zone(state, nx, nz))
    }

  def all_passable_cells(self, state, avoid_enemy_towers=False):
    return [
      (x, z)
      for x in range(state.get("gridWidth", state["gridSize"]))
      for z in range(state.get("gridHeight", state["gridSize"]))
      if self.is_passable_cell(state, x, z)
      and (not avoid_enemy_towers or not self.is_enemy_power_tower_zone(state, x, z))
    ]

  def is_passable_cell(self, state, x, z):
    return state["grid"][x][z]["type"] not in ("base", "obstacle", "resource")

  def safest_passable_neighbor(self, state, unit, enemies, avoid_enemy_towers=False):
    candidates = self.passable_neighbors(state, unit["x"], unit["z"], avoid_enemy_towers=avoid_enemy_towers)
    if not candidates and avoid_enemy_towers:
      candidates = self.passable_neighbors(state, unit["x"], unit["z"])
    if not candidates:
      return None
    return max(candidates, key=lambda coord: (
      0 if self.is_enemy_power_tower_zone(state, coord[0], coord[1]) else 1,
      self.nearest_enemy_distance(coord[0], coord[1], enemies)
    ))

  def is_enemy_power_tower_zone(self, state, x, z):
    return any(
      hex_distance(x, z, tower["x"], tower["z"]) <= ENEMY_POWER_TOWER_AVOID_RADIUS
      for tower in self.enemy_units(state, POWER_TOWER_TYPE, stationary=True)
    )
