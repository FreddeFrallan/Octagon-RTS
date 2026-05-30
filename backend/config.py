import json
import os


def load_json_config(filename):
  try:
    config_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), filename)
    with open(config_path, 'r') as f:
      return json.load(f)
  except Exception as e:
    print(f"Error loading {filename}: {e}")
    return {}


UNITS_CONFIG = load_json_config('units.json')
TECH_TREE_CONFIG = load_json_config('tech_tree.json')


def get_artillery_shell_flight_ms():
  anim_config = UNITS_CONFIG.get("artillery", {}).get("animation", {})
  flight_time = anim_config.get("shellFlightTime", 1000)
  if not isinstance(flight_time, (int, float)) or flight_time <= 0:
    return 1000
  return int(flight_time)
