from GeneralStrategy.settings import (
  ARTILLERY_COMBAT_CONTEXT_MECH_DISTANCE,
  POWER_TOWER_COMBAT_CONTEXT_RANGE,
  POWER_TOWER_TYPE,
  UnitTacticalState
)


class TacticalStateMixin:
  def unit_tactical_state(self, state, unit):
    if unit.get("isMoving"):
      return UnitTacticalState.MOVING
    if self.unit_has_combat_context(state, unit):
      return UnitTacticalState.COMBAT
    return UnitTacticalState.WAITING

  def unit_has_combat_context(self, state, unit):
    unit_type = unit.get("type")
    if unit_type == "artillery":
      combat_context_mech_distance = self.strategy_instance.micro_value(
        "artillery",
        "combatContextMechDistance",
        ARTILLERY_COMBAT_CONTEXT_MECH_DISTANCE
      )
      return (
        unit.get("attackTargetX") is not None
        or unit.get("attackWillLand") is not None
        or self.nearest_enemy_mech_distance(state, unit) <= combat_context_mech_distance
        or any(self.is_valid_artillery_target(state, unit, enemy["x"], enemy["z"]) for enemy in self.enemy_units(state))
      )
    if unit_type == "mech":
      max_steps = self.strategy_instance.micro_value("mech", "nearbyEnemyMaxSteps", 3)
      return self.nearby_mech_attack_target(state, unit, max_steps=max_steps) is not None
    if unit_type == POWER_TOWER_TYPE:
      combat_context_range = self.strategy_instance.micro_value(
        "powerTower",
        "combatContextRange",
        POWER_TOWER_COMBAT_CONTEXT_RANGE
      )
      return any(
        self.hex_distance(unit["x"], unit["z"], enemy["x"], enemy["z"]) <= combat_context_range
        for enemy in self.enemy_units(state)
      )
    return False
