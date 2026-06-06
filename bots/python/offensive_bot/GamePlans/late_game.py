from GamePlans.game_plan import GamePlan
from GeneralStrategy.settings import BuildPhase


class LateGamePlan(GamePlan):
  phase = BuildPhase.LATE_GAME

  def choose_build(self, bot, state, crystals):
    return self.choose_combat_build(bot, state, crystals)

  def choose_upgrade(self, bot, state, crystals, owned_levels):
    tech_tree = state.get("techTree", {})
    if not bot.own_units(state, "mech"):
      return None

    upgrade_rules = bot.strategy_instance.phase_value(self.phase, "upgrades", [])
    candidates = []
    for rule in upgrade_rules:
      target_unit = rule.get("targetUnit")
      target_property = rule.get("targetProperty")
      for name, upgrade in tech_tree.items():
        if upgrade.get("targetUnit") != target_unit:
          continue
        if upgrade.get("targetProperty") != target_property:
          continue

        level = owned_levels.get(name, 0)
        cost = upgrade.get("initialCost", 0) + level * upgrade.get("costIncrease", 0)
        if cost > crystals:
          continue

        candidates.append((
          level,
          cost,
          name
        ))

    if not candidates:
      return None
    return min(candidates)[2]
