import uuid
import urllib.parse

from models import Room
from map_generator import generate_random_map, initalize_map, load_random_map_settings, save_random_map_settings
from state import ROOMS, state_lock


MAP_MODES = {
  "standard": "StandardMap",
  "random": "CustomMap"
}


def get_rooms():
  with state_lock:
    rooms_list = []
    for rid, room in ROOMS.items():
      rooms_list.append({
        "id": rid,
        "status": room.status,
        "mapMode": room.map_mode,
        "playerCount": room.player_count,
        "players": {str(player_id): player["name"] for player_id, player in room.players.items()}
      })
  return rooms_list


def get_state(query_str):
  params = urllib.parse.parse_qs(query_str)
  room_id = params.get('roomId', [None])[0]
  player_str = params.get('playerId', [None])[0]
  include_events = params.get('events', ['1'])[0] != '0'

  if not room_id or not player_str:
    return None, "Missing roomId or playerId"

  player_id = int(player_str)

  with state_lock:
    if room_id not in ROOMS:
      return None, "Room not found"

    room = ROOMS[room_id]
    if player_id not in room.players:
      return None, "Player not found"
    state = room.to_dict(player_id)
    if include_events:
      visible_cells = room.visible_cells_for_player(player_id)
      events = [
        event for event in room.event_queues[player_id]
        if room.event_is_visible_to_player(event, visible_cells)
      ]
      room.event_queues[player_id] = []
      state["events"] = events
    else:
      state["events"] = []

  return state, None


def host_room(data):
  name = data.get("playerName", "Host")
  player_count = max(2, min(int(data.get("playerCount", 2)), 4))
  room_id = str(uuid.uuid4())[:4].upper()

  with state_lock:
    room = Room(room_id, player_count=player_count)
    room.players[1]["name"] = name
    ROOMS[room_id] = room

  return {
    "roomId": room_id,
    "playerId": 1,
    "playerName": name
  }, None


def join_room(data):
  name = data.get("playerName", "Guest")
  room_id = data.get("roomId", "").upper()

  with state_lock:
    if room_id not in ROOMS:
      return None, "Room code invalid"

    room = ROOMS[room_id]
    open_slots = [
      player_id for player_id, player in room.players.items()
      if player_id != 1 and player["name"] is None
    ]
    if not open_slots:
      return None, "Room is full"

    player_id = open_slots[0]
    room.players[player_id]["name"] = name
    room.log(f"Player {player_id} ({name}) joined.")

  return {
    "roomId": room_id,
    "playerId": player_id,
    "playerName": name
  }, None


def start_room(data):
  room_id = data.get("roomId")
  player_id = data.get("playerId")

  with state_lock:
    if room_id not in ROOMS:
      return None, "Room not found"

    room = ROOMS[room_id]
    if player_id != 1:
      return None, "Only Host can start game"
    if any(player["name"] is None for player in room.players.values()):
      return None, "Waiting for all players to join"

    try:
      if room.map_mode == "random":
        room.apply_map(generate_random_map(room.player_count))
      else:
        room.apply_map(initalize_map(room.player_count))
    except ValueError as e:
      return None, str(e)

    room.status = "playing"
    room.log("Game started! Real-time combat initialized.")

  return {"success": True}, None


def set_room_map(data):
  room_id = data.get("roomId")
  player_id = data.get("playerId")
  map_mode = data.get("mapMode", "standard")

  if map_mode not in MAP_MODES:
    return None, "Unknown map mode"

  with state_lock:
    if room_id not in ROOMS:
      return None, "Room not found"

    room = ROOMS[room_id]
    if room.status != "lobby":
      return None, "Map cannot be changed after the match starts"
    if player_id != 1:
      return None, "Only Host can change map"

    room.map_mode = map_mode
    room.map_name = MAP_MODES[map_mode]
    room.log(f"Map set to {MAP_MODES[map_mode]}.")

  return {"success": True, "mapMode": map_mode, "mapName": MAP_MODES[map_mode]}, None


def set_map_settings(data):
  room_id = data.get("roomId")
  player_id = data.get("playerId")
  settings = data.get("settings")

  if not isinstance(settings, dict):
    return None, "Missing map settings"

  with state_lock:
    if room_id not in ROOMS:
      return None, "Room not found"

    room = ROOMS[room_id]
    if room.status != "lobby":
      return None, "Map settings cannot be changed after the match starts"
    if player_id != 1:
      return None, "Only Host can change map settings"
    if room.map_mode != "random":
      return None, "Map settings are only available for CustomMap"

    current = load_random_map_settings()
    updated = {**current, **settings}
    saved = save_random_map_settings(updated)
    room.log("CustomMap settings updated.")

  return {"success": True, "settings": saved}, None
