// app.js
// Client Controller: coordinates lobby, real-time networking, logic, and 3D rendering (Bright Grass Theme)

import { GameState, getHexDistance } from './game.js';
import { GameRenderer } from './renderer.js';
import * as THREE from 'three';

let game = null;
let renderer = null;
let lastHovered = null;

// Dynamic units configuration from units.json
let unitsConfig = {
  worker: { cost: 50, maxHp: 10, attack: 1, minRange: 1, maxRange: 1 },
  mech: { cost: 100, maxHp: 30, attack: 8, minRange: 1, maxRange: 1 },
  artillery: { cost: 80, maxHp: 5, attack: 16, minRange: 1, maxRange: 2 }
};
window.UNITS_CONFIG = unitsConfig;

function updateUILabels() {
  const wSpan = btnBuildWorker.querySelector('.cost');
  if (wSpan && unitsConfig.worker) wSpan.innerText = `🪙 ${unitsConfig.worker.cost}`;
  
  const mSpan = btnBuildMech.querySelector('.cost');
  if (mSpan && unitsConfig.mech) mSpan.innerText = `🪙 ${unitsConfig.mech.cost}`;
  
  const aSpan = btnBuildArtillery.querySelector('.cost');
  if (aSpan && unitsConfig.artillery) aSpan.innerText = `🪙 ${unitsConfig.artillery.cost}`;

  const attackSpan = btnAttack.querySelector('.cost');
  if (attackSpan && unitsConfig.artillery) {
    attackSpan.innerText = `Range ${unitsConfig.artillery.minRange}-${unitsConfig.artillery.maxRange}`;
  }
}


// Network variables
let roomId = null;
let playerId = null;
let playerName = "Commander";
let apiBase = window.location.origin; // Dynamically updated on join

// Polling intervals
let lobbyPollInterval = null;
let gamePollInterval = null;

// Game states
let isMoveMode = false;
let isAttackMode = false;

// DOM Elements - Lobby Screen
const lobbyScreen = document.getElementById('lobby-screen');
const lobbySetup = document.getElementById('lobby-setup');
const lobbyWaitingHost = document.getElementById('lobby-waiting-host');
const lobbyWaitingGuest = document.getElementById('lobby-waiting-guest');

// Inputs
const inputPlayerName = document.getElementById('player-name');
const inputServerIp = document.getElementById('server-ip');
const inputRoomCode = document.getElementById('room-code');

// Buttons
const btnHostLobby = document.getElementById('btn-host-lobby');
const btnJoinLobby = document.getElementById('btn-join-lobby');
const btnStartGame = document.getElementById('btn-start-game');

// Lobby Text Displays
const hostRoomCode = document.getElementById('host-room-code');
const hostServerIp = document.getElementById('host-server-ip');
const slotHostName = document.getElementById('slot-host-name');
const slotGuestName = document.getElementById('slot-guest-name');
const guestRoomCode = document.getElementById('guest-room-code');
const guestSlotHost = document.getElementById('guest-slot-host');
const guestSlotGuest = document.getElementById('guest-slot-guest');

// HUD Displays
const activePlayerIndicator = document.getElementById('active-player-indicator');
const activePlayerName = document.getElementById('active-player-name');
const roleTag = document.getElementById('role-tag');
const resourceCount = document.getElementById('resource-count');
const hudRoomCode = document.getElementById('hud-room-code');
const selectionName = document.getElementById('selection-name');
const selectionCoord = document.getElementById('selection-coord');
const selectionUnitStack = document.getElementById('selection-unit-stack');

// Context Action Buttons
const btnGather = document.getElementById('action-gather');
const btnAttack = document.getElementById('action-attack');
const btnStopFire = document.getElementById('action-stop');
const buildOptionsContainer = document.getElementById('build-options-container');
const btnBuildWorker = document.getElementById('action-build-worker');
const btnBuildMech = document.getElementById('action-build-mech');
const btnBuildArtillery = document.getElementById('action-build-artillery');

// Modals
const instructionsModal = document.getElementById('instructions-modal');
const closeInstructionsBtn = document.getElementById('close-instructions');
const toggleRulesBtn = document.getElementById('instructions-btn');
const endGameModal = document.getElementById('end-game-modal');
const endTitle = document.getElementById('end-title');
const endWinnerText = document.getElementById('end-winner-text');
const btnRestart = document.getElementById('action-restart');

// --- Initialization ---

function init() {
  // Bind lobby buttons
  btnHostLobby.addEventListener('click', handleHostLobby);
  btnJoinLobby.addEventListener('click', handleJoinLobby);
  btnStartGame.addEventListener('click', handleStartGame);

  // Bind instructions modal
  closeInstructionsBtn.addEventListener('click', () => instructionsModal.classList.add('hidden'));
  if (toggleRulesBtn) {
    toggleRulesBtn.addEventListener('click', () => instructionsModal.classList.remove('hidden'));
  }

  // Bind HUD contextual actions
  btnAttack.addEventListener('click', handleAttackAction);
  btnStopFire.addEventListener('click', handleStopFireAction);
  btnBuildWorker.addEventListener('click', () => handleBuildAction('worker'));
  btnBuildMech.addEventListener('click', () => handleBuildAction('mech'));
  btnBuildArtillery.addEventListener('click', () => handleBuildAction('artillery'));

  btnRestart.addEventListener('click', handleRestartLobby);

  // Populate local IP suggestion in setup
  inputServerIp.value = window.location.host;

  // Load dynamic units configuration
  fetch('/units.json')
    .then(res => res.json())
    .then(data => {
      unitsConfig = data;
      window.UNITS_CONFIG = data;
      updateUILabels();
    })
    .catch(err => {
      console.warn("Failed to load units.json, using default stats:", err);
      updateUILabels();
    });
}

// --- Lobby HTTP client actions ---

async function handleHostLobby() {
  playerName = inputPlayerName.value.trim() || "Commander";
  apiBase = window.location.origin;

  try {
    const res = await fetch(`${apiBase}/api/host`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ playerName })
    });
    
    if (!res.ok) throw new Error("Failed to create room");
    const data = await res.json();
    
    roomId = data.roomId;
    playerId = 1;

    // Fetch local network IP from server
    const ipRes = await fetch(`${apiBase}/api/ip`);
    const ipData = await ipRes.json();
    
    // Setup Host UI state
    hostRoomCode.innerText = roomId;
    hostServerIp.innerText = `${ipData.ip}:8000`;
    slotHostName.innerText = playerName;
    
    lobbySetup.classList.add('hidden');
    lobbyWaitingHost.classList.remove('hidden');

    // Start waiting room polling
    lobbyPollInterval = setInterval(pollLobbyState, 500);

  } catch (err) {
    alert(err.message);
  }
}

async function handleJoinLobby() {
  playerName = inputPlayerName.value.trim() || "Commander";
  let hostIp = inputServerIp.value.trim() || window.location.host;
  let code = inputRoomCode.value.trim().toUpperCase();

  if (!code) {
    alert("Please enter a Room Code");
    return;
  }

  // Format connection address
  if (!hostIp.startsWith('http://') && !hostIp.startsWith('https://')) {
    hostIp = 'http://' + hostIp;
  }
  apiBase = hostIp;

  try {
    const res = await fetch(`${apiBase}/api/join`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ roomId: code, playerName })
    });

    if (!res.ok) {
      const errData = await res.json();
      throw new Error(errData.error || "Join failed");
    }

    const data = await res.json();
    roomId = data.roomId;
    playerId = 2;

    // Setup Guest UI state
    guestRoomCode.innerText = roomId;
    
    lobbySetup.classList.add('hidden');
    lobbyWaitingGuest.classList.remove('hidden');

    // Start waiting room polling
    lobbyPollInterval = setInterval(pollLobbyState, 500);

  } catch (err) {
    alert(err.message);
  }
}

async function handleStartGame() {
  try {
    const res = await fetch(`${apiBase}/api/start`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ roomId, playerId })
    });
    if (!res.ok) throw new Error("Failed to start game");
  } catch (err) {
    alert(err.message);
  }
}

// Polling while waiting inside the room lobby
async function pollLobbyState() {
  try {
    const res = await fetch(`${apiBase}/api/state?roomId=${roomId}&playerId=${playerId}`);
    if (!res.ok) return;
    const data = await res.json();

    if (playerId === 1) {
      // Host: check if player 2 joined
      const guestName = data.players[2]?.name;
      if (guestName) {
        slotGuestName.innerText = guestName;
        slotGuestName.parentElement.classList.add('occupied');
        btnStartGame.disabled = false; // enable play button
      } else {
        slotGuestName.innerText = "Waiting for player...";
        slotGuestName.parentElement.classList.remove('occupied');
        btnStartGame.disabled = true;
      }
    }

    // Launch game screen if started
    if (data.status === "playing") {
      clearInterval(lobbyPollInterval);
      lobbyPollInterval = null;
      startGameSession(data);
    }
  } catch (err) {
    console.error("Lobby poll error", err);
  }
}

// Transition from lobby screen to active 3D board
function startGameSession(initialState) {
  lobbyScreen.classList.add('hidden');
  instructionsModal.classList.remove('hidden');

  // Initialize GameState client
  game = new GameState();
  game.unpackState(initialState);

  // Initialize WebGL Renderer
  renderer = new GameRenderer('game-canvas', game);
  
  // Set canvas raycasters
  const canvasElement = document.getElementById('game-canvas');
  canvasElement.addEventListener('click', onCanvasClick);
  canvasElement.addEventListener('mousemove', onCanvasMouseMove);
  canvasElement.addEventListener('contextmenu', onCanvasRightClick);

  // Establish high-frequency sync loop
  gamePollInterval = setInterval(pollGameState, 200);

  updateHUD();
}

// --- High-Frequency Sync Loop ---

async function pollGameState() {
  try {
    const res = await fetch(`${apiBase}/api/state?roomId=${roomId}&playerId=${playerId}`);
    if (!res.ok) return;
    const data = await res.json();

    // 1. Unpack details
    game.unpackState(data);

    // 2. Process and trigger local events (combat damage & gathering laser effects)
    if (data.events && data.events.length > 0) {
      data.events.forEach(e => {
        if (e.type === "combat_hit") {
          const targetPos = renderer.gridToWorld(e.x, e.z);
          const dest = new THREE.Vector3(targetPos.x, targetPos.y + (e.isBase ? 0.6 : 0.3), targetPos.z);
          const originOffset = new THREE.Vector3();

          // Shelling from adjacent tiles
          if (e.attackerX !== undefined && e.attackerZ !== undefined) {
            const attPos = renderer.gridToWorld(e.attackerX, e.attackerZ);
            originOffset.set(attPos.x, attPos.y + 0.3, attPos.z);
          } else {
            originOffset.copy(targetPos);
            originOffset.x += (Math.random() - 0.5) * 1.5;
            originOffset.z += (Math.random() - 0.5) * 1.5;
            originOffset.y += 0.5;
          }
          
          const teamColor = e.targetOwner === 1 ? 0xff0055 : 0x00f0ff; // firing team color
          renderer.createLaserBeam(originOffset, dest, teamColor);

          // Trigger particle hit
          setTimeout(() => {
            renderer.createExplosion(dest.x, dest.y, dest.z);
          }, 100);

          // Project floating text
          const isP1Target = e.targetOwner === 1;
          const textColors = isP1Target ? 'rgba(0, 119, 170, 1)' : 'rgba(204, 0, 85, 1)';
          renderer.showFloatingDamageText(e.x, e.z, `-${e.damage} HP`, textColors);

        } else if (e.type === "gather_beam") {
          const targetPos = renderer.gridToWorld(e.x, e.z);
          const topPoint = new THREE.Vector3(targetPos.x, targetPos.y + 0.6, targetPos.z);
          const bottomPoint = new THREE.Vector3(targetPos.x, targetPos.y - 0.1, targetPos.z);
          
          renderer.createLaserBeam(topPoint, bottomPoint, 0x0077aa);
          renderer.showFloatingDamageText(e.x, e.z, `+${e.amount} Gold`, 'rgba(0, 119, 170, 1)');

        } else if (e.type === "artillery_shell") {
          renderer.createArtilleryShellArc(e.fromX, e.fromZ, e.toX, e.toZ);
          setTimeout(() => {
            if (e.damage > 0) {
              const isP1Target = e.targetOwner === 1;
              const textColors = isP1Target ? 'rgba(0, 119, 170, 1)' : 'rgba(204, 0, 85, 1)';
              renderer.showFloatingDamageText(e.toX, e.toZ, `-${e.damage} HP`, textColors);
            } else {
              renderer.showFloatingDamageText(e.toX, e.toZ, "Miss", 'rgba(255, 170, 0, 1)');
            }
          }, 1000);
        }
      });
    }

    // 3. Update 3D scene meshes (movement interpolation, crystals height scaling)
    renderer.syncScene();

    // 4. Update HUD text and buttons
    updateHUD();

    // 5. Game Over triggers
    if (game.gameOver) {
      clearInterval(gamePollInterval);
      gamePollInterval = null;
      
      const winnerName = game.players[game.winner]?.name || "Neutral";
      endWinnerText.innerText = `${winnerName.toUpperCase()} DOMINATES THE SECTOR`;
      endWinnerText.style.color = game.winner === 1 ? 'var(--neon-cyan)' : 'var(--neon-magenta)';
      endTitle.innerText = game.winner === playerId ? 'Victory Achieved' : 'Defeat Suffered';
      endTitle.style.color = game.winner === playerId ? 'var(--neon-cyan)' : 'var(--neon-magenta)';
      endGameModal.classList.add('show');
    }

  } catch (err) {
    console.error("Game poll error", err);
  }
}

// --- Action API Triggers ---

async function sendAction(actionName, args = {}) {
  try {
    const res = await fetch(`${apiBase}/api/action`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        roomId,
        playerId,
        action: actionName,
        args
      })
    });
    
    if (!res.ok) {
      const errData = await res.json();
      throw new Error(errData.error || "Action failed");
    }
  } catch (err) {
    console.warn("Action execution error:", err.message);
  }
}


function handleBuildAction(unitType) {
  sendAction("build", { unitType });
}

function handleAttackAction() {
  if (!game.selectedCell) return;
  isAttackMode = true;
  isMoveMode = false;
  renderer.highlightMovementTiles(game.selectedCell.x, game.selectedCell.z, false);
  renderer.highlightAttackTiles(game.selectedCell.x, game.selectedCell.z, true);
  updateHUD();
}

function handleStopFireAction() {
  if (!game.selectedCell) return;
  const cell = game.getCell(game.selectedCell.x, game.selectedCell.z);
  const selectedArtilleryIds = cell.units
    .filter(u => u.owner === playerId && u.type === 'artillery' && game.selectedUnitIds.includes(u.id))
    .map(u => u.id);

  sendAction("stop", { unitIds: selectedArtilleryIds });
  if (isAttackMode) {
    isAttackMode = false;
    renderer.highlightAttackTiles(game.selectedCell.x, game.selectedCell.z, false);
  }
  updateHUD();
}

// --- Selection & Canvas click controls ---

function onCanvasClick(e) {
  if (game.gameOver) return;

  const result = renderer.raycastTile(e.clientX, e.clientY);

  if (result) {
    const { x, z } = result;

    // --- Attack Mode Click logic ---
    if (isAttackMode) {
      const dist = getHexDistance(game.selectedCell.x, game.selectedCell.z, x, z);
      const artConfig = unitsConfig.artillery || { minRange: 1, maxRange: 2 };
      if (dist >= (artConfig.minRange ?? 1) && dist <= (artConfig.maxRange ?? 2)) {
        const cell = game.getCell(game.selectedCell.x, game.selectedCell.z);
        const selectedArtilleryIds = cell.units
          .filter(u => u.owner === playerId && u.type === 'artillery' && game.selectedUnitIds.includes(u.id))
          .map(u => u.id);

        sendAction("attack", {
          unitIds: selectedArtilleryIds,
          toX: x,
          toZ: z
        });
        isAttackMode = false;
        renderer.highlightAttackTiles(game.selectedCell.x, game.selectedCell.z, false);
        updateHUD();
        return;
      } else {
        isAttackMode = false;
        renderer.highlightAttackTiles(game.selectedCell.x, game.selectedCell.z, false);
      }
    }

    // --- Move Mode Click logic ---
    if (isMoveMode) {
      const dist = getHexDistance(game.selectedCell.x, game.selectedCell.z, x, z);

      // Check if click is on adjacent cell (dist === 1)
      if (dist === 1) {
        // Send move request
        sendAction("move", {
          unitIds: game.selectedUnitIds,
          toX: x,
          toZ: z
        });
        
        // Reset move mode green outlines
        isMoveMode = false;
        renderer.highlightMovementTiles(game.selectedCell.x, game.selectedCell.z, false);
        
        // Keep selection on target cell
        game.selectedCell = { x, z };
        renderer.updateSelection(game.selectedCell);
        updateHUD();
        return;
      } else {
        // Clicked far away: cancel move mode and select clicked tile normally
        isMoveMode = false;
        renderer.highlightMovementTiles(game.selectedCell.x, game.selectedCell.z, false);
      }
    }

    // --- Normal Selection click logic ---
    const isAlreadySelected = game.selectedCell && game.selectedCell.x === x && game.selectedCell.z === z;
    game.selectedCell = { x, z };
    if (!isAlreadySelected) {
      game.selectAllUnitsInSelected(playerId);
    }
    renderer.updateSelection(game.selectedCell);

    // Auto-activate Move Mode if owned stationary units are present
    const cell = game.getCell(x, z);
    const ownedUnits = cell.units.filter(u => u.owner === playerId && game.selectedUnitIds.includes(u.id));
    const isAnyMoving = ownedUnits.some(u => u.isMoving);

    if (ownedUnits.length > 0 && !isAnyMoving) {
      isMoveMode = true;
      renderer.highlightMovementTiles(x, z, true);
    } else {
      isMoveMode = false;
    }

    updateHUD();

  } else {
    // Clicked void - cancel modes and deselect
    if (isMoveMode) {
      isMoveMode = false;
      renderer.highlightMovementTiles(game.selectedCell.x, game.selectedCell.z, false);
    }
    if (isAttackMode) {
      isAttackMode = false;
      renderer.highlightAttackTiles(game.selectedCell.x, game.selectedCell.z, false);
    }
    game.selectedCell = null;
    game.selectedUnitIds = [];
    renderer.updateSelection(null);
    updateHUD();
  }
}

function onCanvasRightClick(e) {
  e.preventDefault();
  if (game.gameOver) return;

  if (isMoveMode || isAttackMode) {
    const result = renderer.raycastTile(e.clientX, e.clientY);
    if (result) {
      const { x, z } = result;
      const dist = getHexDistance(game.selectedCell.x, game.selectedCell.z, x, z);

      // Check if click is on adjacent cell
      if (dist === 1) {
        if (isAttackMode) {
          isAttackMode = false;
          renderer.highlightAttackTiles(game.selectedCell.x, game.selectedCell.z, false);
        }

        // Send move request
        sendAction("move", {
          unitIds: game.selectedUnitIds,
          toX: x,
          toZ: z
        });
        
        // Reset Move Mode
        isMoveMode = false;
        renderer.highlightMovementTiles(game.selectedCell.x, game.selectedCell.z, false);
        
        // Update selection to destination
        game.selectedCell = { x, z };
        renderer.updateSelection(game.selectedCell);
        updateHUD();
      }
    }
  }
}

function onCanvasMouseMove(e) {
  if (game.gameOver) return;

  const hovered = renderer.raycastTile(e.clientX, e.clientY);

  if (hovered !== lastHovered) {
    const artConfig = unitsConfig.artillery || { minRange: 1, maxRange: 2 };
    if (lastHovered) {
      const isSelected = game.selectedCell && game.selectedCell.x === lastHovered.x && game.selectedCell.z === lastHovered.z;
      const isAdjacentToSelect = game.selectedCell && getHexDistance(game.selectedCell.x, game.selectedCell.z, lastHovered.x, lastHovered.z) === 1;
      const isAttackRange = game.selectedCell && getHexDistance(game.selectedCell.x, game.selectedCell.z, lastHovered.x, lastHovered.z) >= (artConfig.minRange ?? 1) && getHexDistance(game.selectedCell.x, game.selectedCell.z, lastHovered.x, lastHovered.z) <= (artConfig.maxRange ?? 2);
      
      const isBase = game.getCell(lastHovered.x, lastHovered.z).type === 'base';

      if (!isSelected && !(isMoveMode && isAdjacentToSelect && !isBase) && !(isAttackMode && isAttackRange)) {
        renderer.resetTileOutlineColor(lastHovered.x, lastHovered.z);
      }
    }

    if (hovered) {
      const isSelected = game.selectedCell && game.selectedCell.x === hovered.x && game.selectedCell.z === hovered.z;
      const isAdjacentToSelect = game.selectedCell && getHexDistance(game.selectedCell.x, game.selectedCell.z, hovered.x, hovered.z) === 1;
      const isAttackRange = game.selectedCell && getHexDistance(game.selectedCell.x, game.selectedCell.z, hovered.x, hovered.z) >= (artConfig.minRange ?? 1) && getHexDistance(game.selectedCell.x, game.selectedCell.z, hovered.x, hovered.z) <= (artConfig.maxRange ?? 2);
      
      const isBase = game.getCell(hovered.x, hovered.z).type === 'base';

      if (!isSelected && !(isMoveMode && isAdjacentToSelect && !isBase) && !(isAttackMode && isAttackRange)) {
        renderer.setTileOutlineColor(hovered.x, hovered.z, new THREE.Color(0xffffff));
      }
    }

    lastHovered = hovered;
  }
}

// Return to lobby and reinitialize setup
function handleRestartLobby() {
  endGameModal.classList.remove('show');
  lobbyScreen.classList.remove('hidden');
  
  // Reset Waiting views
  lobbyWaitingHost.classList.add('hidden');
  lobbyWaitingGuest.classList.add('hidden');
  lobbySetup.classList.remove('hidden');

  // Clear render canvas contents
  if (renderer) {
    renderer.unitMeshes.forEach(mesh => renderer.scene.remove(mesh));
    renderer.crystalMeshes.forEach(mesh => renderer.scene.remove(mesh));
    renderer.baseMeshes.forEach(mesh => renderer.scene.remove(mesh));
    renderer.unitMeshes.clear();
    renderer.crystalMeshes.clear();
    renderer.baseMeshes.clear();
    renderer.animations = [];
  }

  // Clear timers
  if (gamePollInterval) clearInterval(gamePollInterval);
  if (lobbyPollInterval) clearInterval(lobbyPollInterval);
  gamePollInterval = null;
  lobbyPollInterval = null;

  // Clear codes
  roomId = null;
  playerId = null;
}

// --- HUD Refresh Panel ---

function updateHUD() {
  // Update role tags and player colors
  const player = game.players[playerId];
  activePlayerIndicator.className = `player-indicator p${playerId}`;
  activePlayerName.innerText = player?.name || "Commander";
  activePlayerName.style.color = playerId === 1 ? 'var(--neon-cyan)' : 'var(--neon-magenta)';
  activePlayerName.style.textShadow = `0 0 10px ${playerId === 1 ? 'rgba(0, 119, 170, 0.2)' : 'rgba(204, 0, 85, 0.2)'}`;

  roleTag.innerText = playerId === 1 ? "(Cyan Sector)" : "(Magenta Empire)";
  roleTag.style.color = playerId === 1 ? 'var(--neon-cyan)' : 'var(--neon-magenta)';

  hudRoomCode.innerText = roomId;
  resourceCount.innerText = player?.crystals || 0; // Using backend .crystals field which holds gold balance

  // Context panels visibility controls
  const selectedCell = game.selectedCell;
  if (!selectedCell) {
    selectionName.innerText = 'Select a tile';
    selectionCoord.innerText = 'Click on an octagon cell to view options';
    selectionUnitStack.innerHTML = '';

    btnGather.classList.add('hidden');
    btnAttack.classList.add('hidden');
    btnStopFire.classList.add('hidden');
    buildOptionsContainer.classList.add('hidden');
    
    if (isMoveMode) {
      isMoveMode = false;
      renderer.highlightMovementTiles(0, 0, false);
    }
    if (isAttackMode) {
      isAttackMode = false;
      renderer.highlightAttackTiles(0, 0, false);
    }
  } else {
    const cell = game.getCell(selectedCell.x, selectedCell.z);
    selectionCoord.innerText = `Coordinate: [${selectedCell.x}, ${selectedCell.z}]`;

    if (cell.type === 'base') {
      const owner = game.players[cell.owner];
      selectionName.innerText = `${owner.name}'s Command Base`;
      selectionCoord.innerText += ` • Integrity: ${owner.baseHp}/${owner.maxBaseHp} HP`;
    } else if (cell.type === 'resource') {
      selectionName.innerText = 'Gold Resource Node';
      selectionCoord.innerText += ` • Resource Volume: ${cell.gold}🪙`;
    } else {
      selectionName.innerText = 'Neutral Grid Cell';
    }

    // Badges stacking
    selectionUnitStack.innerHTML = '';
    
    if (cell.units.length === 0) {
      selectionUnitStack.innerHTML = '<span style="font-size:0.85rem; color:var(--text-muted)">No units on this tile</span>';
    } else {
      cell.units.forEach(u => {
        const owner = game.players[u.owner];
        const badge = document.createElement('div');
        badge.className = 'unit-badge';
        
        const isSelected = game.selectedUnitIds.includes(u.id);
        if (isSelected) badge.classList.add('selected');

        badge.style.color = owner.color;
        badge.style.borderColor = isSelected ? owner.color : 'rgba(0,0,0,0.08)';
        
        const typeIcon = u.type === 'mech' ? '🤖' : (u.type === 'artillery' ? '🚀' : '👷');
        const typeLabel = u.type === 'mech' ? 'Mech' : (u.type === 'artillery' ? 'Artillery' : 'Worker');
        const movingTag = u.isMoving ? " [Moving]" : "";
        const gatherTag = u.isGathering ? " [Mining]" : "";
        const targetTag = (u.type === 'artillery' && u.attackTargetX !== null && u.attackTargetX !== undefined) ? ` [Firing -> [${u.attackTargetX}, ${u.attackTargetZ}]]` : "";
        badge.innerText = `${typeIcon} ${typeLabel} (${u.hp}/${u.maxHp} HP)${movingTag}${gatherTag}${targetTag}`;
        
        // Let players select/deselect units in stack
        badge.addEventListener('click', (ev) => {
          ev.stopPropagation();
          if (u.owner === playerId) {
            game.toggleUnitSelection(u.id);
            updateHUD();
          }
        });

        selectionUnitStack.appendChild(badge);
      });
    }

    // Visibility 1: Build options show up ONLY when base is selected
    // and base owner matches player
    const isOwnBase = cell.type === 'base' && cell.owner === playerId;
    if (isOwnBase) {
      buildOptionsContainer.classList.remove('hidden');
      
      const costWorker = unitsConfig.worker?.cost ?? 50;
      const costMech = unitsConfig.mech?.cost ?? 100;
      const costArtillery = unitsConfig.artillery?.cost ?? 80;
      btnBuildWorker.disabled = (player.crystals < costWorker || player.baseHp <= 0);
      btnBuildMech.disabled = (player.crystals < costMech || player.baseHp <= 0);
      btnBuildArtillery.disabled = (player.crystals < costArtillery || player.baseHp <= 0);
    } else {
      buildOptionsContainer.classList.add('hidden');
    }

    // Visibility 2: Automatic Move Mode checks
    const ownedSelectedUnits = cell.units.filter(u => u.owner === playerId && game.selectedUnitIds.includes(u.id));
    const hasArtillerySelected = ownedSelectedUnits.some(u => u.type === 'artillery' && !u.isMoving);

    if (isAttackMode && !hasArtillerySelected) {
      isAttackMode = false;
      renderer.highlightAttackTiles(selectedCell.x, selectedCell.z, false);
    }

    if (ownedSelectedUnits.length > 0) {
      const isAnyMoving = ownedSelectedUnits.some(u => u.isMoving);
      if (isAnyMoving) {
        if (isMoveMode) {
          isMoveMode = false;
          renderer.highlightMovementTiles(selectedCell.x, selectedCell.z, false);
        }
      } else {
        if (!isMoveMode && !isAttackMode) {
          isMoveMode = true;
          renderer.highlightMovementTiles(selectedCell.x, selectedCell.z, true);
        }
      }
    } else {
      if (isMoveMode) {
        isMoveMode = false;
        renderer.highlightMovementTiles(selectedCell.x, selectedCell.z, false);
      }
    }

    // Visibility 3: Automatic gold gathering (gather button is hidden)
    btnGather.classList.add('hidden');

    // Visibility 4: Artillery Attack button options
    if (hasArtillerySelected) {
      btnAttack.classList.remove('hidden');
      const nowMs = Date.now();
      const anyCoolingDown = ownedSelectedUnits.some(u => u.type === 'artillery' && (nowMs - u.lastAttackTime < 3000));
      btnAttack.disabled = anyCoolingDown;
    } else {
      btnAttack.classList.add('hidden');
    }

    const hasFiringArtillery = ownedSelectedUnits.some(u => u.type === 'artillery' && u.attackTargetX !== null && u.attackTargetX !== undefined);
    if (hasFiringArtillery) {
      btnStopFire.classList.remove('hidden');
    } else {
      btnStopFire.classList.add('hidden');
    }
  }
}

// --- Camera setup overlay buttons ---

function setupCameraButtons() {
  const rotateCamera = (angle) => {
    if (!renderer) return;
    const target = renderer.controls.target;
    const pos = renderer.camera.position.clone().sub(target);
    pos.applyAxisAngle(new THREE.Vector3(0, 1, 0), angle);
    renderer.camera.position.copy(pos.add(target));
    renderer.controls.update();
  };

  const tiltCamera = (angle) => {
    if (!renderer) return;
    const target = renderer.controls.target;
    const pos = renderer.camera.position.clone().sub(target);
    const right = new THREE.Vector3().crossVectors(pos, new THREE.Vector3(0, 1, 0)).normalize();
    pos.applyAxisAngle(right, angle);

    const testY = pos.y + target.y;
    if (testY > 1.0 && testY < 30.0) {
      renderer.camera.position.copy(pos.add(target));
      renderer.controls.update();
    }
  };

  const zoomCamera = (factor) => {
    if (!renderer) return;
    const target = renderer.controls.target;
    const pos = renderer.camera.position.clone().sub(target);
    pos.multiplyScalar(factor);

    const newDist = pos.length();
    if (newDist > 4.5 && newDist < 45.0) {
      renderer.camera.position.copy(pos.add(target));
      renderer.controls.update();
    }
  };

  document.getElementById('cam-rot-ccw').addEventListener('click', () => rotateCamera(-Math.PI / 12));
  document.getElementById('cam-rot-cw').addEventListener('click', () => rotateCamera(Math.PI / 12));
  document.getElementById('cam-tilt-up').addEventListener('click', () => tiltCamera(0.12));
  document.getElementById('cam-tilt-down').addEventListener('click', () => tiltCamera(-0.12));
  document.getElementById('cam-zoom-in').addEventListener('click', () => zoomCamera(0.85));
  document.getElementById('cam-zoom-out').addEventListener('click', () => zoomCamera(1.15));
  document.getElementById('cam-reset').addEventListener('click', () => {
    if (!renderer) return;
    renderer.camera.position.set(0, 16, 18);
    renderer.controls.target.set(0, 0, 0);
    renderer.controls.update();
  });
}

// Initialize on DOM ready
window.addEventListener('DOMContentLoaded', () => {
  init();
  setupCameraButtons();
});
