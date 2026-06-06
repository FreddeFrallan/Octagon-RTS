from enum import Enum

UNIT_COSTS = {
  "worker": 50,
  "mech": 100,
  "artillery": 80,
  "powerTower": 125
}

DEFAULT_BOT_NAME = "Python Offensive Bot"
DEFAULT_MAX_ACTIONS_PER_TICK = 8
DEFAULT_MIN_WORKERS = 1
DEFAULT_MAX_WORKERS = 5
DEFAULT_MAX_POWER_TOWERS = 4
DEFAULT_BASE_POWER_TOWERS = 2

COMBAT_TYPES = {"mech", "artillery"}
POWER_TOWER_TYPE = "powerTower"
DEFENSIVE_POWER_TOWER_COUNT = 1
DEFENSIVE_POWER_TOWER_RADIUS = 3
ENEMY_POWER_TOWER_AVOID_RADIUS = 1
ARTILLERY_SHELL_FLIGHT_SECONDS = 1.0
EARLY_WORKER_TARGET = 4
EARLY_HUNTER_MECHS = 2
EARLY_HUNTER_ARTILLERY = 0
MID_BASE_POWER_TOWERS = 1
PASSIVE_INCOME_UPGRADE = "upgrade_passive_income"
MID_PASSIVE_INCOME_LEVEL = 1
MIN_MECH_SQUAD_SIZE = 2

COMBAT_OPENING_ARTILLERY_MIN_MECHS = 1
COMBAT_MIN_ARTILLERY = 1
COMBAT_MIN_MECHS_BEFORE_DEFAULT = 2

ARTILLERY_MIN_RANGE = 1
ARTILLERY_MAX_RANGE = 2
ARTILLERY_ESCORT_DISTANCE = 1
ARTILLERY_COMBAT_CONTEXT_MECH_DISTANCE = 3

POWER_TOWER_COMBAT_CONTEXT_RANGE = 1
POWER_TOWER_WORKER_SAFE_DISTANCE = 2

WORKER_SAFE_RESOURCE_ENEMY_DISTANCE = 2
WORKER_RESOURCE_ENEMY_DANGER_RADIUS = 4
WORKER_RESOURCE_ENEMY_DANGER_WEIGHT = 2
WORKER_RESOURCE_TOWER_DANGER = 8

MOVE_ORDER_REPEAT_SECONDS = 0.8
BUILD_TOWER_ORDER_REPEAT_SECONDS = 1.5

UNIT_PRIORITY = {
  "worker": 0,
  "artillery": 1,
  "mech": 2
}
DEFAULT_UNIT_PRIORITY = 3


class BuildPhase(Enum):
  EARLY_GAME = "early_game"
  MID_GAME = "mid_game"
  LATE_GAME = "late_game"


class UnitTacticalState(Enum):
  WAITING = "waiting"
  MOVING = "moving"
  COMBAT = "combat"


class WorkerStrategy(Enum):
  GATHER_AND_BUILD_BASE_TOWER = "gather_and_build_base_tower"


class WorkerTacticalState(Enum):
  BUILDING_TOWER = "BuildingTower"


class MechStrategy(Enum):
  HUNT_WORKERS_THEN_ATTACK_BASE = "hunt_workers_then_attack_base"


class ArtilleryStrategy(Enum):
  SNEAKY_FLANK_AND_SHELL = "sneaky_flank_and_shell"


class PowerTowerStrategy(Enum):
  BASE_DEFENSE = "base_defense"


class MechWaitingBehavior(Enum):
  HOLD_FOR_OBJECTIVE = "hold_for_objective"


class MechMovingBehavior(Enum):
  ADVANCE_TO_OBJECTIVE = "advance_to_objective"


class MechCombatBehavior(Enum):
  HUNT_OR_PRESS_BASE = "hunt_or_press_base"


class ArtilleryWaitingBehavior(Enum):
  WAIT_FOR_ESCORT = "wait_for_escort"


class ArtilleryMovingBehavior(Enum):
  MOVE_TO_FLANK = "move_to_flank"


class ArtilleryCombatBehavior(Enum):
  STRATEGIC_AIM_THEN_COOLDOWN_RETREAT = "strategic_aim_then_cooldown_retreat"


class PowerTowerWaitingBehavior(Enum):
  HOLD_POSITION = "hold_position"


class PowerTowerMovingBehavior(Enum):
  CANNOT_MOVE = "cannot_move"


class PowerTowerCombatBehavior(Enum):
  AUTO_FIRE = "auto_fire"


class SquadType(Enum):
  SNEAKY_ARTILLERY = "SneakyArtillery"
  WORKER_HUNTER = "workerHunter"
  MECH = "mech"


class SquadGoal(Enum):
  FLANK_BASE = "flank_base"
  ENEMY_WORKERS = "enemy_workers"
  ENEMY_BASE = "enemy_base"


BUILD_PHASE_ORDER = {
  BuildPhase.EARLY_GAME: 0,
  BuildPhase.MID_GAME: 1,
  BuildPhase.LATE_GAME: 2
}

DEFAULT_WORKER_STRATEGY = WorkerStrategy.GATHER_AND_BUILD_BASE_TOWER
DEFAULT_MECH_STRATEGY = MechStrategy.HUNT_WORKERS_THEN_ATTACK_BASE
DEFAULT_ARTILLERY_STRATEGY = ArtilleryStrategy.SNEAKY_FLANK_AND_SHELL
DEFAULT_POWER_TOWER_STRATEGY = PowerTowerStrategy.BASE_DEFENSE

DEFAULT_MECH_STATE_BEHAVIORS = {
  UnitTacticalState.WAITING: MechWaitingBehavior.HOLD_FOR_OBJECTIVE,
  UnitTacticalState.MOVING: MechMovingBehavior.ADVANCE_TO_OBJECTIVE,
  UnitTacticalState.COMBAT: MechCombatBehavior.HUNT_OR_PRESS_BASE
}

DEFAULT_ARTILLERY_STATE_BEHAVIORS = {
  UnitTacticalState.WAITING: ArtilleryWaitingBehavior.WAIT_FOR_ESCORT,
  UnitTacticalState.MOVING: ArtilleryMovingBehavior.MOVE_TO_FLANK,
  UnitTacticalState.COMBAT: ArtilleryCombatBehavior.STRATEGIC_AIM_THEN_COOLDOWN_RETREAT
}

DEFAULT_POWER_TOWER_STATE_BEHAVIORS = {
  UnitTacticalState.WAITING: PowerTowerWaitingBehavior.HOLD_POSITION,
  UnitTacticalState.MOVING: PowerTowerMovingBehavior.CANNOT_MOVE,
  UnitTacticalState.COMBAT: PowerTowerCombatBehavior.AUTO_FIRE
}
