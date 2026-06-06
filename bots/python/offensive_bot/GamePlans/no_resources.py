from GamePlans.game_plan import GamePlan
from GeneralStrategy.settings import BuildPhase


class NoResourcesPlan(GamePlan):
  phase = BuildPhase.NO_RESOURCES

  def choose_build(self, bot, state, crystals):
    return None

  def choose_upgrade(self, bot, state, crystals, owned_levels):
    return None
