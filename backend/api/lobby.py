import uuid
import urllib.parse

from models import Room
from state import ROOMS, state_lock


def get_rooms():
  with state_lock:
    rooms_list = []
    for rid, room in ROOMS.items():
      rooms_list.append({
        "id": rid,
        "status": room.status,
        "players": {
          "1": room.players[1]["name"],
          "2": room.players[2]["name"]
        }
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
    state = room.to_dict(player_id)
    if include_events:
      events = list(room.event_queues[player_id])
      room.event_queues[player_id] = []
      state["events"] = events
    else:
      state["events"] = []

  return state, None


def host_room(data):
  name = data.get("playerName", "Host")
  room_id = str(uuid.uuid4())[:4].upper()

  with state_lock:
    room = Room(room_id)
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
    if room.players[2]["name"] is not None:
      return None, "Room is full"

    room.players[2]["name"] = name
    room.log(f"Player 2 ({name}) joined.")

  return {
    "roomId": room_id,
    "playerId": 2,
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

    room.status = "playing"
    room.log("Game started! Real-time combat initialized.")

  return {"success": True}, None
