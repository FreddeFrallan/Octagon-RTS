from GamePlans import (
  EarlyGamePlan,
  FinishStagePlan,
  LateGamePlan,
  MidGamePlan,
  NoResourcesPlan
)
from GeneralStrategy.settings import (
  BUILD_PHASE_ORDER,
  BuildPhase,
  UNIT_COSTS
)


def create_game_plans():
  plans = [
    EarlyGamePlan(),
    MidGamePlan(),
    LateGamePlan(),
    NoResourcesPlan(),
    FinishStagePlan()
  ]
  return {plan.phase: plan for plan in plans}


def select_game_plan(bot, state):
  candidate = next_build_strategy_phase(bot, state)
  terminal_phases = (BuildPhase.NO_RESOURCES, BuildPhase.FINISH_STAGE)
  if candidate in terminal_phases or bot.current_build_phase in terminal_phases:
    if candidate != bot.current_build_phase:
      bot.current_build_phase = candidate
      bot.current_game_plan = bot.game_plans[candidate]
      bot.log(f"build phase advanced to {candidate.value}")
  elif BUILD_PHASE_ORDER[candidate] > BUILD_PHASE_ORDER[bot.current_build_phase]:
    bot.current_build_phase = candidate
    bot.current_game_plan = bot.game_plans[candidate]
    bot.log(f"build phase advanced to {candidate.value}")
  return bot.current_game_plan


def choose_build(bot, state, crystals, game_plan=None):
  if crystals < min(UNIT_COSTS.values()):
    return None

  plan = game_plan or select_game_plan(bot, state)
  return plan.choose_build(bot, state, crystals)


def build_strategy_phase(bot, state):
  return select_game_plan(bot, state).phase


def next_build_strategy_phase(bot, state):
  if not bot.enemy_units(state):
    return BuildPhase.FINISH_STAGE
  if not bot.resource_cells(state):
    return BuildPhase.NO_RESOURCES

  own = bot.own_units(state)
  unit_counts = {}
  for unit in own:
    unit_counts[unit["type"]] = unit_counts.get(unit["type"], 0) + 1
  early_criteria = bot.strategy_instance.phase_completion_criteria(BuildPhase.EARLY_GAME)
  required_unit_counts = early_criteria.get("unitCounts", {
    "worker": bot.early_worker_target,
    "mech": bot.early_hunter_mechs,
    "artillery": bot.early_hunter_artillery
  })

  for unit_type, required_count in required_unit_counts.items():
    if unit_counts.get(unit_type, 0) < required_count:
      return BuildPhase.EARLY_GAME

  player = state["players"][str(state["localPlayerId"])]
  base_pos = player["basePos"]
  base = (base_pos["x"], base_pos["z"])
  mid_criteria = bot.strategy_instance.phase_completion_criteria(BuildPhase.MID_GAME)
  required_base_power_towers = mid_criteria.get("basePowerTowers", bot.mid_base_power_towers)
  required_passive_income_level = mid_criteria.get("passiveIncomeLevel", bot.mid_passive_income_level)
  if len(bot.power_towers_near_base(state, base)) < required_base_power_towers:
    return BuildPhase.MID_GAME
  if bot.game_plans[BuildPhase.MID_GAME].passive_income_level(player.get("techUpgrades", {})) < required_passive_income_level:
    return BuildPhase.MID_GAME

  return BuildPhase.LATE_GAME


def choose_combat_build(bot, state, crystals):
  return select_game_plan(bot, state).choose_combat_build(bot, state, crystals)


def choose_upgrade(bot, state, crystals, owned_levels, game_plan=None):
  plan = game_plan or select_game_plan(bot, state)
  return plan.choose_upgrade(bot, state, crystals, owned_levels)
