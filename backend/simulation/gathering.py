def update_gathering(room, now_ms):
  for unit in list(room.units.values()):
    if unit.type == 'worker' and not unit.isMoving:
      cell = room.grid[unit.x][unit.z]
      if cell.type == 'resource' and cell.gold > 0:
        if unit.lastGatherTime is None or now_ms - unit.lastGatherTime >= 2000:
          amount = min(cell.gold, 25)
          cell.gold -= amount
          room.players[unit.owner]["crystals"] += amount
          unit.lastGatherTime = now_ms
          unit.isGathering = True

          room.log(f"{room.players[unit.owner]['name']} worker harvested {amount} gold at [{unit.x}, {unit.z}]", "gather")

          room.add_event({
            "type": "gather_beam",
            "x": unit.x,
            "z": unit.z,
            "amount": amount
          })

          if cell.gold <= 0:
            cell.type = 'normal'
            room.log(f"Gold node at [{unit.x}, {unit.z}] depleted.")
            for worker in room.units.values():
              if worker.x == unit.x and worker.z == unit.z:
                worker.isGathering = False
      else:
        unit.isGathering = False
