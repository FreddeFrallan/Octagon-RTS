import time

from config import TECH_TREE_CONFIG, UNITS_CONFIG
from map_generator import initalize_map


class Unit:
  def __init__(self, uid, utype, owner, x, z):
    self.id = uid
    self.type = utype  # 'worker', 'mech', or 'artillery'
    self.owner = owner # 1 or 2

    config = UNITS_CONFIG.get(utype, {})
    self.maxHp = config.get("maxHp", 10)
    self.hp = self.maxHp
    self.attack = config.get("attack", 1)
    self.attackCooldown = config.get("attackCooldown", 1000)
    self.moveSpeed = config.get("moveSpeed", 1.0)

    self.x = x
    self.z = z

    self.isMoving = False
    self.moveStartX = None
    self.moveStartZ = None
    self.targetX = None
    self.targetZ = None
    self.moveStartTime = None
    self.moveEndTime = None
    self.hasSnappedToTarget = False

    self.isGathering = False
    self.lastGatherTime = None

    self.lastAttackTime = 0
    self.attackTargetX = None
    self.attackTargetZ = None

  def to_dict(self):
    return {
      "id": self.id,
      "type": self.type,
      "owner": self.owner,
      "hp": self.hp,
      "maxHp": self.maxHp,
      "attack": self.attack,
      "attackCooldown": self.attackCooldown,
      "moveSpeed": self.moveSpeed,
      "x": self.x,
      "z": self.z,
      "isMoving": self.isMoving,
      "moveStartX": self.moveStartX,
      "moveStartZ": self.moveStartZ,
      "targetX": self.targetX,
      "targetZ": self.targetZ,
      "moveStartTime": self.moveStartTime,
      "moveEndTime": self.moveEndTime,
      "hasSnappedToTarget": self.hasSnappedToTarget,
      "isGathering": self.isGathering,
      "lastAttackTime": self.lastAttackTime,
      "attackTargetX": self.attackTargetX,
      "attackTargetZ": self.attackTargetZ
    }


class Cell:
  def __init__(self, x, z):
    self.x = x
    self.z = z
    self.type = 'normal'
    self.owner = 0
    self.gold = 0
    self.maxGold = 0

  def to_dict(self):
    return {
      "x": self.x,
      "z": self.z,
      "type": self.type,
      "owner": self.owner,
      "gold": self.gold,
      "maxGold": self.maxGold
    }


class Room:
  def __init__(self, room_id, map_data=None, map_mode="standard"):
    map_data = map_data or initalize_map()
    self.id = room_id
    self.map_mode = map_mode
    self.status = "lobby"
    self.players = {}
    self.winner = None
    self.event_queues = {1: [], 2: []}
    self.pending_artillery_impacts = []
    self.logs = []
    self.unit_counter = 0
    self.apply_map(map_data)
    self.log("Room created.")

  def apply_map(self, map_data):
    existing_names = {
      player_id: player.get("name")
      for player_id, player in getattr(self, "players", {}).items()
    }

    self.map_name = map_data.get("name", "Untitled Map")
    self.players = {}
    for player_id, player_config in map_data.get("players", {}).items():
      player_id = int(player_id)
      self.players[player_id] = {
        "name": existing_names.get(player_id),
        "crystals": player_config.get("startingCrystals", 100),
        "baseHp": player_config.get("baseHp", 100),
        "maxBaseHp": player_config.get("maxBaseHp", player_config.get("baseHp", 100)),
        "basePos": player_config.get("basePos", {"x": 0, "z": 0}),
        "techUpgrades": {}
      }
    self.winner = None
    self.grid_width = map_data.get("gridWidth", map_data.get("gridSize", 8))
    self.grid_height = map_data.get("gridHeight", map_data.get("gridSize", self.grid_width))
    self.grid_size = self.grid_width

    self.grid = [[Cell(x, z) for z in range(self.grid_height)] for x in range(self.grid_width)]
    for obstacle in map_data.get("obstacles", []):
      cell = self.grid[obstacle["x"]][obstacle["z"]]
      cell.type = 'obstacle'

    for player_id, player in self.players.items():
      base_pos = player["basePos"]
      cell = self.grid[base_pos["x"]][base_pos["z"]]
      cell.type = 'base'
      cell.owner = player_id

    for resource in map_data.get("resources", []):
      cell = self.grid[resource["x"]][resource["z"]]
      cell.type = 'resource'
      cell.gold = resource.get("gold", 200)
      cell.maxGold = resource.get("maxGold", cell.gold)

    self.units = {}
    self.unit_counter = 0

    for unit in map_data.get("startingUnits", []):
      self.spawn_unit(unit["type"], unit["owner"], unit["x"], unit["z"])
    self.pending_artillery_impacts = []

  def generate_unit_id(self):
    self.unit_counter += 1
    return f"unit_{self.unit_counter}"

  def spawn_unit(self, utype, owner, x, z):
    uid = self.generate_unit_id()
    unit = Unit(uid, utype, owner, x, z)
    self.apply_player_upgrades_to_unit(unit)
    self.units[uid] = unit
    return unit

  def get_upgrade_level(self, player_id, upgrade_name):
    return self.players[player_id].get("techUpgrades", {}).get(upgrade_name, 0)

  def get_upgrade_cost(self, player_id, upgrade_name):
    upgrade = TECH_TREE_CONFIG[upgrade_name]
    level = self.get_upgrade_level(player_id, upgrade_name)
    return upgrade.get("initialCost", 0) + (level * upgrade.get("costIncrease", 0))

  def apply_player_upgrades_to_unit(self, unit):
    player = self.players.get(unit.owner)
    if not player:
      return

    for upgrade_name, level in player.get("techUpgrades", {}).items():
      if level <= 0:
        continue
      upgrade = TECH_TREE_CONFIG.get(upgrade_name)
      if not upgrade or upgrade.get("targetUnit") != unit.type:
        continue
      self.apply_upgrade_to_unit(unit, upgrade, level)

  def apply_upgrade_to_unit(self, unit, upgrade, level=1):
    prop = upgrade.get("targetProperty")
    increase = upgrade.get("valueIncrease", 0) * level
    if not hasattr(unit, prop):
      return

    setattr(unit, prop, getattr(unit, prop) + increase)
    if prop == "maxHp":
      unit.hp += increase

  def log(self, text, log_type="system"):
    entry = {"text": text, "type": log_type, "timestamp": int(time.time() * 1000)}
    self.logs.append(entry)
    if len(self.logs) > 50:
      self.logs.pop(0)

  def add_event(self, event):
    self.event_queues[1].append(event)
    self.event_queues[2].append(event)

  def to_dict(self, player_id):
    units = {uid: unit.to_dict() for uid, unit in self.units.items()}
    for unit_data in units.values():
      if unit_data["type"] == "artillery":
        unit_data["attackWillLand"] = None

    for impact in self.pending_artillery_impacts:
      source_unit_id = impact.get("sourceUnitId")
      if source_unit_id in units:
        units[source_unit_id]["attackWillLand"] = {
          "toX": impact["toX"],
          "toZ": impact["toZ"],
          "fireTime": impact["fireTime"],
          "flightTime": impact["flightTime"],
          "impactTime": impact["impactTime"],
          "damage": impact["damage"]
        }

    return {
      "roomId": self.id,
      "mapName": self.map_name,
      "mapMode": self.map_mode,
      "status": self.status,
      "winner": self.winner,
      "techTree": TECH_TREE_CONFIG,
      "players": {str(k): v for k, v in self.players.items()},
      "gridSize": self.grid_size,
      "gridWidth": self.grid_width,
      "gridHeight": self.grid_height,
      "grid": [[c.to_dict() for c in row] for row in self.grid],
      "units": units,
      "logs": self.logs
    }
