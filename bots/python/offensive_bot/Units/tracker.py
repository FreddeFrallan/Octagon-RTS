import time


class UnitTrackerMixin:
  def update_unit_tracker(self, state):
    now = self.order_time() if hasattr(self, "order_time") else time.time()
    seen_unit_ids = set()

    for unit_id, unit in state.get("units", {}).items():
      seen_unit_ids.add(unit_id)
      current_pos = (unit["x"], unit["z"])
      previous = self.unit_tracker.get(unit_id)

      if not previous:
        self.unit_tracker[unit_id] = {
          "last_pos": current_pos,
          "stationary_since": now if not unit.get("isMoving") else None,
          "last_direction": None
        }
        continue

      last_pos = previous["last_pos"]
      direction = previous.get("last_direction")
      if current_pos != last_pos:
        direction = (current_pos[0] - last_pos[0], current_pos[1] - last_pos[1])
        stationary_since = now if not unit.get("isMoving") else None
      elif unit.get("isMoving"):
        stationary_since = None
      else:
        stationary_since = previous.get("stationary_since") or now

      tracked = dict(previous)
      tracked.update({
        "last_pos": current_pos,
        "stationary_since": stationary_since,
        "last_direction": direction
      })
      self.unit_tracker[unit_id] = tracked

    for unit_id in list(self.unit_tracker):
      if unit_id not in seen_unit_ids:
        self.unit_tracker.pop(unit_id, None)
