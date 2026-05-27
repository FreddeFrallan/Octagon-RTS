from hex_grid import get_neighbors


def update_gathering(room, now_ms):
  for unit in list(room.units.values()):
    if unit.type == 'worker' and not unit.isMoving:
      resource_cell = adjacent_resource_cell(room, unit.x, unit.z)
      if resource_cell:
        if unit.lastGatherTime is None or now_ms - unit.lastGatherTime >= 2000:
          amount = min(resource_cell.gold, 25)
          resource_cell.gold -= amount
          room.players[unit.owner]["crystals"] += amount
          unit.lastGatherTime = now_ms
          unit.isGathering = True

          room.log(f"{room.players[unit.owner]['name']} worker harvested {amount} gold from [{resource_cell.x}, {resource_cell.z}]", "gather")

          room.add_event({
            "type": "gather_beam",
            "workerX": unit.x,
            "workerZ": unit.z,
            "x": resource_cell.x,
            "z": resource_cell.z,
            "amount": amount
          })

          if resource_cell.gold <= 0:
            resource_cell.type = 'normal'
            room.log(f"Gold node at [{resource_cell.x}, {resource_cell.z}] depleted.")
            for worker in room.units.values():
              if worker.type == 'worker' and is_adjacent_to(worker.x, worker.z, resource_cell.x, resource_cell.z, room):
                worker.isGathering = False
      else:
        unit.isGathering = False


def adjacent_resource_cell(room, x, z):
  for nx, nz in get_neighbors(x, z, room.grid_width, room.grid_height):
    cell = room.grid[nx][nz]
    if cell.type == 'resource' and cell.gold > 0:
      return cell
  return None


def is_adjacent_to(x, z, target_x, target_z, room):
  return (target_x, target_z) in get_neighbors(x, z, room.grid_width, room.grid_height)
