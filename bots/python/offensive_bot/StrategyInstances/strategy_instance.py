import json
from pathlib import Path


DEFAULT_STRATEGY_INSTANCE_PATH = Path(__file__).with_name("default.json")


class StrategyInstance:
  def __init__(self, data, path=None):
    self.data = data
    self.path = path

  def bot_name(self, fallback):
    return self.data.get("name", fallback)

  def max_actions_per_tick(self, fallback):
    return self.data.get("maxActionsPerTick", fallback)

  def unit_limit(self, key, fallback):
    return self.data.get("unitLimits", {}).get(key, fallback)

  def phase(self, phase):
    return self.data.get("phases", {}).get(phase.value, {})

  def phase_build_order(self, phase):
    return self.phase(phase).get("buildOrder", [])

  def phase_completion_criteria(self, phase):
    return self.phase(phase).get("completionCriteria", {})

  def phase_unit_target(self, phase, unit_type, fallback):
    for step in self.phase_build_order(phase):
      if step.get("unitType") == unit_type:
        return step.get("targetCount", fallback)
    return fallback

  def phase_value(self, phase, key, fallback=None):
    return self.phase(phase).get(key, fallback)

  def combat_build_order(self):
    return self.data.get("combatBuildOrder", {})

  def squad(self, squad_name):
    return self.data.get("squads", {}).get(squad_name, {})

  def squad_value(self, squad_name, key, fallback):
    return self.squad(squad_name).get(key, fallback)

  def micro(self, section):
    return self.data.get("micro", {}).get(section, {})

  def micro_value(self, section, key, fallback):
    return self.micro(section).get(key, fallback)


def load_strategy_instance(path=None):
  strategy_path = Path(path) if path else DEFAULT_STRATEGY_INSTANCE_PATH
  with strategy_path.open("r", encoding="utf-8") as file:
    return StrategyInstance(json.load(file), path=strategy_path)
