#!/usr/bin/env node
const http = require('http');

const BOT_NAME = 'JavaScript Worker Bot';
const BOT_PORT = 8787;

let session = null;
let loopTimer = null;

function send(res, status, payload) {
  const body = JSON.stringify(payload);
  res.writeHead(status, {
    'Access-Control-Allow-Origin': '*',
    'Access-Control-Allow-Methods': 'POST, OPTIONS',
    'Access-Control-Allow-Headers': 'Content-Type',
    'Content-Type': 'application/json',
    'Content-Length': Buffer.byteLength(body)
  });
  res.end(body);
}

function readJson(req) {
  return new Promise((resolve, reject) => {
    let body = '';
    req.on('data', chunk => { body += chunk; });
    req.on('end', () => {
      try {
        resolve(body ? JSON.parse(body) : {});
      } catch (err) {
        reject(err);
      }
    });
  });
}

async function getJson(url) {
  const res = await fetch(url);
  if (!res.ok) throw new Error(`GET failed: ${res.status}`);
  return res.json();
}

async function action(actionName, args) {
  if (!session) return;
  await fetch(`${session.gameServer}/api/action`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      roomId: session.roomId,
      playerId: session.playerId,
      action: actionName,
      args
    })
  });
}

function neighbors(x, z, gridSize = 8, gridHeight = gridSize) {
  const coords = z % 2 === 0
    ? [[x - 1, z], [x + 1, z], [x - 1, z - 1], [x, z - 1], [x - 1, z + 1], [x, z + 1]]
    : [[x - 1, z], [x + 1, z], [x, z - 1], [x + 1, z - 1], [x, z + 1], [x + 1, z + 1]];
  return coords.filter(([nx, nz]) => nx >= 0 && nx < gridSize && nz >= 0 && nz < gridHeight);
}

function hexDistance(x1, z1, x2, z2) {
  function offsetToCube(col, row) {
    const x = col - Math.floor((row - (row & 1)) / 2);
    const z = row;
    const y = -x - z;
    return [x, y, z];
  }

  const [ax, ay, az] = offsetToCube(x1, z1);
  const [bx, by, bz] = offsetToCube(x2, z2);
  return Math.max(Math.abs(ax - bx), Math.abs(ay - by), Math.abs(az - bz));
}

function isPassable(cell) {
  return cell.type !== 'base' && cell.type !== 'obstacle' && cell.type !== 'resource';
}

function ownUnits(state, unitType) {
  return Object.values(state.units || {}).filter(unit => {
    return unit.owner === session.playerId && !unit.isMoving && (!unitType || unit.type === unitType);
  });
}

function resourceCells(state) {
  const cells = [];
  for (const row of state.grid) {
    for (const cell of row) {
      if (cell.type === 'resource' && cell.gold > 0) {
        cells.push(cell);
      }
    }
  }
  return cells;
}

function adjacentMiningTiles(state, resource) {
  const width = state.gridWidth || state.gridSize;
  const height = state.gridHeight || state.gridSize;
  return neighbors(resource.x, resource.z, width, height).filter(([x, z]) => {
    return isPassable(state.grid[x][z]);
  });
}

function pickWorkerMove(state) {
  const workers = ownUnits(state, 'worker');
  if (workers.length === 0) return null;

  const width = state.gridWidth || state.gridSize;
  const height = state.gridHeight || state.gridSize;
  const resources = resourceCells(state);

  for (const worker of workers) {
    if (resources.some(resource => hexDistance(worker.x, worker.z, resource.x, resource.z) === 1)) {
      continue;
    }

    const targets = resources.flatMap(resource => adjacentMiningTiles(state, resource));
    if (targets.length > 0) {
      const [targetX, targetZ] = targets.reduce((best, tile) => {
        return hexDistance(worker.x, worker.z, tile[0], tile[1]) < hexDistance(worker.x, worker.z, best[0], best[1])
          ? tile
          : best;
      });

      const candidates = neighbors(worker.x, worker.z, width, height).filter(([x, z]) => isPassable(state.grid[x][z]));
      if (candidates.length > 0) {
        const [x, z] = candidates.reduce((best, tile) => {
          return hexDistance(tile[0], tile[1], targetX, targetZ) < hexDistance(best[0], best[1], targetX, targetZ)
            ? tile
            : best;
        });
        return { unitId: worker.id, x, z };
      }
    }
  }

  if (resources.length > 0) return null;

  const worker = workers[0];
  for (const [nx, nz] of neighbors(worker.x, worker.z, width, height)) {
    if (isPassable(state.grid[nx][nz])) {
      return { unitId: worker.id, x: nx, z: nz };
    }
  }
  return null;
}

async function botTick() {
  if (!session) return;

  try {
    const state = await getJson(`${session.gameServer}/api/state?roomId=${session.roomId}&playerId=${session.playerId}&events=0`);
    const player = state.players[String(session.playerId)];

    if (player.crystals >= 50) {
      await action('build', { unitType: 'worker' });
    }

    const move = pickWorkerMove(state);
    if (move) {
      await action('move', { unitIds: [move.unitId], toX: move.x, toZ: move.z });
    }
  } catch (_) {
    // Ignore transient game-server errors while the lobby is starting or stopping.
  }
}

function startLoop() {
  if (loopTimer) clearInterval(loopTimer);
  loopTimer = setInterval(botTick, session.pollMs || 200);
}

const server = http.createServer(async (req, res) => {
  if (req.method === 'OPTIONS') {
    send(res, 200, { ok: true });
    return;
  }

  if (req.method !== 'POST') {
    send(res, 405, { error: 'Method not allowed' });
    return;
  }

  let payload;
  try {
    payload = await readJson(req);
  } catch (_) {
    send(res, 400, { error: 'Invalid JSON' });
    return;
  }

  if (payload.protocol !== 'octagon-rts-bot-v1') {
    send(res, 400, { error: 'Unsupported bot protocol' });
    return;
  }

  if (req.url === '/handshake') {
    send(res, 200, { ok: true, name: BOT_NAME });
    return;
  }

  if (req.url === '/session') {
    session = {
      gameServer: payload.gameServer,
      roomId: payload.roomId,
      playerId: payload.playerId,
      pollMs: payload.pollMs || 200
    };
    startLoop();
    send(res, 200, { ok: true, name: BOT_NAME });
    return;
  }

  if (req.url === '/stop') {
    session = null;
    if (loopTimer) clearInterval(loopTimer);
    loopTimer = null;
    send(res, 200, { ok: true });
    return;
  }

  send(res, 404, { error: 'Not found' });
});

server.listen(BOT_PORT, '127.0.0.1', () => {
  console.log(`${BOT_NAME} listening on http://127.0.0.1:${BOT_PORT}`);
});
