// game.js
// Client-side game state cache (Hexagonal Edition)

export function offsetToCube(col, row) {
  const x = col - Math.floor((row - (row & 1)) / 2);
  const z = row;
  const y = -x - z;
  return { x, y, z };
}

export function getHexDistance(c1, r1, c2, r2) {
  const a = offsetToCube(c1, r1);
  const b = offsetToCube(c2, r2);
  return Math.max(Math.abs(a.x - b.x), Math.abs(a.y - b.y), Math.abs(a.z - b.z));
}

// Get 6 hexagonal neighbors in offset coordinates
export function getHexNeighbors(x, z, gridSize = 8) {
  const neighbors = [];
  let coords = [];
  if (z % 2 === 0) {
    coords = [[x-1, z], [x+1, z], [x-1, z-1], [x, z-1], [x-1, z+1], [x, z+1]];
  } else {
    coords = [[x-1, z], [x+1, z], [x, z-1], [x+1, z-1], [x, z+1], [x+1, z+1]];
  }

  for (const [nx, nz] of coords) {
    if (nx >= 0 && nx < gridSize && nz >= 0 && nz < gridSize) {
      neighbors.push({ x: nx, z: nz });
    }
  }
  return neighbors;
}

export class Unit {
  constructor(id, type, owner, x, z) {
    this.id = id;
    this.type = type; // 'worker', 'mech', or 'artillery'
    this.owner = owner; // 1 or 2
    const config = (window.UNITS_CONFIG && window.UNITS_CONFIG[type]) || {};
    const defaultMaxHp = type === 'mech' ? 30 : (type === 'artillery' ? 5 : 10);
    const defaultAttack = type === 'mech' ? 8 : (type === 'artillery' ? 16 : 1);
    const defaultAttackCooldown = type === 'artillery' ? 2000 : 1000;
    const defaultMoveSpeed = type === 'mech' ? 1.2 : (type === 'artillery' ? 0.8 : 1.0);
    this.maxHp = config.maxHp ?? defaultMaxHp;
    this.hp = this.maxHp;
    this.attack = config.attack ?? defaultAttack;
    this.attackCooldown = config.attackCooldown ?? defaultAttackCooldown;
    this.moveSpeed = config.moveSpeed ?? defaultMoveSpeed;

    this.x = x;
    this.z = z;
    
    this.isMoving = false;
    this.moveStartX = null;
    this.moveStartZ = null;
    this.targetX = null;
    this.targetZ = null;
    this.moveStartTime = null;
    this.moveEndTime = null;
    this.hasSnappedToTarget = false;
    this.isGathering = false;
    this.lastAttackTime = 0;
    this.attackTargetX = null;
    this.attackTargetZ = null;
  }
}

export class GameCell {
  constructor(x, z) {
    this.x = x;
    this.z = z;
    this.type = 'normal'; // 'normal', 'base', 'resource', 'obstacle'
    this.owner = 0; // 0: neutral, 1: P1, 2: P2
    this.gold = 0;
    this.maxGold = 0;
    this.units = []; // List of Unit objects
  }
}

export class GameState {
  constructor(gridSize = 8) {
    this.gridSize = gridSize;
    this.grid = [];
    this.players = {
      1: { name: 'Host', color: '#0077aa', crystals: 100, baseHp: 100, maxBaseHp: 100, basePos: { x: 0, z: 0 } }, // crystals field represents gold
      2: { name: 'Guest', color: '#cc0055', crystals: 100, baseHp: 100, maxBaseHp: 100, basePos: { x: 7, z: 7 } }
    };
    this.selectedCell = null; // { x, z }
    this.selectedUnitIds = []; // Selected unit IDs on selected tile
    this.logs = [];
    this.gameOver = false;
    this.winner = null;

    this.initGrid();
  }

  initGrid() {
    this.grid = [];
    for (let x = 0; x < this.gridSize; x++) {
      this.grid[x] = [];
      for (let z = 0; z < this.gridSize; z++) {
        this.grid[x][z] = new GameCell(x, z);
      }
    }
  }

  getCell(x, z) {
    if (x >= 0 && x < this.gridSize && z >= 0 && z < this.gridSize) {
      return this.grid[x][z];
    }
    return null;
  }

  // Deserializes state snapshot received from server
  unpackState(data) {
    this.status = data.status;
    this.gameOver = (data.status === 'gameover');
    this.winner = data.winner;
    this.logs = data.logs;

    // Unpack Player States
    for (const pidStr in data.players) {
      const pid = parseInt(pidStr);
      const serverPlayer = data.players[pidStr];
      if (this.players[pid]) {
        this.players[pid].name = serverPlayer.name || (pid === 1 ? 'Cyan Sector' : 'Magenta Empire');
        this.players[pid].crystals = serverPlayer.crystals;
        this.players[pid].baseHp = serverPlayer.baseHp;
        this.players[pid].maxBaseHp = serverPlayer.maxBaseHp;
      }
    }

    // Unpack Grid Cells
    for (let x = 0; x < this.gridSize; x++) {
      for (let z = 0; z < this.gridSize; z++) {
        const serverCell = data.grid[x][z];
        const localCell = this.grid[x][z];
        localCell.type = serverCell.type;
        localCell.owner = serverCell.owner;
        localCell.gold = serverCell.gold;
        localCell.maxGold = serverCell.maxGold;
        localCell.units = []; // Clear units to re-populate
      }
    }

    // Unpack Live Units
    for (const uid in data.units) {
      const su = data.units[uid];
      const unit = new Unit(su.id, su.type, su.owner, su.x, su.z);
      unit.hp = su.hp;
      unit.maxHp = su.maxHp;
      unit.attack = su.attack;
      unit.attackCooldown = su.attackCooldown;
      unit.moveSpeed = su.moveSpeed;
      unit.isMoving = su.isMoving;
      unit.moveStartX = su.moveStartX;
      unit.moveStartZ = su.moveStartZ;
      unit.targetX = su.targetX;
      unit.targetZ = su.targetZ;
      unit.moveStartTime = su.moveStartTime;
      unit.moveEndTime = su.moveEndTime;
      unit.hasSnappedToTarget = su.hasSnappedToTarget;
      unit.isGathering = su.isGathering;
      unit.lastAttackTime = su.lastAttackTime;
      unit.attackTargetX = su.attackTargetX;
      unit.attackTargetZ = su.attackTargetZ;

      // Moving units are associated with their authoritative server cell.
      // The server snaps this association to the target cell at 50% travel.
      const targetCellX = unit.x;
      const targetCellZ = unit.z;
      
      const cell = this.getCell(targetCellX, targetCellZ);
      if (cell) {
        cell.units.push(unit);
      }
    }

    // Clean up selections if units are no longer present on selected tile
    if (this.selectedCell) {
      const cell = this.getCell(this.selectedCell.x, this.selectedCell.z);
      if (cell) {
        this.selectedUnitIds = this.selectedUnitIds.filter(id => 
          cell.units.some(u => u.id === id)
        );
      } else {
        this.selectedCell = null;
        this.selectedUnitIds = [];
      }
    }
  }

  toggleUnitSelection(unitId) {
    const idx = this.selectedUnitIds.indexOf(unitId);
    if (idx >= 0) {
      this.selectedUnitIds.splice(idx, 1);
    } else {
      this.selectedUnitIds.push(unitId);
    }
  }

  selectAllUnitsInSelected(playerId) {
    if (!this.selectedCell) return;
    const cell = this.getCell(this.selectedCell.x, this.selectedCell.z);
    if (!cell) return;
    
    this.selectedUnitIds = cell.units
      .filter(u => u.owner === playerId)
      .map(u => u.id);
  }
}
