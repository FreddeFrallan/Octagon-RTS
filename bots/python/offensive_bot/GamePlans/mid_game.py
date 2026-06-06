from GamePlans.game_plan import GamePlan
from GeneralStrategy.settings import (
  BuildPhase,
  PASSIVE_INCOME_UPGRADE,
  POWER_TOWER_TYPE,
  UNIT_COSTS
)


class MidGamePlan(GamePlan):
  phase = BuildPhase.MID_GAME

  def choose_build(self, bot, state, crystals):
    if bot.strategy_instance.phase_value(self.phase, "reserveForPowerTower", True) and bot.should_reserve_for_power_tower(state, crystals):
      return None
    reserve_combat_unit = bot.strategy_instance.phase_value(self.phase, "reserveCombatUnit", "mech")
    reserve_combat_cost = UNIT_COSTS.get(reserve_combat_unit, 0)
    if bot.mid_base_power_towers_remaining(state) > 0 and crystals < UNIT_COSTS[POWER_TOWER_TYPE] + reserve_combat_cost:
      return None

    player = state["players"][str(state["localPlayerId"])]
    if self.needs_mid_game_passive_income(bot, player.get("techUpgrades", {})):
      return None

    return self.choose_combat_build(bot, state, crystals)

  def choose_upgrade(self, bot, state, crystals, owned_levels):
    if not self.needs_mid_game_passive_income(bot, owned_levels):
      return None

    cost = self.passive_income_upgrade_cost(state, owned_levels)
    if cost is None or cost > crystals:
      return None
    return PASSIVE_INCOME_UPGRADE
