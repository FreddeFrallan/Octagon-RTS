import json
import os


def load_units_config():
  try:
    config_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'units.json')
    with open(config_path, 'r') as f:
      return json.load(f)
  except Exception as e:
    print(f"Error loading units.json: {e}")
    return {}


UNITS_CONFIG = load_units_config()


def get_artillery_shell_flight_ms():
  anim_config = UNITS_CONFIG.get("artillery", {}).get("animation", {})
  flight_time = anim_config.get("shellFlightTime", 1000)
  if not isinstance(flight_time, (int, float)) or flight_time <= 0:
    return 1000
  return int(flight_time)
