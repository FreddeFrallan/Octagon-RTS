import time

from simulation.artillery import resolve_artillery_impacts, update_artillery
from simulation.bases import update_base_attacks
from simulation.combat import resolve_close_combat
from simulation.gathering import update_gathering
from simulation.movement import update_movements
from simulation.passive_income import update_passive_income
from state import ROOMS, state_lock


def tick_rooms():
  now_ms = int(time.time() * 1000)
  with state_lock:
    for room_id, room in list(ROOMS.items()):
      if room.status != "playing":
        continue

      for player in room.players.values():
        if player.get("baseHp", 0) > 0:
          player["ticks"] = player.get("ticks", 0) + 1

      update_movements(room, now_ms)

      resolve_artillery_impacts(room, now_ms)
      if room.status != "playing":
        continue

      resolve_close_combat(room, now_ms)
      update_gathering(room, now_ms)
      update_artillery(room, now_ms)

      base_ticks_key = "_last_base_attack_tick"
      last_base_attack = getattr(room, base_ticks_key, 0)
      if now_ms - last_base_attack >= 1000:
        setattr(room, base_ticks_key, now_ms)
        update_passive_income(room)
        update_base_attacks(room, now_ms)


def game_loop_thread():
  while True:
    tick_rooms()
    time.sleep(0.1)
