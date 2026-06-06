from GamePlans.game_plan import GamePlan
from GeneralStrategy.settings import BuildPhase


DEFAULT_COUNTER_WEIGHT = 1.0


class LateGamePlan(GamePlan):
  phase = BuildPhase.LATE_GAME

  def choose_build(self, bot, state, crystals):
    return self.choose_combat_build(bot, state, crystals)

  def choose_upgrade(self, bot, state, crystals, owned_levels):
    tech_tree = state.get("techTree", {})
    if not bot.own_units(state, "mech"):
      return None

    upgrade_rules = bot.strategy_instance.phase_value(self.phase, "upgrades", {})
    candidates = []
    for name, upgrade in tech_tree.items():
      rule = upgrade_rule_for_name(name, upgrade, upgrade_rules)
      level = owned_levels.get(name, 0)
      max_level = rule.get("maxLevel")
      if max_level is not None and level >= max_level:
        continue

      cost = upgrade.get("initialCost", 0) + level * upgrade.get("costIncrease", 0)
      if cost > crystals:
        continue

      counter_weight = clamp_counter_weight(rule.get("counterWeight", rule.get("lossWeight", DEFAULT_COUNTER_WEIGHT)))
      candidates.append((
        (level + 1) * counter_weight,
        cost,
        name
      ))

    if not candidates:
      return None
    return min(candidates)[2]


def upgrade_rule_for_name(name, upgrade, upgrade_rules):
  if isinstance(upgrade_rules, dict):
    rule = upgrade_rules.get(name, {})
    return rule if isinstance(rule, dict) else {}

  for rule in upgrade_rules or []:
    if not isinstance(rule, dict):
      continue
    upgrade_name = rule.get("upgradeName")
    if upgrade_name and name == upgrade_name:
      return rule

    target_unit = rule.get("targetUnit")
    target_property = rule.get("targetProperty")
    if (
      target_unit
      and target_property
      and upgrade.get("targetUnit") == target_unit
      and upgrade.get("targetProperty") == target_property
    ):
      return rule

  return {}


def clamp_counter_weight(value):
  try:
    parsed = float(value)
  except (TypeError, ValueError):
    return DEFAULT_COUNTER_WEIGHT
  return max(0.0, min(1.0, parsed))
