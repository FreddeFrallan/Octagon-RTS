import time

from config import UNITS_CONFIG


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
  def __init__(self, room_id):
    self.id = room_id
    self.status = "lobby"
    self.players = {
      1: {"name": None, "crystals": 100, "baseHp": 100, "maxBaseHp": 100, "basePos": {"x": 0, "z": 0}},
      2: {"name": None, "crystals": 100, "baseHp": 100, "maxBaseHp": 100, "basePos": {"x": 7, "z": 7}}
    }
    self.winner = None
    self.grid_size = 8

    self.grid = [[Cell(x, z) for z in range(self.grid_size)] for x in range(self.grid_size)]
    self.grid[0][0].type = 'base'
    self.grid[0][0].owner = 1
    self.grid[7][7].type = 'base'
    self.grid[7][7].owner = 2

    resource_locations = [
      (2, 2), (5, 5), (2, 5), (5, 2),
      (0, 4), (4, 0), (7, 3), (3, 7)
    ]
    for rx, rz in resource_locations:
      cell = self.grid[rx][rz]
      cell.type = 'resource'
      cell.gold = 200
      cell.maxGold = 200

    self.units = {}
    self.unit_counter = 0

    self.spawn_unit("worker", 1, 1, 0)
    self.spawn_unit("worker", 2, 6, 7)

    self.event_queues = {1: [], 2: []}
    self.pending_artillery_impacts = []

    self.logs = []
    self.log("Room created.")

  def generate_unit_id(self):
    self.unit_counter += 1
    return f"unit_{self.unit_counter}"

  def spawn_unit(self, utype, owner, x, z):
    uid = self.generate_unit_id()
    unit = Unit(uid, utype, owner, x, z)
    self.units[uid] = unit
    return unit

  def log(self, text, log_type="system"):
    entry = {"text": text, "type": log_type, "timestamp": int(time.time() * 1000)}
    self.logs.append(entry)
    if len(self.logs) > 50:
      self.logs.pop(0)

  def add_event(self, event):
    self.event_queues[1].append(event)
    self.event_queues[2].append(event)

  def to_dict(self, player_id):
    return {
      "roomId": self.id,
      "status": self.status,
      "winner": self.winner,
      "players": {str(k): v for k, v in self.players.items()},
      "gridSize": self.grid_size,
      "grid": [[c.to_dict() for c in row] for row in self.grid],
      "units": {uid: u.to_dict() for uid, u in self.units.items()},
      "logs": self.logs
    }
