import argparse
import importlib
import json
import sys
import time
from dataclasses import dataclass
from pathlib import Path


BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
  sys.path.insert(0, str(BACKEND_DIR))

from api.actions import apply_action
from map_generator import generate_random_map, initalize_map
from models import Room
from simulation.loop import tick_room

try:
  from .dummy_bot import DummyBot
except ImportError:
  from offline_simulation.dummy_bot import DummyBot


DEFAULT_TICK_SECONDS = 0.2


@dataclass
class OfflineSimulationResult:
  room: Room
  ticks: int
  simulated_ms: int
  elapsed_seconds: float
  actions_sent: int
  rejected_actions: list


def build_offline_room(player_count, map_mode="standard"):
  if map_mode == "random":
    map_data = generate_random_map(player_count)
  elif map_mode == "standard":
    map_data = initalize_map(player_count)
  else:
    raise ValueError(f"Unknown map mode: {map_mode}")

  room = Room("OFFLINE", map_data=map_data, map_mode=map_mode, player_count=player_count)
  for player_id, player in room.players.items():
    player["name"] = f"Offline Bot {player_id}"
  room.status = "playing"
  room.log("Offline simulation started.")
  return room


def normalize_actions(bot_result):
  if bot_result is None or bot_result is False:
    return []

  if isinstance(bot_result, str):
    bot_result = json.loads(bot_result)

  if isinstance(bot_result, list):
    return bot_result

  if isinstance(bot_result, dict):
    if "actions" in bot_result:
      actions = bot_result["actions"]
      if actions is None:
        return []
      if not isinstance(actions, list):
        raise ValueError("actions must be a list")
      return actions
    if "action" in bot_result:
      return [bot_result]

  raise ValueError("force_tick must return an action, a list of actions, an actions object, or None")


def player_state(room, player_id):
  state = room.to_dict(player_id)
  state["events"] = []
  state["localPlayerId"] = player_id
  return state


def apply_bot_action(room, player_id, action, now_ms):
  if not isinstance(action, dict):
    return False, "Action must be a JSON object"

  action_type = action.get("action")
  args = action.get("args", {})
  if not action_type:
    return False, "Missing action"
  if not isinstance(args, dict):
    return False, "Action args must be an object"

  payload_player_id = action.get("playerId", player_id)
  if payload_player_id != player_id:
    return False, f"Bot for player {player_id} returned action for player {payload_player_id}"

  return apply_action(room, player_id, action_type, args, now_ms=now_ms)


def run_offline_simulation(
  player_count=2,
  bot_factories=None,
  max_ticks=1000,
  tick_seconds=DEFAULT_TICK_SECONDS,
  map_mode="standard"
):
  if player_count < 2 or player_count > 4:
    raise ValueError("player_count must be between 2 and 4")
  if max_ticks < 1:
    raise ValueError("max_ticks must be at least 1")
  if tick_seconds <= 0:
    raise ValueError("tick_seconds must be positive")

  if bot_factories is None:
    bot_factories = [lambda player_id=player_id: DummyBot(f"Offline Dummy Bot {player_id}") for player_id in range(1, player_count + 1)]
  if len(bot_factories) != player_count:
    raise ValueError("bot_factories length must match player_count")

  bots = [factory() for factory in bot_factories]
  room = build_offline_room(player_count, map_mode=map_mode)
  simulated_ms = 0
  tick_ms = int(tick_seconds * 1000)
  actions_sent = 0
  rejected_actions = []
  start = time.perf_counter()

  for tick_index in range(max_ticks):
    if room.status != "playing":
      break

    simulated_ms += tick_ms
    tick_room(room, simulated_ms)
    if room.status != "playing":
      break

    planned_actions = []
    for player_id, bot in zip(sorted(room.players), bots):
      if room.players[player_id].get("baseHp", 0) <= 0:
        continue

      state = player_state(room, player_id)
      try:
        actions = normalize_actions(bot.force_tick(state))
      except Exception as exc:
        rejected_actions.append({
          "tick": tick_index + 1,
          "playerId": player_id,
          "error": f"force_tick failed: {exc}"
        })
        continue

      planned_actions.append((player_id, actions))

    for player_id, actions in planned_actions:
      for action in actions:
        success, error = apply_bot_action(room, player_id, action, simulated_ms)
        if success:
          actions_sent += 1
        else:
          rejected_actions.append({
            "tick": tick_index + 1,
            "playerId": player_id,
            "action": action,
            "error": error
          })

  elapsed_seconds = time.perf_counter() - start
  return OfflineSimulationResult(
    room=room,
    ticks=room.players[1].get("ticks", 0),
    simulated_ms=simulated_ms,
    elapsed_seconds=elapsed_seconds,
    actions_sent=actions_sent,
    rejected_actions=rejected_actions
  )


def load_bot_factory(dotted_path):
  module_name, _, object_name = dotted_path.partition(":")
  if not module_name or not object_name:
    raise ValueError("Bot path must use module:object format")

  module = importlib.import_module(module_name)
  bot_object = getattr(module, object_name)
  return bot_object


def parse_args():
  parser = argparse.ArgumentParser(description="Run an Octagon-RTS match between local Python bot objects.")
  parser.add_argument("--players", type=int, default=2, help="Number of bot players, from 2 to 4. Default: 2")
  parser.add_argument("--ticks", type=int, default=1000, help="Maximum 0.2 second ticks to simulate. Default: 1000")
  parser.add_argument("--tick-seconds", type=float, default=DEFAULT_TICK_SECONDS, help="Simulated seconds per tick. Default: 0.2")
  parser.add_argument("--map-mode", choices=["standard", "random"], default="standard", help="Map mode. Default: standard")
  parser.add_argument(
    "--bot",
    action="append",
    default=[],
    help="Python bot class/factory in module:object format. Repeat once per player. Defaults to dummy bots."
  )
  return parser.parse_args()


def main():
  args = parse_args()
  bot_factories = [load_bot_factory(path) for path in args.bot] if args.bot else None
  result = run_offline_simulation(
    player_count=args.players,
    bot_factories=bot_factories,
    max_ticks=args.ticks,
    tick_seconds=args.tick_seconds,
    map_mode=args.map_mode
  )

  print(f"status={result.room.status}")
  print(f"winner={result.room.winner}")
  print(f"ticks={result.ticks}")
  print(f"simulated_seconds={result.simulated_ms / 1000:.1f}")
  print(f"elapsed_seconds={result.elapsed_seconds:.3f}")
  print(f"actions_sent={result.actions_sent}")
  print(f"rejected_actions={len(result.rejected_actions)}")
  if result.rejected_actions:
    print(json.dumps(result.rejected_actions[:10], indent=2))


if __name__ == "__main__":
  main()
