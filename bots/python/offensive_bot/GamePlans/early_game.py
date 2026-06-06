from GamePlans.game_plan import GamePlan
from GeneralStrategy.settings import BuildPhase, UNIT_COSTS


class EarlyGamePlan(GamePlan):
  phase = BuildPhase.EARLY_GAME

  def choose_build(self, bot, state, crystals):
    own = bot.own_units(state)
    counts = {}
    for unit in own:
      counts[unit["type"]] = counts.get(unit["type"], 0) + 1

    for step in bot.strategy_instance.phase_build_order(self.phase):
      unit_type = step.get("unitType")
      target_count = step.get("targetCount", 0)
      if unit_type in UNIT_COSTS and counts.get(unit_type, 0) < target_count and crystals >= UNIT_COSTS[unit_type]:
        return unit_type
    return None
