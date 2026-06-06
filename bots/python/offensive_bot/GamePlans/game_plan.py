from abc import ABC, abstractmethod

from GeneralStrategy.settings import COMBAT_MIN_ARTILLERY, COMBAT_MIN_MECHS_BEFORE_DEFAULT, COMBAT_OPENING_ARTILLERY_MIN_MECHS, PASSIVE_INCOME_UPGRADE, UNIT_COSTS


class GamePlan(ABC):
  phase = None

  @abstractmethod
  def choose_build(self, bot, state, crystals):
    pass

  def choose_upgrade(self, bot, state, crystals, owned_levels):
    return None

  def choose_combat_build(self, bot, state, crystals):
    own = bot.own_units(state)
    mech_count = sum(1 for unit in own if unit["type"] == "mech")
    artillery_count = sum(1 for unit in own if unit["type"] == "artillery")
    combat_order = bot.strategy_instance.combat_build_order()
    opening_artillery_min_mechs = combat_order.get("openingArtilleryMinMechs", COMBAT_OPENING_ARTILLERY_MIN_MECHS)
    min_artillery = combat_order.get("minArtillery", COMBAT_MIN_ARTILLERY)
    min_mechs_before_default = combat_order.get("minMechsBeforeDefault", COMBAT_MIN_MECHS_BEFORE_DEFAULT)
    default_unit = combat_order.get("defaultUnit", "mech")

    if (
      mech_count >= opening_artillery_min_mechs
      and artillery_count < min_artillery
      and crystals >= UNIT_COSTS["artillery"]
    ):
      bot.combat_build_toggle += 1
      return "artillery"

    if mech_count < min_mechs_before_default and crystals >= UNIT_COSTS["mech"]:
      bot.combat_build_toggle += 1
      return "mech"

    if default_unit in UNIT_COSTS and crystals >= UNIT_COSTS[default_unit]:
      bot.combat_build_toggle += 1
      return default_unit

    return None

  def needs_mid_game_passive_income(self, bot, owned_levels):
    return self.passive_income_level(owned_levels) < bot.mid_passive_income_level

  def passive_income_level(self, owned_levels):
    return owned_levels.get(PASSIVE_INCOME_UPGRADE, 0)

  def passive_income_upgrade_cost(self, state, owned_levels):
    upgrade = state.get("techTree", {}).get(PASSIVE_INCOME_UPGRADE)
    if not upgrade:
      return None

    level = self.passive_income_level(owned_levels)
    return upgrade.get("initialCost", 0) + level * upgrade.get("costIncrease", 0)
