from GeneralStrategy.settings import DEFAULT_UNIT_PRIORITY, UNIT_PRIORITY
from GeneralStrategy.navigation import hex_distance


def unit_priority(unit):
  return UNIT_PRIORITY.get(unit["type"], DEFAULT_UNIT_PRIORITY)


class UnitQueriesMixin:
  def unit_priority(self, unit):
    return unit_priority(unit)

  def own_units(self, state, unit_type=None, stationary=False):
    units = [
      unit for unit in state.get("units", {}).values()
      if unit["owner"] == state["localPlayerId"]
    ]
    if unit_type:
      units = [unit for unit in units if unit["type"] == unit_type]
    if stationary:
      units = [unit for unit in units if not unit["isMoving"]]
    return units

  def enemy_units(self, state, unit_type=None, stationary=False):
    units = [
      unit for unit in state.get("units", {}).values()
      if unit["owner"] != state["localPlayerId"]
    ]
    if unit_type:
      units = [unit for unit in units if unit["type"] == unit_type]
    if stationary:
      units = [unit for unit in units if not unit["isMoving"]]
    return units

  def closest_target(self, unit, targets):
    if not targets:
      return None
    return min(
      targets,
      key=lambda target: (
        hex_distance(unit["x"], unit["z"], target["x"], target["z"]),
        3 if target.get("type") == "base" else unit_priority(target),
        target.get("hp", 999)
      )
    )

  def closest_unit(self, unit, units):
    if not units:
      return None
    return min(units, key=lambda candidate: hex_distance(unit["x"], unit["z"], candidate["x"], candidate["z"]))

  def resource_cells(self, state):
    cells = []
    for row in state["grid"]:
      for cell in row:
        if cell["type"] == "resource" and cell["gold"] > 0:
          cells.append(cell)
    return cells

  def nearest_enemy_distance(self, x, z, enemies):
    if not enemies:
      return 99
    return min(hex_distance(x, z, enemy["x"], enemy["z"]) for enemy in enemies)

  def enemy_base_target(self, current, state):
    for player_id, player in state.get("players", {}).items():
      if int(player_id) != current["playerId"] and player.get("baseHp", 0) > 0:
        base_pos = player["basePos"]
        return {
          "type": "base",
          "x": base_pos["x"],
          "z": base_pos["z"],
          "hp": player.get("baseHp", 0)
        }
    return None
