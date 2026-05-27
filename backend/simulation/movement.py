def update_movements(room, now_ms):
  for unit in list(room.units.values()):
    if unit.isMoving:
      midpoint_ms = unit.moveStartTime + ((unit.moveEndTime - unit.moveStartTime) / 2)
      if not unit.hasSnappedToTarget and now_ms >= midpoint_ms:
        unit.x = unit.targetX
        unit.z = unit.targetZ
        unit.hasSnappedToTarget = True
        unit.isGathering = False

      if now_ms >= unit.moveEndTime:
        room.log(f"{room.players[unit.owner]['name']} unit arrived at [{unit.targetX}, {unit.targetZ}]")
        unit.x = unit.targetX
        unit.z = unit.targetZ
        unit.isMoving = False
        unit.moveStartX = None
        unit.moveStartZ = None
        unit.targetX = None
        unit.targetZ = None
        unit.moveStartTime = None
        unit.moveEndTime = None
        unit.hasSnappedToTarget = False
        unit.isGathering = False
