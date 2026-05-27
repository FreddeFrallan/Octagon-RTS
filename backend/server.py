# server.py
# Authoritative Real-Time Game Server with match lobby and tick loops (Hexagonal Grid Edition)

from http.server import SimpleHTTPRequestHandler, HTTPServer
import errno
import socketserver
import json
import uuid
import threading
import time
import socket
import urllib.parse
import random
import os

# Load units configuration
UNITS_CONFIG = {}
try:
  config_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'units.json')
  with open(config_path, 'r') as f:
    UNITS_CONFIG = json.load(f)
except Exception as e:
  print(f"Error loading units.json: {e}")

# Global state lock
state_lock = threading.Lock()

# Rooms database
ROOMS = {}

def get_artillery_shell_flight_ms():
  anim_config = UNITS_CONFIG.get("artillery", {}).get("animation", {})
  flight_time = anim_config.get("shellFlightTime", 1000)
  if not isinstance(flight_time, (int, float)) or flight_time <= 0:
    return 1000
  return int(flight_time)

class Unit:
  def __init__(self, uid, utype, owner, x, z):
    self.id = uid
    self.type = utype  # 'worker', 'mech', or 'artillery'
    self.owner = owner # 1 or 2
    
    # Load stats from config
    config = UNITS_CONFIG.get(utype, {})
    self.maxHp = config.get("maxHp", 10)
    self.hp = self.maxHp
    self.attack = config.get("attack", 1)
    self.moveSpeed = config.get("moveSpeed", 1.0)
      
    self.x = x
    self.z = z
    
    # Real-time properties
    self.isMoving = False
    self.targetX = None
    self.targetZ = None
    self.moveStartTime = None
    self.moveEndTime = None
    
    self.isGathering = False
    self.lastGatherTime = None
    
    self.lastAttackTime = 0 # timestamp of last artillery shot
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
      "moveSpeed": self.moveSpeed,
      "x": self.x,
      "z": self.z,
      "isMoving": self.isMoving,
      "targetX": self.targetX,
      "targetZ": self.targetZ,
      "moveStartTime": self.moveStartTime,
      "moveEndTime": self.moveEndTime,
      "isGathering": self.isGathering,
      "lastAttackTime": self.lastAttackTime,
      "attackTargetX": self.attackTargetX,
      "attackTargetZ": self.attackTargetZ
    }

class Cell:
  def __init__(self, x, z):
    self.x = x
    self.z = z
    self.type = 'normal' # 'normal', 'base', 'resource'
    self.owner = 0 # 0 (neutral), 1 (P1), 2 (P2)
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
    self.status = "lobby" # "lobby", "playing", "gameover"
    self.players = {
      1: {"name": None, "crystals": 100, "baseHp": 100, "maxBaseHp": 100, "basePos": {"x": 0, "z": 0}},
      2: {"name": None, "crystals": 100, "baseHp": 100, "maxBaseHp": 100, "basePos": {"x": 7, "z": 7}}
    }
    self.winner = None
    self.grid_size = 8
    
    # Initialize logic cells
    self.grid = [[Cell(x, z) for z in range(self.grid_size)] for x in range(self.grid_size)]
    self.grid[0][0].type = 'base'
    self.grid[0][0].owner = 1
    self.grid[7][7].type = 'base'
    self.grid[7][7].owner = 2

    # Gold resource nodes placement
    resource_locations = [
      (2, 2), (5, 5), (2, 5), (5, 2),
      (0, 4), (4, 0), (7, 3), (3, 7)
    ]
    for rx, rz in resource_locations:
      cell = self.grid[rx][rz]
      cell.type = 'resource'
      cell.gold = 200
      cell.maxGold = 200

    # Live units list
    self.units = {}
    self.unit_counter = 0

    # Spawn starting units (1 worker spawned adjacent to base)
    self.spawn_unit("worker", 1, 1, 0)
    self.spawn_unit("worker", 2, 6, 7)

    # Event queues for each player to broadcast action animations (lasers, hits) exactly once
    self.event_queues = {1: [], 2: []}
    self.pending_artillery_impacts = []
    
    # Global logs
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

# --- Hexagonal Grid Math Helpers ---

def get_neighbors(x, z, grid_size=8):
  # Pointy-topped odd-r offset coordinates
  neighbors = []
  if z % 2 == 0:
    # Even rows
    coords = [(x-1, z), (x+1, z), (x-1, z-1), (x, z-1), (x-1, z+1), (x, z+1)]
  else:
    # Odd rows
    coords = [(x-1, z), (x+1, z), (x, z-1), (x+1, z-1), (x, z+1), (x+1, z+1)]
  
  for nx, nz in coords:
    if 0 <= nx < grid_size and 0 <= nz < grid_size:
      neighbors.append((nx, nz))
  return neighbors

def offset_to_cube(col, row):
  x = col - (row - (row & 1)) // 2
  z = row
  y = -x - z
  return x, y, z

def get_hex_distance(x1, z1, x2, z2):
  ax, ay, az = offset_to_cube(x1, z1)
  bx, by, bz = offset_to_cube(x2, z2)
  return max(abs(ax - bx), abs(ay - by), abs(az - bz))

def resolve_artillery_impact(room, impact):
  tx = impact["toX"]
  tz = impact["toZ"]
  damage = impact["damage"]
  attacker_owner = impact["attackerOwner"]
  target_cell = room.grid[tx][tz]

  hit_base = False
  base_owner = 0
  if target_cell.type == 'base':
    hit_base = True
    base_owner = target_cell.owner
    base_player = room.players[base_owner]
    base_player["baseHp"] = max(0, base_player["baseHp"] - damage)
    room.log(f"💥 Artillery shell impacts Base at [{tx}, {tz}] dealing {damage} damage!", "combat")

    if base_player["baseHp"] <= 0:
      room.log(f"Base of {base_player['name']} destroyed!")
      room.status = "gameover"
      room.winner = attacker_owner

  targets_here = [tu for tu in room.units.values() if tu.x == tx and tu.z == tz and not tu.isMoving]
  hit_any_unit = False
  first_target_owner = 0
  for victim in list(targets_here):
    if first_target_owner == 0:
      first_target_owner = victim.owner
    victim.hp -= damage
    hit_any_unit = True
    room.log(f"💥 Artillery blast impacts [{tx}, {tz}] dealing {damage} damage to {room.players[victim.owner]['name']}'s {victim.type.upper()}!", "combat")
    if victim.hp <= 0:
      room.log(f"💀 {room.players[victim.owner]['name']}'s {victim.type.upper()} destroyed by artillery blast!", "combat")
      room.units.pop(victim.id, None)

  if not hit_base and not hit_any_unit:
    room.log(f"💥 Artillery shell impacts empty cell [{tx}, {tz}]")

  room.add_event({
    "type": "artillery_impact",
    "toX": tx,
    "toZ": tz,
    "damage": damage if (hit_base or hit_any_unit) else 0,
    "isBase": hit_base,
    "targetOwner": base_owner if hit_base else first_target_owner
  })

# --- Authoritative loops updating rooms in the background ---

def tick_rooms():
  now_ms = int(time.time() * 1000)
  with state_lock:
    for room_id, room in list(ROOMS.items()):
      if room.status != "playing":
        continue

      # 1. Update Unit Movements
      for unit in list(room.units.values()):
        if unit.isMoving and now_ms >= unit.moveEndTime:
          room.log(f"{room.players[unit.owner]['name']} unit arrived at [{unit.targetX}, {unit.targetZ}]")
          unit.x = unit.targetX
          unit.z = unit.targetZ
          unit.isMoving = False
          unit.targetX = None
          unit.targetZ = None
          unit.moveStartTime = None
          unit.moveEndTime = None
          unit.isGathering = False

      # 1.5. Resolve artillery impacts after their shell flight reaches the target cell
      pending_impacts = []
      for impact in room.pending_artillery_impacts:
        if now_ms >= impact["impactTime"]:
          resolve_artillery_impact(room, impact)
        else:
          pending_impacts.append(impact)
      room.pending_artillery_impacts = pending_impacts
      if room.status != "playing":
        continue

      # 2. Update Resource Gathering (every 2.0s tick per worker automatically when on resource tile)
      for unit in list(room.units.values()):
        if unit.type == 'worker' and not unit.isMoving:
          cell = room.grid[unit.x][unit.z]
          if cell.type == 'resource' and cell.gold > 0:
            if unit.lastGatherTime is None or now_ms - unit.lastGatherTime >= 2000:
              amount = min(cell.gold, 25)
              cell.gold -= amount
              room.players[unit.owner]["crystals"] += amount # crystals field stores gold
              unit.lastGatherTime = now_ms
              unit.isGathering = True
              
              room.log(f"{room.players[unit.owner]['name']} worker harvested {amount} gold at [{unit.x}, {unit.z}]", "gather")
              
              room.add_event({
                "type": "gather_beam",
                "x": unit.x,
                "z": unit.z,
                "amount": amount
              })

              if cell.gold <= 0:
                cell.type = 'normal'
                room.log(f"Gold node at [{unit.x}, {unit.z}] depleted.")
                for w in room.units.values():
                  if w.x == unit.x and w.z == unit.z:
                     w.isGathering = False
          else:
            unit.isGathering = False

      # 2.5. Update Artillery Auto-firing (runs once per 2.0s per active artillery)
      for unit in list(room.units.values()):
        if unit.type == 'artillery' and not unit.isMoving and unit.attackTargetX is not None and unit.attackTargetZ is not None:
          if now_ms - unit.lastAttackTime >= 2000:
            unit.lastAttackTime = now_ms
            tx = unit.attackTargetX
            tz = unit.attackTargetZ
            
            # Verify range (in case it somehow changed, but normally it shouldn't)
            dist = get_hex_distance(unit.x, unit.z, tx, tz)
            art_config = UNITS_CONFIG.get("artillery", {})
            min_range = art_config.get("minRange", 1)
            max_range = art_config.get("maxRange", 2)
            if dist < min_range or dist > max_range:
              # Stop firing if target somehow went out of range
              unit.attackTargetX = None
              unit.attackTargetZ = None
              continue
            
            damage = art_config.get("attack", 16) 
            shell_flight_ms = get_artillery_shell_flight_ms()
            room.pending_artillery_impacts.append({
              "attackerOwner": unit.owner,
              "toX": tx,
              "toZ": tz,
              "damage": damage,
              "impactTime": now_ms + shell_flight_ms
            })
            room.log(f"💥 Artillery fires at [{tx}, {tz}]", "combat")

            # Add client event
            room.add_event({
              "type": "artillery_shell",
              "fromX": unit.x, "fromZ": unit.z,
              "toX": tx, "toZ": tz,
              "flightTime": shell_flight_ms
            })

      # 3. Update Real-Time Combat ticks (runs once per 1.0s)
      combat_ticks_key = f"_last_combat_tick_{room_id}"
      last_combat = getattr(tick_rooms, combat_ticks_key, 0)
      
      if now_ms - last_combat >= 1000:
        setattr(tick_rooms, combat_ticks_key, now_ms)
        
        # Build unit grouping per cell (only mechs/workers, since artillery can't fight on same tile)
        cells_units = {}
        for u in room.units.values():
          if not u.isMoving:
            coord = (u.x, u.z)
            cells_units.setdefault(coord, []).append(u)

        for coord, units_on_cell in cells_units.items():
          cx, cz = coord
          p1_here = [u for u in units_on_cell if u.owner == 1]
          p2_here = [u for u in units_on_cell if u.owner == 2]

          if p1_here and p2_here:
            # Battle ensues!
            p1_dmg = sum(u.attack for u in p1_here)
            p2_dmg = sum(u.attack for u in p2_here)

            target2 = random.choice(p2_here)
            target2.hp -= p1_dmg
            room.log(f"Cyan deals {p1_dmg} damage to Magenta {target2.type} (HP: {max(0, target2.hp)}/{target2.maxHp})", "combat")
            room.add_event({"type": "combat_hit", "x": cx, "z": cz, "damage": p1_dmg, "targetOwner": 2})

            target1 = random.choice(p1_here)
            target1.hp -= p2_dmg
            room.log(f"Magenta deals {p2_dmg} damage to Cyan {target1.type} (HP: {max(0, target1.hp)}/{target1.maxHp})", "combat")
            room.add_event({"type": "combat_hit", "x": cx, "z": cz, "damage": p2_dmg, "targetOwner": 1})

            # Remove dead units
            for u in units_on_cell:
              if u.hp <= 0:
                room.log(f"💀 {room.players[u.owner]['name']}'s {u.type.upper()} was destroyed in battle!", "combat")
                room.units.pop(u.id, None)

        # 4. Check adjacent base shellings (Mechs and Workers only attack adjacent tiles)
        for base_owner, base_pos in [(1, (0, 0)), (2, (7, 7))]:
          bx, bz = base_pos
          base_player = room.players[base_owner]
          if base_player["baseHp"] <= 0:
            continue
          
          # Gather all hostiles adjacent to this base (6 hex neighbors)
          hostiles = []
          for tx, tz in get_neighbors(bx, bz, room.grid_size):
            # Check for enemy units on this adjacent tile
            for u in room.units.values():
              if u.x == tx and u.z == tz and u.owner != base_owner and not u.isMoving:
                # If there are defenders occupying the same cell as attacker, attacker fights them first
                defenders = [d for d in room.units.values() if d.x == tx and d.z == tz and d.owner == base_owner and not d.isMoving]
                if not defenders:
                  hostiles.append(u)
          
          if hostiles:
            hostile_dmg = sum(u.attack for u in hostiles)
            base_player["baseHp"] = max(0, base_player["baseHp"] - hostile_dmg)
            room.log(f"💥 Hostiles shell Base from adjacent hexes! Deals {hostile_dmg} damage (Base HP: {base_player['baseHp']}/{base_player['maxBaseHp']})", "combat")
            
            # Fire a laser from each hostile to base
            for u in hostiles:
              room.add_event({
                "type": "combat_hit",
                "x": bx,
                "z": bz,
                "damage": u.attack,
                "targetOwner": base_owner,
                "isBase": True,
                "attackerX": u.x,
                "attackerZ": u.z
              })

            if base_player["baseHp"] <= 0:
              room.log(f"🏆 Base destroyed! Game over.")
              room.status = "gameover"
              room.winner = hostiles[0].owner

def game_loop_thread():
  while True:
    tick_rooms()
    time.sleep(0.1)

# Start logic update thread
t = threading.Thread(target=game_loop_thread, daemon=True)
t.start()

class GameRequestHandler(SimpleHTTPRequestHandler):
  def translate_path(self, path):
    parsed_path = urllib.parse.urlparse(path).path
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if parsed_path == "/units.json":
      return os.path.join(base_dir, "backend", "units.json")
    else:
      rel_path = parsed_path.lstrip('/')
      if not rel_path:
        rel_path = 'index.html'
      return os.path.join(base_dir, "frontend", rel_path)

  def end_headers(self):
    self.send_header('Access-Control-Allow-Origin', '*')
    self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
    self.send_header('Access-Control-Allow-Headers', 'Content-Type')
    super().end_headers()

  def do_OPTIONS(self):
    self.send_response(200)
    self.end_headers()

  def do_GET(self):
    url = urllib.parse.urlparse(self.path)
    if url.path.startswith('/api/rooms'):
      self.handle_get_rooms()
    elif url.path.startswith('/api/ip'):
      self.send_json({"ip": get_local_ip()})
    elif url.path.startswith('/api/state'):
      self.handle_get_state(url.query)
    else:
      super().do_GET()

  def do_POST(self):
    url = urllib.parse.urlparse(self.path)
    content_length = int(self.headers.get('Content-Length', 0))
    body = self.rfile.read(content_length).decode('utf-8') if content_length > 0 else ""
    data = json.loads(body) if body else {}

    if url.path.startswith('/api/host'):
      self.handle_post_host(data)
    elif url.path.startswith('/api/join'):
      self.handle_post_join(data)
    elif url.path.startswith('/api/start'):
      self.handle_post_start(data)
    elif url.path.startswith('/api/action'):
      self.handle_post_action(data)
    else:
      self.send_response(404)
      self.end_headers()

  # --- API Handlers ---

  def handle_get_rooms(self):
    with state_lock:
      rooms_list = []
      for rid, r in ROOMS.items():
        rooms_list.append({
          "id": rid,
          "status": r.status,
          "players": {
            "1": r.players[1]["name"],
            "2": r.players[2]["name"]
          }
        })
    self.send_json(rooms_list)

  def handle_get_state(self, query_str):
    params = urllib.parse.parse_qs(query_str)
    room_id = params.get('roomId', [None])[0]
    player_str = params.get('playerId', [None])[0]
    include_events = params.get('events', ['1'])[0] != '0'

    if not room_id or not player_str:
      self.send_error_json("Missing roomId or playerId")
      return

    player_id = int(player_str)

    with state_lock:
      if room_id not in ROOMS:
        self.send_error_json("Room not found")
        return
      
      room = ROOMS[room_id]
      state = room.to_dict(player_id)
      if include_events:
        events = list(room.event_queues[player_id])
        room.event_queues[player_id] = []
        state["events"] = events
      else:
        state["events"] = []

    self.send_json(state)

  def handle_post_host(self, data):
    name = data.get("playerName", "Host")
    room_id = str(uuid.uuid4())[:4].upper()
    
    with state_lock:
      room = Room(room_id)
      room.players[1]["name"] = name
      ROOMS[room_id] = room
      
    self.send_json({
      "roomId": room_id,
      "playerId": 1,
      "playerName": name
    })

  def handle_post_join(self, data):
    name = data.get("playerName", "Guest")
    room_id = data.get("roomId", "").upper()

    with state_lock:
      if room_id not in ROOMS:
        self.send_error_json("Room code invalid")
        return
      
      room = ROOMS[room_id]
      if room.players[2]["name"] is not None:
        self.send_error_json("Room is full")
        return
      
      room.players[2]["name"] = name
      room.log(f"Player 2 ({name}) joined.")

    self.send_json({
      "roomId": room_id,
      "playerId": 2,
      "playerName": name
    })

  def handle_post_start(self, data):
    room_id = data.get("roomId")
    player_id = data.get("playerId")

    with state_lock:
      if room_id not in ROOMS:
        self.send_error_json("Room not found")
        return
      
      room = ROOMS[room_id]
      if player_id != 1:
        self.send_error_json("Only Host can start game")
        return
      
      room.status = "playing"
      room.log("Game started! Real-time combat initialized.")

    self.send_json({"success": True})

  def handle_post_action(self, data):
    room_id = data.get("roomId")
    player_id = data.get("playerId")
    action_type = data.get("action")
    args = data.get("args", {})

    with state_lock:
      if room_id not in ROOMS:
        self.send_error_json("Room not found")
        return
      
      room = ROOMS[room_id]
      if room.status != "playing":
        self.send_error_json("Game not running")
        return

      success = False
      error_msg = ""

      # --- Real-Time API Movement order (Hexagonal) ---
      if action_type == "move":
        unit_ids = args.get("unitIds", [])
        tx = args.get("toX")
        tz = args.get("toZ")

        valid = True
        for uid in unit_ids:
          if uid not in room.units:
            valid = False
            error_msg = "Unit does not exist"
            break
          u = room.units[uid]
          if u.owner != player_id:
            valid = False
            error_msg = "You don't own this unit"
            break
          if u.isMoving:
            valid = False
            error_msg = "Unit is already traveling"
            break
          
          # Check if target is a neighbor in the hex grid
          neighbors = get_neighbors(u.x, u.z, room.grid_size)
          if (tx, tz) not in neighbors:
            valid = False
            error_msg = "Invalid coordinate target"
            break
          
          if room.grid[tx][tz].type == 'base':
            valid = False
            error_msg = "Cannot enter building structures"
            break

        if valid:
          now_ms = int(time.time() * 1000)
          for uid in unit_ids:
            u = room.units[uid]
            u.isMoving = True
            u.targetX = tx
            u.targetZ = tz
            u.moveStartTime = now_ms
            duration = int(1500 / u.moveSpeed) if u.moveSpeed > 0 else 1500
            u.moveEndTime = now_ms + duration
            u.isGathering = False
            u.attackTargetX = None
            u.attackTargetZ = None

          room.log(f"{room.players[player_id]['name']} ordered {len(unit_ids)} unit(s) to [{tx}, {tz}]")
          success = True

      # --- Real-Time API Build order (Hexagonal Adjacent Spawns) ---
      elif action_type == "build":
        utype = args.get("unitType")
        cost = UNITS_CONFIG.get(utype, {}).get("cost", 50)
        player = room.players[player_id]

        if player["crystals"] < cost:
          error_msg = "Insufficient Gold"
        elif player["baseHp"] <= 0:
          error_msg = "Base is destroyed"
        else:
          bx, bz = (0, 0) if player_id == 1 else (7, 7)
          
          # Find valid adjacent spawning cells (within bounds, not bases)
          spawn_spots = []
          for tx, tz in get_neighbors(bx, bz, room.grid_size):
            if room.grid[tx][tz].type != 'base':
              spawn_spots.append((tx, tz))
          
          if spawn_spots:
            player["crystals"] -= cost
            sx, sz = random.choice(spawn_spots)
            new_unit = room.spawn_unit(utype, player_id, sx, sz)
            room.log(f"{player['name']} spawned {utype} at [{sx}, {sz}].", "build")
            success = True
          else:
            error_msg = "No open adjacent spawning ground around base"

      # --- Real-Time API Artillery Shelling order (Distance 1-2) ---
      elif action_type == "attack":
        unit_ids = args.get("unitIds", [])
        tx = args.get("toX")
        tz = args.get("toZ")

        artillery_units = []
        for uid in unit_ids:
          if uid in room.units:
            u = room.units[uid]
            if u.type == 'artillery' and u.owner == player_id and not u.isMoving:
              dist = get_hex_distance(u.x, u.z, tx, tz)
              art_config = UNITS_CONFIG.get("artillery", {})
              min_range = art_config.get("minRange", 1)
              max_range = art_config.get("maxRange", 2)
              if min_range <= dist <= max_range:
                artillery_units.append(u)

        if artillery_units:
          success = True
          for u in artillery_units:
            u.attackTargetX = tx
            u.attackTargetZ = tz
            u.lastAttackTime = 0 # fire immediately on next tick
        else:
          success = False
          error_msg = "No stationary artillery units in range selected"

      # --- Real-Time API Stop Artillery Fire order ---
      elif action_type == "stop":
        unit_ids = args.get("unitIds", [])
        
        valid = False
        for uid in unit_ids:
          if uid in room.units:
            u = room.units[uid]
            if u.type == 'artillery' and u.owner == player_id:
              u.attackTargetX = None
              u.attackTargetZ = None
              valid = True
              
        if valid:
          success = True
          room.log(f"{room.players[player_id]['name']} stopped artillery fire.")
        else:
          error_msg = "No active artillery units selected"

      if success:
        self.send_json({"success": True})
      else:
        self.send_error_json(error_msg or "Unknown action error")

  # --- JSON Utilities ---

  def send_json(self, data):
    self.send_response(200)
    self.send_header('Content-Type', 'application/json')
    payload = json.dumps(data).encode('utf-8')
    self.send_header('Content-Length', str(len(payload)))
    self.end_headers()
    self.wfile.write(payload)

  def send_error_json(self, msg):
    self.send_response(400)
    self.send_header('Content-Type', 'application/json')
    payload = json.dumps({"error": msg}).encode('utf-8')
    self.send_header('Content-Length', str(len(payload)))
    self.end_headers()
    self.wfile.write(payload)

def get_local_ip():
  try:
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.connect(("8.8.8.8", 80))
    ip = s.getsockname()[0]
    s.close()
    return ip
  except Exception:
    return "127.0.0.1"

class ThreadingHTTPServer(socketserver.ThreadingMixIn, HTTPServer):
  pass

def create_server(host, port):
  try:
    return ThreadingHTTPServer((host, port), GameRequestHandler)
  except OSError as e:
    if e.errno != errno.EADDRINUSE:
      raise

    bind_addr = "localhost" if host in ("0.0.0.0", "::", "127.0.0.1") else host
    print("="*60)
    print(f"Cannot start server: {bind_addr}:{port} is already in use.")
    print("Another Octagon-RTS server or another app is already using that port.")
    print(f"Stop the existing process, or start this server on another port:")
    print(f"  PORT={port + 1} python3 backend/server.py")
    print(f"  PORT={port + 1} ./start-localhost.sh")
    print("="*60)
    raise SystemExit(1) from e

if __name__ == '__main__':
  HOST = os.environ.get("HOST", "0.0.0.0")
  PORT = int(os.environ.get("PORT", "8000"))
  local_ip = get_local_ip()
  print("="*60)
  print(f"OCTO-COMMAND Authoritative Multiplayer Game Server starting...")
  print(f"Server is running locally at: http://localhost:{PORT}")
  if HOST in ("0.0.0.0", "::"):
    print(f"Local Network IP: http://{local_ip}:{PORT}")
    print("Ask your friend on the same network to join using the network IP!")
  else:
    print(f"Bound to: {HOST}:{PORT}")
  print("="*60)

  server = create_server(HOST, PORT)
  try:
    server.serve_forever()
  except KeyboardInterrupt:
    print("\nServer shutting down.")
    server.server_close()
