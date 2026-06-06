from collections import OrderedDict
from dataclasses import dataclass


EARLY_BUILD_UNITS = ("worker", "mech", "artillery")
EARLY_COMPLETION_UNITS = ("worker", "mech", "artillery")

UNIT_LIMIT_KEYS = (
  "minWorkers",
  "maxWorkers",
  "maxPowerTowers",
  "basePowerTowers",
  "defensivePowerTowers",
  "defensivePowerTowerRadius"
)

COMBAT_BUILD_ORDER_KEYS = (
  "openingArtilleryMinMechs",
  "minArtillery",
  "minMechsBeforeDefault",
  "defaultUnit"
)

MICRO_KEYS = OrderedDict([
  ("mech", (
    "nearbyEnemyMaxSteps",
    "baseStandoffDistance",
    "blockerAdjacentDistance",
    "avoidEnemyTowers"
  )),
  ("artillery", (
    "minRange",
    "maxRange",
    "escortDistance",
    "shellFlightSeconds",
    "combatContextMechDistance",
    "retreatThreatDistance",
    "avoidEnemyTowers",
    "enemyPowerTowerPriority"
  )),
  ("worker", (
    "safeResourceEnemyDistance",
    "resourceEnemyDangerRadius",
    "resourceEnemyDangerWeight",
    "resourceTowerDanger",
    "resourceAdjacentDistance",
    "avoidEnemyTowers"
  )),
  ("powerTower", (
    "combatContextRange",
    "workerSafeDistance",
    "basePreferredDistance"
  )),
  ("orders", (
    "moveRepeatSeconds",
    "buildTowerRepeatSeconds",
    "suppressRepeatedAttackTargets"
  ))
])

GENE_TYPE_INT = "int"
GENE_TYPE_FLOAT = "float"
GENE_TYPE_BOOL = "bool"
GENE_TYPE_CATEGORY = "category"
GENE_TYPE_TEXT = "text"

COMBAT_UNIT_OPTIONS = ("mech", "artillery")
UPGRADE_UNIT_OPTIONS = ("worker", "mech", "artillery")
UPGRADE_PROPERTY_OPTIONS = ("maxHp", "attack", "moveSpeed")
UPGRADE_SELECTION_OPTIONS = ("lowest_level_then_cost",)


@dataclass(frozen=True)
class GeneMetadata:
  key: str
  gene_type: str
  minimum: float = None
  maximum: float = None
  step: float = None
  options: tuple = None
  mutable: bool = True
  description: str = ""
  repair: str = None

  def contains(self, value):
    if value is None:
      return False
    if self.gene_type == GENE_TYPE_TEXT:
      return isinstance(value, str)
    if self.gene_type == GENE_TYPE_BOOL:
      return isinstance(value, bool)
    if self.gene_type == GENE_TYPE_CATEGORY:
      return value in self.options
    if self.gene_type == GENE_TYPE_INT:
      return isinstance(value, int) and not isinstance(value, bool) and self.minimum <= value <= self.maximum
    if self.gene_type == GENE_TYPE_FLOAT:
      return isinstance(value, (int, float)) and not isinstance(value, bool) and self.minimum <= value <= self.maximum
    return False


def text_gene(key, description):
  return GeneMetadata(key, GENE_TYPE_TEXT, mutable=False, description=description)


def int_gene(key, minimum, maximum, description, step=1, repair=None):
  return GeneMetadata(key, GENE_TYPE_INT, minimum=minimum, maximum=maximum, step=step, description=description, repair=repair)


def float_gene(key, minimum, maximum, description, step=0.1, repair=None):
  return GeneMetadata(key, GENE_TYPE_FLOAT, minimum=minimum, maximum=maximum, step=step, description=description, repair=repair)


def bool_gene(key, description):
  return GeneMetadata(key, GENE_TYPE_BOOL, description=description)


def category_gene(key, options, description, repair=None):
  return GeneMetadata(key, GENE_TYPE_CATEGORY, options=tuple(options), description=description, repair=repair)


def metadata(*items):
  return OrderedDict((item.key, item) for item in items)


GENE_METADATA = metadata(
  text_gene("name", "Bot display name; fixed for learning runs."),
  int_gene("maxActionsPerTick", 1, 20, "Maximum actions the bot may emit on one strategy tick."),

  int_gene("unitLimits.minWorkers", 0, 12, "Minimum worker floor before spending freely on combat.", repair="minWorkers <= maxWorkers"),
  int_gene("unitLimits.maxWorkers", 0, 20, "Maximum intended worker count.", repair="maxWorkers >= minWorkers"),
  int_gene("unitLimits.maxPowerTowers", 0, 12, "Maximum intended power tower count."),
  int_gene("unitLimits.basePowerTowers", 0, 12, "Desired base-adjacent power tower count.", repair="basePowerTowers <= maxPowerTowers"),
  int_gene("unitLimits.defensivePowerTowers", 0, 12, "Desired defensive power tower count.", repair="defensivePowerTowers <= maxPowerTowers"),
  int_gene("unitLimits.defensivePowerTowerRadius", 1, 8, "Radius around base used for defensive tower planning."),

  int_gene("combatBuildOrder.openingArtilleryMinMechs", 0, 12, "Mech count required before opening artillery production."),
  int_gene("combatBuildOrder.minArtillery", 0, 12, "Minimum artillery count before default combat production."),
  int_gene("combatBuildOrder.minMechsBeforeDefault", 0, 20, "Minimum mech count before default combat production."),
  category_gene("combatBuildOrder.defaultUnit", COMBAT_UNIT_OPTIONS, "Default combat unit to produce after minimums are satisfied."),

  int_gene("squads.mech.minimumUnits", 1, 8, "Minimum mechs grouped into one mech squad."),
  int_gene("squads.sneakyArtillery.artilleryCount", 0, 6, "Artillery count required for a sneaky artillery squad."),
  int_gene("squads.sneakyArtillery.mechEscortCount", 0, 8, "Mech escort count required for a sneaky artillery squad."),

  int_gene("micro.mech.nearbyEnemyMaxSteps", 0, 8, "Search distance for nearby mech targets."),
  int_gene("micro.mech.baseStandoffDistance", 0, 4, "Preferred mech distance from enemy base."),
  int_gene("micro.mech.blockerAdjacentDistance", 0, 3, "Distance used to classify enemy blockers."),
  bool_gene("micro.mech.avoidEnemyTowers", "Whether mech pathing avoids enemy tower zones."),

  int_gene("micro.artillery.minRange", 0, 4, "Minimum artillery fire range.", repair="minRange <= maxRange"),
  int_gene("micro.artillery.maxRange", 1, 6, "Maximum artillery fire range.", repair="maxRange >= minRange"),
  int_gene("micro.artillery.escortDistance", 0, 4, "Preferred escort distance around artillery."),
  float_gene("micro.artillery.shellFlightSeconds", 0.1, 5.0, "Predicted artillery shell flight time."),
  int_gene("micro.artillery.combatContextMechDistance", 0, 8, "Enemy mech distance that marks artillery as in combat."),
  int_gene("micro.artillery.retreatThreatDistance", 0, 6, "Enemy mech distance that can trigger artillery retreat."),
  bool_gene("micro.artillery.avoidEnemyTowers", "Whether artillery movement avoids enemy tower zones."),
  int_gene("micro.artillery.enemyPowerTowerPriority", -5, 10, "Artillery target priority for enemy power towers."),

  int_gene("micro.worker.safeResourceEnemyDistance", 0, 8, "Enemy distance considered safe for resource gathering."),
  int_gene("micro.worker.resourceEnemyDangerRadius", 0, 8, "Enemy radius contributing resource danger."),
  int_gene("micro.worker.resourceEnemyDangerWeight", 0, 10, "Score weight for enemy danger near resources."),
  int_gene("micro.worker.resourceTowerDanger", 0, 20, "Score penalty for enemy tower danger near resources."),
  int_gene("micro.worker.resourceAdjacentDistance", 0, 3, "Distance at which workers consider themselves adjacent to resources."),
  bool_gene("micro.worker.avoidEnemyTowers", "Whether worker pathing avoids enemy tower zones."),

  int_gene("micro.powerTower.combatContextRange", 0, 5, "Range used to decide whether tower behavior is in combat context."),
  int_gene("micro.powerTower.workerSafeDistance", 0, 8, "Required worker safety distance for tower building."),
  int_gene("micro.powerTower.basePreferredDistance", 0, 5, "Preferred tower placement distance from base."),

  float_gene("micro.orders.moveRepeatSeconds", 0.0, 5.0, "Cooldown before repeating an identical move order."),
  float_gene("micro.orders.buildTowerRepeatSeconds", 0.0, 5.0, "Cooldown before repeating a tower build order."),
  bool_gene("micro.orders.suppressRepeatedAttackTargets", "Whether repeated artillery targets are suppressed."),

  int_gene("phases.early_game.completionCriteria.unitCounts.worker", 0, 20, "Workers required to leave early game."),
  int_gene("phases.early_game.completionCriteria.unitCounts.mech", 0, 20, "Mechs required to leave early game."),
  int_gene("phases.early_game.completionCriteria.unitCounts.artillery", 0, 12, "Artillery required to leave early game."),
  int_gene("phases.early_game.buildOrder.worker.targetCount", 0, 20, "Worker target in early build order."),
  int_gene("phases.early_game.buildOrder.mech.targetCount", 0, 20, "Mech target in early build order."),
  int_gene("phases.early_game.buildOrder.artillery.targetCount", 0, 12, "Artillery target in early build order; 0 means skipped."),

  int_gene("phases.mid_game.completionCriteria.basePowerTowers", 0, 12, "Base power towers required to leave mid game."),
  int_gene("phases.mid_game.completionCriteria.passiveIncomeLevel", 0, 10, "Passive income level required to leave mid game."),
  int_gene("phases.mid_game.basePowerTowers", 0, 12, "Base power tower target in mid game.", repair="basePowerTowers <= maxPowerTowers"),
  int_gene("phases.mid_game.passiveIncomeLevel", 0, 10, "Passive income target in mid game."),
  bool_gene("phases.mid_game.reserveForPowerTower", "Whether mid game reserves resources for power towers."),
  category_gene("phases.mid_game.reserveCombatUnit", COMBAT_UNIT_OPTIONS, "Combat unit cost reserved while planning towers."),

  int_gene("phases.late_game.buildOrder.combat", 0, 1, "Whether late game combat production is enabled."),
  category_gene("phases.late_game.upgrades.0.targetUnit", UPGRADE_UNIT_OPTIONS, "Unit type affected by the first late-game upgrade rule."),
  category_gene("phases.late_game.upgrades.0.targetProperty", UPGRADE_PROPERTY_OPTIONS, "Property affected by the first late-game upgrade rule."),
  category_gene("phases.late_game.upgrades.0.selection", UPGRADE_SELECTION_OPTIONS, "Selection policy for the first late-game upgrade rule.")
)

GENE_REPAIR_RULES = (
  ("unitLimits.minWorkers", "<=", "unitLimits.maxWorkers"),
  ("unitLimits.basePowerTowers", "<=", "unitLimits.maxPowerTowers"),
  ("unitLimits.defensivePowerTowers", "<=", "unitLimits.maxPowerTowers"),
  ("phases.mid_game.basePowerTowers", "<=", "unitLimits.maxPowerTowers"),
  ("micro.artillery.minRange", "<=", "micro.artillery.maxRange")
)


class StrategyGenome:
  def __init__(self, genes):
    self.genes = OrderedDict(genes)

  @classmethod
  def from_strategy_instance(cls, strategy):
    genes = OrderedDict()
    genes["name"] = strategy.get("name")
    genes["maxActionsPerTick"] = strategy.get("maxActionsPerTick")

    for key in UNIT_LIMIT_KEYS:
      genes[f"unitLimits.{key}"] = strategy.get("unitLimits", {}).get(key, 0)

    for key in COMBAT_BUILD_ORDER_KEYS:
      genes[f"combatBuildOrder.{key}"] = strategy.get("combatBuildOrder", {}).get(key, 0)

    genes["squads.mech.minimumUnits"] = strategy.get("squads", {}).get("mech", {}).get("minimumUnits", 0)
    genes["squads.sneakyArtillery.artilleryCount"] = strategy.get("squads", {}).get("sneakyArtillery", {}).get("artilleryCount", 0)
    genes["squads.sneakyArtillery.mechEscortCount"] = strategy.get("squads", {}).get("sneakyArtillery", {}).get("mechEscortCount", 0)

    for section, keys in MICRO_KEYS.items():
      values = strategy.get("micro", {}).get(section, {})
      for key in keys:
        genes[f"micro.{section}.{key}"] = values.get(key, 0)

    early_game = strategy.get("phases", {}).get("early_game", {})
    early_counts = early_game.get("completionCriteria", {}).get("unitCounts", {})
    for unit_type in EARLY_COMPLETION_UNITS:
      genes[f"phases.early_game.completionCriteria.unitCounts.{unit_type}"] = early_counts.get(unit_type, 0)

    early_targets = {
      step.get("unitType"): step.get("targetCount", 0)
      for step in early_game.get("buildOrder", [])
      if "unitType" in step
    }
    for unit_type in EARLY_BUILD_UNITS:
      genes[f"phases.early_game.buildOrder.{unit_type}.targetCount"] = early_targets.get(unit_type, 0)

    mid_game = strategy.get("phases", {}).get("mid_game", {})
    mid_completion = mid_game.get("completionCriteria", {})
    genes["phases.mid_game.completionCriteria.basePowerTowers"] = mid_completion.get("basePowerTowers", 0)
    genes["phases.mid_game.completionCriteria.passiveIncomeLevel"] = mid_completion.get("passiveIncomeLevel", 0)
    genes["phases.mid_game.basePowerTowers"] = mid_game.get("basePowerTowers", 0)
    genes["phases.mid_game.passiveIncomeLevel"] = mid_game.get("passiveIncomeLevel", 0)
    genes["phases.mid_game.reserveForPowerTower"] = mid_game.get("reserveForPowerTower", False)
    genes["phases.mid_game.reserveCombatUnit"] = mid_game.get("reserveCombatUnit", 0)

    late_game = strategy.get("phases", {}).get("late_game", {})
    genes["phases.late_game.buildOrder.combat"] = 1 if any(
      step.get("type") == "combat"
      for step in late_game.get("buildOrder", [])
    ) else 0

    upgrades = late_game.get("upgrades", [])
    first_upgrade = upgrades[0] if upgrades else {}
    genes["phases.late_game.upgrades.0.targetUnit"] = first_upgrade.get("targetUnit", 0)
    genes["phases.late_game.upgrades.0.targetProperty"] = first_upgrade.get("targetProperty", 0)
    genes["phases.late_game.upgrades.0.selection"] = first_upgrade.get("selection", 0)

    return cls(genes)

  def to_strategy_instance(self):
    return {
      "name": self.genes["name"],
      "maxActionsPerTick": self.genes["maxActionsPerTick"],
      "unitLimits": {
        key: self.genes[f"unitLimits.{key}"]
        for key in UNIT_LIMIT_KEYS
      },
      "combatBuildOrder": {
        key: self.genes[f"combatBuildOrder.{key}"]
        for key in COMBAT_BUILD_ORDER_KEYS
      },
      "squads": {
        "mech": {
          "minimumUnits": self.genes["squads.mech.minimumUnits"]
        },
        "sneakyArtillery": {
          "artilleryCount": self.genes["squads.sneakyArtillery.artilleryCount"],
          "mechEscortCount": self.genes["squads.sneakyArtillery.mechEscortCount"]
        }
      },
      "micro": {
        section: {
          key: self.genes[f"micro.{section}.{key}"]
          for key in keys
        }
        for section, keys in MICRO_KEYS.items()
      },
      "phases": {
        "early_game": {
          "completionCriteria": {
            "unitCounts": {
              unit_type: self.genes[f"phases.early_game.completionCriteria.unitCounts.{unit_type}"]
              for unit_type in EARLY_COMPLETION_UNITS
            }
          },
          "buildOrder": [
            {
              "unitType": unit_type,
              "targetCount": self.genes[f"phases.early_game.buildOrder.{unit_type}.targetCount"]
            }
            for unit_type in EARLY_BUILD_UNITS
          ]
        },
        "mid_game": {
          "completionCriteria": {
            "basePowerTowers": self.genes["phases.mid_game.completionCriteria.basePowerTowers"],
            "passiveIncomeLevel": self.genes["phases.mid_game.completionCriteria.passiveIncomeLevel"]
          },
          "basePowerTowers": self.genes["phases.mid_game.basePowerTowers"],
          "passiveIncomeLevel": self.genes["phases.mid_game.passiveIncomeLevel"],
          "reserveForPowerTower": self.genes["phases.mid_game.reserveForPowerTower"],
          "reserveCombatUnit": self.genes["phases.mid_game.reserveCombatUnit"]
        },
        "late_game": {
          "buildOrder": self.late_game_build_order(),
          "upgrades": self.late_game_upgrades()
        }
      }
    }

  def late_game_build_order(self):
    if self.genes["phases.late_game.buildOrder.combat"] <= 0:
      return []
    return [{"type": "combat"}]

  def late_game_upgrades(self):
    target_unit = self.genes["phases.late_game.upgrades.0.targetUnit"]
    target_property = self.genes["phases.late_game.upgrades.0.targetProperty"]
    selection = self.genes["phases.late_game.upgrades.0.selection"]
    if not target_unit or not target_property or not selection:
      return []
    return [{
      "targetUnit": target_unit,
      "targetProperty": target_property,
      "selection": selection
    }]
