import time

from GeneralStrategy.settings import BUILD_TOWER_ORDER_REPEAT_SECONDS, MOVE_ORDER_REPEAT_SECONDS


class OrderMixin:
  def interleave_orders(self, economy_orders, combat_orders):
    max_len = max(len(economy_orders), len(combat_orders))
    for idx in range(max_len):
      if idx < len(economy_orders):
        yield economy_orders[idx]
      if idx < len(combat_orders):
        yield combat_orders[idx]

  def send_order(self, current, order):
    now = self.order_time() if hasattr(self, "order_time") else time.time()

    if order["action"] == "move":
      unit_id = order["args"]["unitIds"][0]
      to_x = order["args"]["toX"]
      to_z = order["args"]["toZ"]
      key = (to_x, to_z)
      last_key, last_time = self.last_unit_orders.get(unit_id, (None, 0))
      repeat_seconds = self.strategy_instance.micro_value("orders", "moveRepeatSeconds", MOVE_ORDER_REPEAT_SECONDS)
      if last_key == key and now - last_time < repeat_seconds:
        return False
      if self.action(current, "move", order["args"]):
        self.last_unit_orders[unit_id] = (key, now)
        return True
      return False

    if order["action"] == "attack":
      unit_id = order["args"]["unitIds"][0]
      target = (order["args"]["toX"], order["args"]["toZ"])
      suppress_repeated_targets = self.strategy_instance.micro_value("orders", "suppressRepeatedAttackTargets", True)
      if suppress_repeated_targets and self.last_artillery_targets.get(unit_id) == target:
        return False
      if self.action(current, "attack", order["args"]):
        self.last_artillery_targets[unit_id] = target
        return True
      return False

    if order["action"] == "buildTower":
      worker_id = order["args"]["workerId"]
      key = ("buildTower",)
      last_key, last_time = self.last_unit_orders.get(worker_id, (None, 0))
      repeat_seconds = self.strategy_instance.micro_value("orders", "buildTowerRepeatSeconds", BUILD_TOWER_ORDER_REPEAT_SECONDS)
      if last_key == key and now - last_time < repeat_seconds:
        return False
      if self.action(current, "buildTower", order["args"]):
        self.last_unit_orders[worker_id] = (key, now)
        return True
      return False

    return self.action(current, order["action"], order["args"])

  def move_order(self, unit_ids, x, z):
    if isinstance(unit_ids, str):
      unit_ids = [unit_ids]
    return {
      "action": "move",
      "args": {"unitIds": unit_ids, "toX": x, "toZ": z}
    }

  def build_tower_order(self, worker_id):
    return {
      "action": "buildTower",
      "args": {"workerId": worker_id}
    }

  def attack_order(self, unit_id, x, z):
    return {
      "action": "attack",
      "args": {"unitIds": [unit_id], "toX": x, "toZ": z}
    }

  def order_unit_id(self, order):
    args = order.get("args", {})
    if order.get("action") == "buildTower":
      return args.get("workerId")
    unit_ids = args.get("unitIds", [])
    return unit_ids[0] if unit_ids else None
