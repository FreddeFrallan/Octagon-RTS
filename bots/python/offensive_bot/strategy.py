import json
import threading
import time
import urllib.error

from api_client import ApiClientMixin
from GeneralStrategy import build_order
from GeneralStrategy.settings import (
  BuildPhase,
  DEFAULT_ARTILLERY_STATE_BEHAVIORS,
  DEFAULT_ARTILLERY_STRATEGY,
  DEFAULT_BASE_POWER_TOWERS,
  DEFAULT_BOT_NAME,
  DEFAULT_MAX_ACTIONS_PER_TICK,
  DEFAULT_MAX_POWER_TOWERS,
  DEFAULT_MAX_WORKERS,
  DEFAULT_MECH_STATE_BEHAVIORS,
  DEFAULT_MECH_STRATEGY,
  DEFAULT_MIN_WORKERS,
  DEFAULT_POWER_TOWER_STATE_BEHAVIORS,
  DEFAULT_POWER_TOWER_STRATEGY,
  DEFAULT_WORKER_STRATEGY,
  DEFENSIVE_POWER_TOWER_COUNT,
  DEFENSIVE_POWER_TOWER_RADIUS,
  EARLY_HUNTER_ARTILLERY,
  EARLY_HUNTER_MECHS,
  EARLY_WORKER_TARGET,
  MID_BASE_POWER_TOWERS,
  MID_PASSIVE_INCOME_LEVEL,
  UNIT_COSTS
)
from GeneralStrategy.navigation import NavigationMixin
from orders import OrderMixin
from StrategyInstances import load_strategy_instance
from Units.combat_planner import CombatPlannerMixin
from Units.queries import UnitQueriesMixin
from Units.tactical_state import TacticalStateMixin
from Units.tracker import UnitTrackerMixin
from Units.PowerTower import micro as power_tower_micro


class OffensiveBot(
  ApiClientMixin,
  OrderMixin,
  UnitTrackerMixin,
  TacticalStateMixin,
  CombatPlannerMixin,
  UnitQueriesMixin,
  NavigationMixin
):
  def __init__(
    self,
    name=None,
    max_actions_per_tick=None,
    verbose=True,
    min_workers=None,
    max_workers=None,
    max_power_towers=None,
    base_power_towers=None,
    defensive_power_towers=None,
    defensive_power_tower_radius=None,
    early_worker_target=None,
    early_hunter_mechs=None,
    early_hunter_artillery=None,
    mid_base_power_towers=None,
    mid_passive_income_level=None,
    strategy_instance_path=None
  ):
    self.strategy_instance = load_strategy_instance(strategy_instance_path)
    self.name = name if name is not None else self.strategy_instance.bot_name(DEFAULT_BOT_NAME)
    self.max_actions_per_tick = max_actions_per_tick if max_actions_per_tick is not None else self.strategy_instance.max_actions_per_tick(DEFAULT_MAX_ACTIONS_PER_TICK)
    self.verbose = verbose
    min_workers = min_workers if min_workers is not None else self.strategy_instance.unit_limit("minWorkers", DEFAULT_MIN_WORKERS)
    max_workers = max_workers if max_workers is not None else self.strategy_instance.unit_limit("maxWorkers", DEFAULT_MAX_WORKERS)
    max_power_towers = max_power_towers if max_power_towers is not None else self.strategy_instance.unit_limit("maxPowerTowers", DEFAULT_MAX_POWER_TOWERS)
    base_power_towers = base_power_towers if base_power_towers is not None else self.strategy_instance.unit_limit("basePowerTowers", DEFAULT_BASE_POWER_TOWERS)
    defensive_power_towers = defensive_power_towers if defensive_power_towers is not None else self.strategy_instance.unit_limit("defensivePowerTowers", DEFENSIVE_POWER_TOWER_COUNT)
    defensive_power_tower_radius = defensive_power_tower_radius if defensive_power_tower_radius is not None else self.strategy_instance.unit_limit("defensivePowerTowerRadius", DEFENSIVE_POWER_TOWER_RADIUS)
    self.min_workers = max(0, min_workers)
    self.max_workers = max(self.min_workers, max_workers)
    self.max_power_towers = max(0, max_power_towers)
    self.base_power_towers = max(0, min(base_power_towers, self.max_power_towers))
    self.defensive_power_towers = max(0, min(defensive_power_towers, self.max_power_towers))
    self.defensive_power_tower_radius = max(1, defensive_power_tower_radius)
    early_worker_target = early_worker_target if early_worker_target is not None else self.strategy_instance.phase_unit_target(BuildPhase.EARLY_GAME, "worker", EARLY_WORKER_TARGET)
    early_hunter_mechs = early_hunter_mechs if early_hunter_mechs is not None else self.strategy_instance.phase_unit_target(BuildPhase.EARLY_GAME, "mech", EARLY_HUNTER_MECHS)
    early_hunter_artillery = early_hunter_artillery if early_hunter_artillery is not None else self.strategy_instance.phase_unit_target(BuildPhase.EARLY_GAME, "artillery", EARLY_HUNTER_ARTILLERY)
    mid_base_power_towers = mid_base_power_towers if mid_base_power_towers is not None else self.strategy_instance.phase_value(BuildPhase.MID_GAME, "basePowerTowers", MID_BASE_POWER_TOWERS)
    mid_passive_income_level = mid_passive_income_level if mid_passive_income_level is not None else self.strategy_instance.phase_value(BuildPhase.MID_GAME, "passiveIncomeLevel", MID_PASSIVE_INCOME_LEVEL)
    self.early_worker_target = max(self.min_workers, min(early_worker_target, self.max_workers))
    self.early_hunter_mechs = max(0, early_hunter_mechs)
    self.early_hunter_artillery = max(0, early_hunter_artillery)
    self.mid_base_power_towers = max(0, min(mid_base_power_towers, self.max_power_towers))
    self.mid_passive_income_level = max(0, mid_passive_income_level)
    self.worker_strategy = DEFAULT_WORKER_STRATEGY
    self.mech_strategy = DEFAULT_MECH_STRATEGY
    self.artillery_strategy = DEFAULT_ARTILLERY_STRATEGY
    self.power_tower_strategy = DEFAULT_POWER_TOWER_STRATEGY
    self.mech_state_behaviors = dict(DEFAULT_MECH_STATE_BEHAVIORS)
    self.artillery_state_behaviors = dict(DEFAULT_ARTILLERY_STATE_BEHAVIORS)
    self.power_tower_state_behaviors = dict(DEFAULT_POWER_TOWER_STATE_BEHAVIORS)
    self.session = None
    self.session_lock = threading.Lock()
    self.thread = None
    self.stop_event = threading.Event()
    self.worker_spend = 0
    self.combat_spend = 0
    self.upgrade_spend = 0
    self.unit_tracker = {}
    self.last_unit_orders = {}
    self.last_artillery_targets = {}
    self.combat_build_toggle = 0
    self.game_plans = build_order.create_game_plans()
    self.current_build_phase = BuildPhase.EARLY_GAME
    self.current_game_plan = self.game_plans[self.current_build_phase]
    self._offline_actions = None
    self._offline_now_seconds = None
    self._offline_player_id = None

  def start_session(self, payload):
    with self.session_lock:
      self.session = {
        "gameServer": payload["gameServer"],
        "roomId": payload["roomId"],
        "playerId": payload["playerId"],
        "pollMs": payload.get("pollMs", 200)
      }
      self.worker_spend = 0
      self.combat_spend = 0
      self.upgrade_spend = 0
      self.unit_tracker = {}
      self.last_unit_orders = {}
      self.last_artillery_targets = {}
      self.combat_build_toggle = 0
      self.current_build_phase = BuildPhase.EARLY_GAME
      self.current_game_plan = self.game_plans[self.current_build_phase]

    self.stop_event.clear()
    if not self.thread or not self.thread.is_alive():
      self.thread = threading.Thread(target=self.loop, daemon=True)
      self.thread.start()

  def stop_session(self):
    with self.session_lock:
      self.session = None
    self.stop_event.set()

  def current_session(self):
    with self.session_lock:
      return dict(self.session) if self.session else None

  def loop(self):
    while not self.stop_event.is_set():
      current = self.current_session()
      if not current:
        time.sleep(0.2)
        continue

      try:
        self._tick(current)
      except (urllib.error.URLError, TimeoutError, KeyError, json.JSONDecodeError) as e:
        self.log(f"tick skipped: {type(e).__name__}: {e}")

      time.sleep(current.get("pollMs", 200) / 1000)

  def force_tick(self, player_state=None):
    if player_state is None:
      current = self.current_session()
      if not current:
        return False
      self._tick(current)
      return True

    player_id = player_state.get("localPlayerId")
    if player_id is None:
      raise ValueError("Offline force_tick requires player_state['localPlayerId']")

    current = {
      "gameServer": None,
      "roomId": player_state.get("roomId", "OFFLINE"),
      "playerId": player_id,
      "pollMs": 200
    }
    player_state["localPlayerId"] = player_id
    self.prepare_offline_session(player_id)
    self._offline_now_seconds = self.offline_time_from_state(player_state, player_id)
    self._offline_actions = []

    try:
      self.update_unit_tracker(player_state)
      self.play_tick(current, player_state)
      return {"actions": list(self._offline_actions)}
    finally:
      self._offline_actions = None
      self._offline_now_seconds = None

  def prepare_offline_session(self, player_id):
    if self._offline_player_id == player_id:
      return

    self._offline_player_id = player_id
    self.worker_spend = 0
    self.combat_spend = 0
    self.upgrade_spend = 0
    self.unit_tracker = {}
    self.last_unit_orders = {}
    self.last_artillery_targets = {}
    self.combat_build_toggle = 0
    self.current_build_phase = BuildPhase.EARLY_GAME
    self.current_game_plan = self.game_plans[self.current_build_phase]

  def offline_time_from_state(self, state, player_id):
    player = state.get("players", {}).get(str(player_id), {})
    return player.get("ticks", 0) * 0.2

  def order_time(self):
    if self._offline_now_seconds is not None:
      return self._offline_now_seconds
    return time.time()

  def action(self, current, action_name, args):
    if self._offline_actions is not None:
      self._offline_actions.append({
        "roomId": current["roomId"],
        "playerId": current["playerId"],
        "action": action_name,
        "args": args
      })
      self.log(f"{action_name} {args}")
      return True

    return ApiClientMixin.action(self, current, action_name, args)

  def _tick(self, current):
    state = self.fetch_state(current)
    self.update_unit_tracker(state)
    self.play_tick(current, state)

  def play_tick(self, current, state):
    if state.get("status") != "playing":
      return
    state["localPlayerId"] = current["playerId"]

    actions_sent = 0
    game_plan = self.select_game_plan(state)
    if game_plan.phase in (BuildPhase.NO_RESOURCES, BuildPhase.FINISH_STAGE):
      self.send_base_assault_orders(current, state)
      return

    if self.should_prioritize_upgrade(game_plan):
      if self.try_upgrade(current, state, game_plan):
        actions_sent += 1
      elif self.try_build(current, state, game_plan):
        actions_sent += 1
    elif self.try_build(current, state, game_plan):
      actions_sent += 1
    elif self.try_upgrade(current, state, game_plan):
      actions_sent += 1

    economy_orders = self.plan_worker_orders(current, state)
    combat_orders = self.plan_combat_orders(current, state)

    for order in self.interleave_orders(economy_orders, combat_orders):
      if actions_sent >= self.max_actions_per_tick:
        break
      if self.send_order(current, order):
        actions_sent += 1

  def send_base_assault_orders(self, current, state):
    actions_sent = 0
    for order in self.plan_base_assault_orders(current, state):
      if actions_sent >= self.max_actions_per_tick:
        break
      if self.send_order(current, order):
        actions_sent += 1

  def try_build(self, current, state, game_plan=None):
    player = state["players"][str(current["playerId"])]
    crystals = player["crystals"]
    if player["baseHp"] <= 0:
      return False

    unit_type = self.choose_build(state, crystals, game_plan=game_plan)
    if not unit_type:
      return False

    if self.action(current, "build", {"unitType": unit_type}):
      if unit_type == "worker":
        self.worker_spend += UNIT_COSTS[unit_type]
      else:
        self.combat_spend += UNIT_COSTS[unit_type]
      return True
    return False

  def try_upgrade(self, current, state, game_plan=None):
    player = state["players"][str(current["playerId"])]
    crystals = player["crystals"]
    if player["baseHp"] <= 0:
      return False
    game_plan = game_plan or self.select_game_plan(state)
    if game_plan.phase not in (BuildPhase.MID_GAME, BuildPhase.LATE_GAME):
      return False
    if self.should_reserve_for_power_tower(state, crystals):
      return False

    upgrade_name = self.choose_upgrade(state, crystals, player.get("techUpgrades", {}), game_plan=game_plan)
    if not upgrade_name:
      return False

    if self.action(current, "upgrade", {"upgradeName": upgrade_name}):
      self.upgrade_spend += self.upgrade_cost(state, player.get("techUpgrades", {}), upgrade_name)
      return True
    return False

  def upgrade_cost(self, state, owned_levels, upgrade_name):
    upgrade = state.get("techTree", {}).get(upgrade_name, {})
    level = owned_levels.get(upgrade_name, 0)
    return upgrade.get("initialCost", 0) + level * upgrade.get("costIncrease", 0)

  def should_prioritize_upgrade(self, game_plan):
    allocation = self.strategy_instance.phase_value(game_plan.phase, "upgradeAllocation", 0)
    try:
      allocation = float(allocation)
    except (TypeError, ValueError):
      allocation = 0
    allocation = max(0.0, min(1.0, allocation))
    if allocation <= 0:
      return False
    if allocation >= 1:
      return True

    total_spend = self.combat_spend + self.upgrade_spend
    if total_spend <= 0:
      return True
    return self.upgrade_spend / total_spend < allocation

  def select_game_plan(self, state):
    return build_order.select_game_plan(self, state)

  def choose_build(self, state, crystals, game_plan=None):
    return build_order.choose_build(self, state, crystals, game_plan=game_plan)

  def build_strategy_phase(self, state):
    return build_order.build_strategy_phase(self, state)

  def next_build_strategy_phase(self, state):
    return build_order.next_build_strategy_phase(self, state)

  def should_reserve_for_power_tower(self, state, crystals):
    return power_tower_micro.should_reserve_for_power_tower(self, state, crystals)

  def mid_base_power_towers_remaining(self, state):
    return power_tower_micro.mid_base_power_towers_remaining(self, state)

  def choose_combat_build(self, state, crystals):
    return build_order.choose_combat_build(self, state, crystals)

  def choose_upgrade(self, state, crystals, owned_levels, game_plan=None):
    return build_order.choose_upgrade(self, state, crystals, owned_levels, game_plan=game_plan)

  def log(self, message):
    if self.verbose:
      print(f"[{self.name}] {message}", flush=True)


def create_offline_bot():
  return OffensiveBot(verbose=False)
