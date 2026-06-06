from abc import ABC, abstractmethod


class Squad(ABC):
  virtual_unit_type = None
  minimum_units = 1

  def __init__(self, units, goal):
    self.units = list(units)
    self.goal = goal

  @property
  @abstractmethod
  def squad_type(self):
    pass

  @property
  def leader(self):
    return self.units[0] if self.units else None

  @property
  def unit_ids(self):
    return [unit["id"] for unit in self.units]

  def contains_unit(self, unit):
    return unit.get("id") in self.unit_ids

  def is_ready(self):
    return len(self.units) >= self.minimum_units

  def to_virtual_unit(self):
    leader = self.leader
    if not leader:
      return None

    return {
      "id": self.virtual_unit_id,
      "type": self.virtual_unit_type,
      "owner": leader["owner"],
      "x": leader["x"],
      "z": leader["z"],
      "isMoving": any(unit.get("isMoving") for unit in self.units),
      "units": self.units,
      "unitIds": self.unit_ids
    }

  @property
  def virtual_unit_id(self):
    return f"{self.virtual_unit_type}:{'-'.join(self.unit_ids)}"
