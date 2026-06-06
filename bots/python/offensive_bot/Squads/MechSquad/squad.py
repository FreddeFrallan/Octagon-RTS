from GeneralStrategy.settings import MIN_MECH_SQUAD_SIZE, SquadGoal, SquadType
from Squads.squad import Squad


class MechSquad(Squad):
  virtual_unit_type = "shuttleSquad"
  minimum_units = MIN_MECH_SQUAD_SIZE

  def __init__(self, units, goal=SquadGoal.ENEMY_BASE):
    super().__init__(units, goal)

  @property
  def squad_type(self):
    if self.goal == SquadGoal.ENEMY_WORKERS:
      return SquadType.WORKER_HUNTER
    return SquadType.MECH
