from GeneralStrategy.settings import SquadType
from Units.Artillery import micro as artillery_micro
from Units.Mech import micro as mech_micro
from Units.PowerTower import micro as power_tower_micro
from Units.Worker import micro as worker_micro


class CombatPlannerMixin:
  def plan_worker_orders(self, current, state):
    return worker_micro.plan_worker_orders(self, current, state)

  def plan_power_tower_orders(self, current, state, workers, enemies, planned_tower_tiles):
    return power_tower_micro.plan_power_tower_orders(self, current, state, workers, enemies, planned_tower_tiles)

  def power_tower_goals(self, current, state):
    return power_tower_micro.power_tower_goals(self, current, state)

  def needs_defensive_power_tower(self, state):
    return power_tower_micro.needs_defensive_power_tower(self, state)

  def defensive_power_towers_near_base(self, state, base):
    return power_tower_micro.defensive_power_towers_near_base(self, state, base)

  def power_towers_near_base(self, state, base):
    return power_tower_micro.power_towers_near_base(self, state, base)

  def defensive_power_tower_goals(self, state):
    return power_tower_micro.defensive_power_tower_goals(self, state)

  def base_power_tower_goals(self, state, base):
    return power_tower_micro.base_power_tower_goals(self, state, base)

  def center_power_tower_goals(self, state, base):
    return power_tower_micro.center_power_tower_goals(self, state, base)

  def closest_available_worker(self, workers, goal, assigned_workers, enemies):
    return power_tower_micro.closest_available_worker(self, workers, goal, assigned_workers, enemies)

  def is_valid_power_tower_tile(self, state, x, z):
    return power_tower_micro.is_valid_power_tower_tile(self, state, x, z)

  def choose_resource_targets(self, worker, state, resources, enemies, reserved_tiles=None):
    return worker_micro.choose_resource_targets(self, worker, state, resources, enemies, reserved_tiles)

  def choose_worker_step(self, worker, state, target, enemies, reserved_tiles=None):
    return worker_micro.choose_worker_step(self, worker, state, target, enemies, reserved_tiles)

  def plan_combat_orders(self, current, state):
    base_target = self.enemy_base_target(current, state)
    if not base_target:
      return []

    orders = []
    phase = self.build_strategy_phase(state)
    squads = self.build_squads(state, phase)
    allocated_unit_ids = self.squad_allocated_unit_ids(squads)
    for squad in squads:
      order = self.plan_squad_order(state, squad, base_target)
      if isinstance(order, list):
        orders.extend(order)
      elif order:
        orders.append(order)

    for unit in self.own_units(state, stationary=True):
      if unit["id"] in allocated_unit_ids:
        continue
      order = self.plan_unallocated_combat_unit_order(state, unit, base_target)
      if order:
        orders.append(order)

    return orders

  def build_squads(self, state, phase):
    return mech_micro.build_squads(self, state, phase)

  def squad_allocated_unit_ids(self, squads):
    return mech_micro.allocated_unit_ids(squads)

  def plan_squad_order(self, state, squad, base_target):
    squad_type = squad["type"] if isinstance(squad, dict) else squad.squad_type
    if squad_type == SquadType.SNEAKY_ARTILLERY:
      return self.plan_sneaky_artillery_order(state, squad, base_target)
    if squad_type == SquadType.WORKER_HUNTER:
      return self.plan_worker_hunter_order(state, squad, base_target)
    if squad_type == SquadType.MECH:
      return self.plan_mech_squad_order(state, squad, base_target)
    return None

  def plan_unallocated_combat_unit_order(self, state, unit, base_target):
    if unit["type"] == "mech":
      return None
    return None

  def plan_worker_hunter_order(self, state, squad, base_target):
    return mech_micro.plan_worker_hunter_order(self, state, squad, base_target)

  def plan_mech_squad_order(self, state, squad, base_target):
    return mech_micro.plan_mech_squad_order(self, state, squad, base_target)

  def plan_sneaky_artillery_order(self, state, squad, base_target):
    return artillery_micro.plan_sneaky_artillery_order(self, state, squad, base_target)

  def enemy_in_way(self, state, unit, goals):
    return mech_micro.enemy_in_way(self, state, unit, goals)

  def nearby_mech_attack_target(self, state, mech, max_steps=3):
    return mech_micro.nearby_mech_attack_target(self, state, mech, max_steps=max_steps)

  def enemy_worker_target(self, state, unit):
    return mech_micro.enemy_worker_target(self, state, unit)

  def artillery_target_in_way(self, state, artillery, goals):
    return artillery_micro.artillery_target_in_way(self, state, artillery, goals)

  def artillery_power_tower_target(self, state, artillery):
    return artillery_micro.artillery_power_tower_target(self, state, artillery)

  def artillery_combat_retreat_order(self, state, artillery):
    return artillery_micro.artillery_combat_retreat_order(self, state, artillery)

  def artillery_is_reloading(self, artillery):
    return artillery_micro.artillery_is_reloading(self, artillery)

  def nearest_enemy_mech_distance(self, state, unit):
    return artillery_micro.nearest_enemy_mech_distance(self, state, unit)

  def nearby_enemy_mech(self, state, unit, max_distance=2):
    return artillery_micro.nearby_enemy_mech(self, state, unit, max_distance=max_distance)

  def artillery_target_priority(self, enemy):
    return artillery_micro.artillery_target_priority(self, enemy)

  def artillery_target_square(self, state, artillery, target_unit):
    return artillery_micro.artillery_target_square(self, state, artillery, target_unit)

  def target_arrival_time_ms(self, target_unit):
    return artillery_micro.target_arrival_time_ms(self, target_unit)

  def artillery_target_destination(self, target_unit):
    return artillery_micro.artillery_target_destination(self, target_unit)

  def target_direction(self, target_unit, tracker):
    return artillery_micro.target_direction(self, target_unit, tracker)

  def normalize_step(self, dx, dz):
    return (
      0 if dx == 0 else (1 if dx > 0 else -1),
      0 if dz == 0 else (1 if dz > 0 else -1)
    )

  def is_valid_artillery_target(self, state, artillery, x, z):
    return artillery_micro.is_valid_artillery_target(self, state, artillery, x, z)

  def sneaky_artillery_goals(self, state, artillery, base_target):
    return artillery_micro.sneaky_artillery_goals(self, state, artillery, base_target)

  def flank_attack_goals(self, state, artillery, base_target):
    return artillery_micro.flank_attack_goals(self, state, artillery, base_target)

  def flank_lane_goals(self, state, artillery, base_target):
    return artillery_micro.flank_lane_goals(self, state, artillery, base_target)

  def is_flank_position(self, state, unit, base_target):
    return artillery_micro.is_flank_position(self, state, unit, base_target)

  def is_flank_coord(self, state, z, unit, base_target):
    return artillery_micro.is_flank_coord(self, state, z, unit, base_target)

  def flank_lane_z(self, state, unit, base_target):
    return artillery_micro.flank_lane_z(self, state, unit, base_target)
