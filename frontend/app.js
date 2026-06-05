// app.js
// Client Controller: coordinates lobby, real-time networking, logic, and 3D rendering (Bright Grass Theme)

import { GameState, getHexDistance, playerLabel } from './game.js?v=multiplayer-1';
import { GameRenderer } from './renderer.js?v=multiplayer-1';
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
let techTreeConfig = {};

function updateUILabels() {
  const attackSpan = btnAttack.querySelector('.cost');
  if (attackSpan && unitsConfig.artillery) {
    attackSpan.innerText = `Range ${unitsConfig.artillery.minRange}-${unitsConfig.artillery.maxRange}`;
  }
}

function labelFromKey(key) {
  return key
    .replace(/^upgrade_/, '')
    .split('_')
    .map(part => part.charAt(0).toUpperCase() + part.slice(1))
    .join(' ');
}

function techUpgradeCost(upgrade, level) {
  return (upgrade.initialCost ?? 0) + (level * (upgrade.costIncrease ?? 0));
}

function techUpgradeEffectLabel(upgrade) {
  if (upgrade.type === 'PassiveIncome') {
    return `+${upgrade.valueIncrease ?? 0} gold/s`;
  }
  return `+${upgrade.valueIncrease} ${upgrade.targetProperty}`;
}

function createActionHeader(text) {
  const header = document.createElement('div');
  header.style.width = '100%';
  header.style.fontFamily = 'var(--font-title)';
  header.style.fontSize = '0.8rem';
  header.style.color = 'var(--text-muted)';
  header.style.textTransform = 'uppercase';
  header.innerText = text;
  return header;
}

function renderBaseActionButtons(player) {
  buildOptionsContainer.innerHTML = '';
  if (!baseActionMode) {
    baseActionMode = 'units';
  }

  const unitsButton = document.createElement('button');
  unitsButton.className = `btn base-action-tab ${baseActionMode === 'units' ? 'active' : ''}`;
  unitsButton.innerText = 'Units';
  unitsButton.addEventListener('click', () => {
    baseActionMode = 'units';
    updateHUD();
  });
  buildOptionsContainer.appendChild(unitsButton);

  const techButton = document.createElement('button');
  techButton.className = `btn base-action-tab ${baseActionMode === 'tech' ? 'active' : ''}`;
  techButton.innerText = 'Tech Tree';
  techButton.addEventListener('click', () => {
    baseActionMode = 'tech';
    updateHUD();
  });
  buildOptionsContainer.appendChild(techButton);

  if (baseActionMode === 'units') {
    renderUnitBuildButtons(player);
  } else if (baseActionMode === 'tech') {
    renderTechUpgradeButtons(player);
  }
}

function renderUnitBuildButtons(player) {
  buildOptionsContainer.appendChild(createActionHeader('Build Units'));
  for (const unitType of ['worker', 'mech', 'artillery']) {
    const unitConfig = unitsConfig[unitType] || {};
    const cost = unitConfig.cost ?? 50;
    const button = document.createElement('button');
    button.className = 'btn btn-magenta';
    button.disabled = !player || player.crystals < cost || player.baseHp <= 0;
    button.innerText = `Build ${unitConfig.name || labelFromKey(unitType)}`;

    const costSpan = document.createElement('span');
    costSpan.className = 'cost';
    costSpan.innerText = `🪙 ${cost}`;
    button.appendChild(costSpan);

    button.addEventListener('click', () => handleBuildAction(unitType));
    buildOptionsContainer.appendChild(button);
  }
}

function renderTechUpgradeButtons(player) {
  buildOptionsContainer.appendChild(createActionHeader('Tech Upgrades'));
  for (const [upgradeName, upgrade] of Object.entries(techTreeConfig)) {
    const level = player?.techUpgrades?.[upgradeName] ?? 0;
    const cost = techUpgradeCost(upgrade, level);
    const button = document.createElement('button');
    button.className = 'btn btn-magenta';
    button.disabled = !player || player.crystals < cost || player.baseHp <= 0;
    button.innerText = labelFromKey(upgradeName);

    const costSpan = document.createElement('span');
    costSpan.className = 'cost';
    costSpan.innerText = `Level ${level} · ${techUpgradeEffectLabel(upgrade)} · 🪙 ${cost}`;
    button.appendChild(costSpan);

    button.addEventListener('click', () => handleUpgradeAction(upgradeName));
    buildOptionsContainer.appendChild(button);
  }
}


// Network variables
let roomId = null;
let playerId = null;
let playerName = "Commander";
let apiBase = window.location.origin; // Dynamically updated on join
let connectedBot = null;
let botSessionActive = false;
let hostPlayerCount = 2;

// Polling intervals
let lobbyPollInterval = null;
let gamePollInterval = null;

// Game states
let isMoveMode = false;
let isAttackMode = false;
let baseActionMode = null;
let currentMapSettings = null;

// DOM Elements - Lobby Screen
const lobbyScreen = document.getElementById('lobby-screen');
const lobbySetup = document.getElementById('lobby-setup');
const lobbyWaitingHost = document.getElementById('lobby-waiting-host');
const lobbyWaitingGuest = document.getElementById('lobby-waiting-guest');

// Inputs
const inputPlayerName = document.getElementById('player-name');
const inputServerIp = document.getElementById('server-ip');
const inputRoomCode = document.getElementById('room-code');
const inputBotUrl = document.getElementById('bot-url');
const mapModeSelect = document.getElementById('map-mode-select');

// Buttons
const btnHostLobby = document.getElementById('btn-host-lobby');
const btnJoinLobby = document.getElementById('btn-join-lobby');
const btnStartGame = document.getElementById('btn-start-game');
const btnMapSettings = document.getElementById('btn-map-settings');
const btnConnectBot = document.getElementById('btn-connect-bot');
const btnDisconnectBot = document.getElementById('btn-disconnect-bot');
const botStatus = document.getElementById('bot-status');

// Lobby Text Displays
const hostRoomCode = document.getElementById('host-room-code');
const hostServerIp = document.getElementById('host-server-ip');
const hostPlayersList = document.getElementById('host-players-list');
const guestRoomCode = document.getElementById('guest-room-code');
const guestRoleLine = document.getElementById('guest-role-line');
const guestPlayersList = document.getElementById('guest-players-list');
const guestMapMode = document.getElementById('guest-map-mode');

// HUD Displays
const ownPlayerPanel = document.getElementById('own-player-panel');
const ownPlayerIndicator = document.getElementById('own-player-indicator');
const ownPlayerName = document.getElementById('own-player-name');
const ownRoleTag = document.getElementById('own-role-tag');
const ownResourceCount = document.getElementById('own-resource-count');
const ownUnitCount = document.getElementById('own-unit-count');
const ownBaseHp = document.getElementById('own-base-hp');
const opponentPlayerPanel = document.getElementById('opponent-player-panel');
const opponentPlayerIndicator = document.getElementById('opponent-player-indicator');
const opponentPlayerName = document.getElementById('opponent-player-name');
const opponentRoleTag = document.getElementById('opponent-role-tag');
const opponentResourceCount = document.getElementById('opponent-resource-count');
const opponentUnitCount = document.getElementById('opponent-unit-count');
const opponentBaseHp = document.getElementById('opponent-base-hp');
const hudRoomCode = document.getElementById('hud-room-code');
const selectionName = document.getElementById('selection-name');
const selectionCoord = document.getElementById('selection-coord');
const selectionUnitStack = document.getElementById('selection-unit-stack');

// Context Action Buttons
const btnGather = document.getElementById('action-gather');
const btnAttack = document.getElementById('action-attack');
const btnStopFire = document.getElementById('action-stop');
const buildOptionsContainer = document.getElementById('build-options-container');

// Modals
const instructionsModal = document.getElementById('instructions-modal');
const mapSettingsModal = document.getElementById('map-settings-modal');
const mapSettingsList = document.getElementById('map-settings-list');
const closeMapSettingsBtn = document.getElementById('close-map-settings');
const techTreeModal = document.getElementById('tech-tree-modal');
const techTreeSummary = document.getElementById('tech-tree-summary');
const closeTechTreeBtn = document.getElementById('close-tech-tree');
const closeInstructionsBtn = document.getElementById('close-instructions');
const toggleRulesBtn = document.getElementById('instructions-btn');
const endGameModal = document.getElementById('end-game-modal');
const endTitle = document.getElementById('end-title');
const endWinnerText = document.getElementById('end-winner-text');
const btnRestart = document.getElementById('action-restart');
const hostPlayerCountModal = document.getElementById('host-player-count-modal');
const hostPlayerCountValue = document.getElementById('host-player-count-value');
const hostPlayerCountMinus = document.getElementById('host-player-count-minus');
const hostPlayerCountPlus = document.getElementById('host-player-count-plus');
const cancelHostPlayerCount = document.getElementById('cancel-host-player-count');
const confirmHostPlayerCount = document.getElementById('confirm-host-player-count');

// --- Initialization ---

function init() {
  // Bind lobby buttons
  btnHostLobby.addEventListener('click', showHostPlayerCountModal);
  btnJoinLobby.addEventListener('click', handleJoinLobby);
  btnStartGame.addEventListener('click', handleStartGame);
  btnConnectBot.addEventListener('click', handleConnectBot);
  btnDisconnectBot.addEventListener('click', handleDisconnectBot);
  mapModeSelect.addEventListener('change', handleMapModeChange);
  document.addEventListener('click', (ev) => {
    if (ev.target.closest('#btn-map-settings')) {
      showMapSettingsModal();
      return;
    }

    const stepButton = ev.target.closest('.map-step-button');
    if (stepButton) {
      const key = stepButton.dataset.mapSetting;
      const delta = Number(stepButton.dataset.delta);
      const setting = currentMapSettings?.[key];
      if (!setting) return;
      const nextTarget = Math.max(setting.min, Math.min(setting.max, Number(setting.target) + delta));
      updateMapSetting(key, nextTarget);
    }
  });
  mapSettingsList.addEventListener('change', (ev) => {
    const select = ev.target.closest('.map-setting-select');
    if (!select) return;

    const key = select.dataset.mapSetting;
    const setting = currentMapSettings?.[key];
    if (!setting) return;
    const option = setting.options.find(candidate => String(candidate) === select.value);
    updateMapSetting(key, option);
  });
  closeMapSettingsBtn.addEventListener('click', () => mapSettingsModal.classList.add('hidden'));
  mapSettingsModal.addEventListener('click', (ev) => {
    if (ev.target === mapSettingsModal) {
      mapSettingsModal.classList.add('hidden');
    }
  });
  document.addEventListener('click', (ev) => {
    if (ev.target.closest('#tech-tree-summary-btn')) {
      showTechTreeModal();
    }
  });
  if (closeTechTreeBtn && techTreeModal) {
    closeTechTreeBtn.addEventListener('click', () => techTreeModal.classList.add('hidden'));
    techTreeModal.addEventListener('click', (ev) => {
      if (ev.target === techTreeModal) {
        techTreeModal.classList.add('hidden');
      }
    });
  } else {
    console.warn("Tech tree modal elements were not found.");
  }

  // Bind instructions modal
  closeInstructionsBtn.addEventListener('click', () => instructionsModal.classList.add('hidden'));
  if (toggleRulesBtn) {
    toggleRulesBtn.addEventListener('click', () => instructionsModal.classList.remove('hidden'));
  }

  // Bind HUD contextual actions
  btnAttack.addEventListener('click', handleAttackAction);
  btnStopFire.addEventListener('click', handleStopFireAction);

  btnRestart.addEventListener('click', handleRestartLobby);
  hostPlayerCountMinus.addEventListener('click', () => setHostPlayerCount(hostPlayerCount - 1));
  hostPlayerCountPlus.addEventListener('click', () => setHostPlayerCount(hostPlayerCount + 1));
  cancelHostPlayerCount.addEventListener('click', () => hostPlayerCountModal.classList.add('hidden'));
  confirmHostPlayerCount.addEventListener('click', handleHostLobby);

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

  fetch('/tech_tree.json')
    .then(res => res.json())
    .then(data => {
      techTreeConfig = data;
      if (game) updateHUD();
    })
    .catch(err => {
      console.warn("Failed to load tech_tree.json:", err);
    });
}

// --- Local Bot Handshake ---

function setBotStatus(message, state = '') {
  botStatus.innerText = message;
  botStatus.classList.toggle('connected', state === 'connected');
  botStatus.classList.toggle('error', state === 'error');
}

function normalizeBotUrl(url) {
  const trimmed = url.trim();
  if (!trimmed) return 'http://127.0.0.1:8787';
  if (trimmed.startsWith('http://') || trimmed.startsWith('https://')) return trimmed;
  return `http://${trimmed}`;
}

function setHostPlayerCount(value) {
  hostPlayerCount = Math.max(2, Math.min(4, Number(value)));
  hostPlayerCountValue.innerText = String(hostPlayerCount);
  hostPlayerCountMinus.disabled = hostPlayerCount <= 2;
  hostPlayerCountPlus.disabled = hostPlayerCount >= 4;
}

function showHostPlayerCountModal() {
  setHostPlayerCount(hostPlayerCount);
  hostPlayerCountModal.classList.remove('hidden');
}

function playerColor(playerId) {
  return game?.players?.[playerId]?.color || {
    1: '#0077aa',
    2: '#cc0055',
    3: '#16a34a',
    4: '#eab308'
  }[playerId] || '#64748b';
}

function renderLobbyPlayers(container, players) {
  container.innerHTML = '';
  Object.entries(players).forEach(([playerIdText, player]) => {
    const playerIdNumber = Number(playerIdText);
    const row = document.createElement('div');
    row.className = `player-slot ${player.name ? 'occupied' : ''}`;
    row.style.borderColor = playerColor(playerIdNumber);
    row.innerHTML = `
      <span>${playerLabel(playerIdNumber)}${playerIdNumber === 1 ? ' (Host)' : ''}:</span>
      <span>${player.name || 'Waiting for player...'}</span>
    `;
    container.appendChild(row);
  });
}

async function postBot(path, payload) {
  if (!connectedBot && path !== '/handshake') {
    throw new Error('No local bot connected');
  }

  const baseUrl = path === '/handshake' ? normalizeBotUrl(inputBotUrl.value) : connectedBot.url;
  const res = await fetch(`${baseUrl}${path}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload)
  });

  if (!res.ok) {
    let errData = {};
    try {
      errData = await res.json();
    } catch (_) {
      // Ignore non-JSON local bot errors.
    }
    throw new Error(errData.error || `Bot request failed: ${res.status}`);
  }

  return res.json();
}

async function handleConnectBot() {
  try {
    const botUrl = normalizeBotUrl(inputBotUrl.value);
    inputBotUrl.value = botUrl;
    setBotStatus('Connecting to local bot...');

    const data = await postBot('/handshake', {
      protocol: 'octagon-rts-bot-v1',
      game: 'Octagon-RTS',
      pageOrigin: window.location.origin
    });

    connectedBot = {
      url: botUrl,
      name: data.name || 'Local Bot'
    };
    botSessionActive = false;
    setBotStatus(`Connected: ${connectedBot.name}`, 'connected');
    btnConnectBot.classList.add('hidden');
    btnDisconnectBot.classList.remove('hidden');
    inputBotUrl.disabled = true;
  } catch (err) {
    connectedBot = null;
    botSessionActive = false;
    setBotStatus(err.message, 'error');
  }
}

async function handleDisconnectBot() {
  if (connectedBot) {
    try {
      await postBot('/stop', {
        protocol: 'octagon-rts-bot-v1',
        roomId,
        playerId
      });
    } catch (_) {
      // The bot may already be stopped or offline.
    }
  }

  connectedBot = null;
  botSessionActive = false;
  setBotStatus('No bot connected');
  btnConnectBot.classList.remove('hidden');
  btnDisconnectBot.classList.add('hidden');
  inputBotUrl.disabled = false;
}

async function startConnectedBotSession() {
  if (!connectedBot) return;

  const data = await postBot('/session', {
    protocol: 'octagon-rts-bot-v1',
    gameServer: apiBase,
    roomId,
    playerId,
    playerName,
    pollMs: 200
  });

  botSessionActive = true;
  connectedBot.name = data.name || connectedBot.name;
  setBotStatus(`Bot playing as ${playerName}: ${connectedBot.name}`, 'connected');
}

// --- Lobby HTTP client actions ---

async function handleHostLobby() {
  playerName = inputPlayerName.value.trim() || "Commander";
  apiBase = window.location.origin;
  hostPlayerCountModal.classList.add('hidden');

  try {
    const res = await fetch(`${apiBase}/api/host`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ playerName, playerCount: hostPlayerCount })
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
    const serverPort = window.location.port || (window.location.protocol === 'https:' ? '443' : '80');
    hostServerIp.innerText = `${ipData.ip}:${serverPort}`;
    await startConnectedBotSession();
    
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
    playerId = data.playerId;

    // Setup Guest UI state
    guestRoomCode.innerText = roomId;
    guestRoleLine.innerText = `Role: ${playerLabel(playerId)} (P${playerId})`;
    guestRoleLine.style.color = playerColor(playerId);
    await startConnectedBotSession();
    
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

function mapModeLabel(mapMode) {
  return mapMode === 'random' ? 'CustomMap' : 'StandardMap';
}

async function handleMapModeChange() {
  if (!roomId || playerId !== 1) return;
  updateMapSettingsButton();

  try {
    const res = await fetch(`${apiBase}/api/map`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        roomId,
        playerId,
        mapMode: mapModeSelect.value
      })
    });

    if (!res.ok) {
      const errData = await res.json();
      throw new Error(errData.error || "Failed to update map");
    }
  } catch (err) {
    alert(err.message);
  }
}

function updateMapSettingsButton() {
  if (playerId === 1 && mapModeSelect.value === 'random') {
    btnMapSettings.classList.remove('hidden');
  } else {
    btnMapSettings.classList.add('hidden');
  }
}

function formatMapSettingLabel(key) {
  const labels = {
    width: 'Width',
    height: 'Height',
    numResources: 'Resources',
    numObsticale: 'Obstacles',
    randomPlayer: 'Random Players',
    fogOfWar: 'Fog Of War'
  };
  return labels[key] || key;
}

function formatMapSettingValue(value) {
  if (typeof value === 'boolean') {
    return value ? 'Yes' : 'No';
  }
  return String(value);
}

function numericMapSettingControl(key, setting) {
  const target = Number(setting.target);
  const min = Number(setting.min);
  const max = Number(setting.max);
  const decrementDisabled = target <= min ? 'disabled' : '';
  const incrementDisabled = target >= max ? 'disabled' : '';

  return `
    <div class="map-setting-stepper">
      <button class="map-step-button" type="button" data-map-setting="${key}" data-delta="-1" ${decrementDisabled}>‹</button>
      <span class="map-setting-value">${formatMapSettingValue(setting.target)}</span>
      <button class="map-step-button" type="button" data-map-setting="${key}" data-delta="1" ${incrementDisabled}>›</button>
    </div>
  `;
}

function optionMapSettingControl(key, setting) {
  const options = setting.options || [];
  const optionHtml = options.map(option => {
    const selected = option === setting.target ? 'selected' : '';
    return `<option value="${String(option)}" ${selected}>${formatMapSettingValue(option)}</option>`;
  }).join('');

  return `<select class="map-setting-select" data-map-setting="${key}">${optionHtml}</select>`;
}

function renderMapSettings(settings) {
  currentMapSettings = settings;
  mapSettingsList.innerHTML = `
    <div class="map-setting-row header">
      <span>Setting</span>
      <span>Value</span>
    </div>
  `;

  Object.entries(settings).forEach(([key, value]) => {
    const row = document.createElement('div');
    row.className = 'map-setting-row';
    const controlHtml = value.options
      ? optionMapSettingControl(key, value)
      : numericMapSettingControl(key, value);
    row.innerHTML = `
      <span>${formatMapSettingLabel(key)}</span>
      ${controlHtml}
    `;
    mapSettingsList.appendChild(row);
  });
}

async function updateMapSetting(key, target) {
  if (!currentMapSettings || !currentMapSettings[key]) return;

  const nextSettings = {
    ...currentMapSettings,
    [key]: {
      ...currentMapSettings[key],
      target
    }
  };

  renderMapSettings(nextSettings);

  try {
    const res = await fetch(`${apiBase}/api/map-settings`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        roomId,
        playerId,
        settings: nextSettings
      })
    });

    const data = await res.json();
    if (!res.ok) {
      throw new Error(data.error || "Failed to update map settings");
    }
    renderMapSettings(data.settings);
  } catch (err) {
    mapSettingsList.innerHTML = `<div class="map-setting-value">${err.message}</div>`;
  }
}

async function showMapSettingsModal() {
  mapSettingsList.innerHTML = '<div class="map-setting-value">Loading settings...</div>';
  mapSettingsModal.classList.remove('hidden');

  try {
    const res = await fetch(`${apiBase}/map.json`);
    if (!res.ok) throw new Error("Failed to load map settings");
    const settings = await res.json();
    renderMapSettings(settings);
  } catch (err) {
    mapSettingsList.innerHTML = `<div class="map-setting-value">${err.message}</div>`;
  }
}

window.showMapSettingsModal = showMapSettingsModal;

function renderTechTreeModal() {
  if (!game) {
    techTreeSummary.innerHTML = '<div class="tech-empty-state">No active match.</div>';
    return;
  }

  const upgrades = Object.entries(techTreeConfig);
  const playerEntries = (game.activePlayerIds || Object.keys(game.players).map(id => Number(id)))
    .sort((a, b) => a - b)
    .map(id => [String(id), game.players[id]])
    .filter(([, player]) => player);

  techTreeSummary.innerHTML = '';
  if (playerEntries.length === 0) {
    techTreeSummary.innerHTML = '<div class="tech-empty-state">No players loaded.</div>';
    return;
  }

  playerEntries.forEach(([playerIdText, player]) => {
    const playerIdNumber = Number(playerIdText);
    const color = player.color || playerColor(playerIdNumber);
    const card = document.createElement('section');
    card.className = 'tech-player-card';
    card.style.borderColor = color;

    const header = document.createElement('div');
    header.className = 'tech-player-header';
    header.style.color = color;
    const nameSpan = document.createElement('span');
    nameSpan.textContent = player.name || playerLabel(playerIdNumber);
    const ticksSpan = document.createElement('span');
    ticksSpan.textContent = `Ticks ${player.ticks ?? 0}`;
    header.append(nameSpan, ticksSpan);
    card.appendChild(header);

    const list = document.createElement('div');
    list.className = 'tech-upgrade-list';

    if (upgrades.length === 0) {
      list.innerHTML = '<div class="tech-empty-state">Tech tree not loaded.</div>';
    } else {
      upgrades.forEach(([upgradeName, upgrade]) => {
        const level = player.techUpgrades?.[upgradeName] ?? 0;
        const nextCost = techUpgradeCost(upgrade, level);
        const row = document.createElement('div');
        row.className = 'tech-upgrade-row';
        const labelBlock = document.createElement('div');
        const name = document.createElement('span');
        name.className = 'tech-upgrade-name';
        name.textContent = labelFromKey(upgradeName);
        const effect = document.createElement('span');
        effect.className = 'tech-upgrade-effect';
        effect.textContent = techUpgradeEffectLabel(upgrade);
        labelBlock.append(name, effect);

        const meta = document.createElement('div');
        meta.className = 'tech-upgrade-meta';
        const levelSpan = document.createElement('span');
        levelSpan.textContent = `Lvl ${level}`;
        const nextCostSpan = document.createElement('span');
        nextCostSpan.textContent = `Next ${nextCost}`;
        meta.append(levelSpan, nextCostSpan);

        row.append(labelBlock, meta);
        list.appendChild(row);
      });
    }

    card.appendChild(list);
    techTreeSummary.appendChild(card);
  });
}

function showTechTreeModal() {
  renderTechTreeModal();
  techTreeModal.classList.remove('hidden');
}

// Polling while waiting inside the room lobby
async function pollLobbyState() {
  try {
    const res = await fetch(`${apiBase}/api/state?roomId=${roomId}&playerId=${playerId}`);
    if (!res.ok) return;
    const data = await res.json();
    const currentMapMode = data.mapMode || 'standard';
    mapModeSelect.value = currentMapMode;
    guestMapMode.innerText = mapModeLabel(currentMapMode);
    updateMapSettingsButton();
    renderLobbyPlayers(hostPlayersList, data.players);
    renderLobbyPlayers(guestPlayersList, data.players);

    if (playerId === 1) {
      const allPlayersJoined = Object.values(data.players).every(player => player.name);
      btnStartGame.disabled = !allPlayersJoined;
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
          const workerPos = renderer.gridToWorld(e.workerX, e.workerZ);
          const topPoint = new THREE.Vector3(workerPos.x, workerPos.y + 0.35, workerPos.z);
          const bottomPoint = new THREE.Vector3(targetPos.x, targetPos.y + 0.35, targetPos.z);
          
          renderer.createLaserBeam(topPoint, bottomPoint, 0x0077aa);
          renderer.showFloatingDamageText(e.x, e.z, `+${e.amount} Gold`, 'rgba(0, 119, 170, 1)');

        } else if (e.type === "artillery_shell") {
          renderer.createArtilleryShellArc(e.fromX, e.fromZ, e.toX, e.toZ, e.flightTime);
        } else if (e.type === "artillery_impact") {
          if (e.damage > 0) {
            const isP1Target = e.targetOwner === 1;
            const textColors = isP1Target ? 'rgba(0, 119, 170, 1)' : 'rgba(204, 0, 85, 1)';
            renderer.showFloatingDamageText(e.toX, e.toZ, `-${e.damage} HP`, textColors);
          } else {
            renderer.showFloatingDamageText(e.toX, e.toZ, "Miss", 'rgba(255, 170, 0, 1)');
          }
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
      endWinnerText.style.color = game.players[game.winner]?.color || playerColor(game.winner);
      endTitle.innerText = game.winner === playerId ? 'Victory Achieved' : 'Defeat Suffered';
      endTitle.style.color = game.winner === playerId ? playerColor(playerId) : (game.players[game.winner]?.color || playerColor(game.winner));
      endGameModal.classList.add('show');
    }

  } catch (err) {
    console.error("Game poll error", err);
  }
}

// --- Action API Triggers ---

async function sendAction(actionName, args = {}) {
  if (botSessionActive) {
    console.warn('Manual actions are disabled while a local bot controls this player.');
    return;
  }

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


function handleUpgradeAction(upgradeName) {
  if (botSessionActive) return;
  sendAction("upgrade", { upgradeName });
}

function handleBuildAction(unitType) {
  if (botSessionActive) return;
  sendAction("build", { unitType });
}

function handleAttackAction() {
  if (botSessionActive) return;
  if (!game.selectedCell) return;
  isAttackMode = true;
  isMoveMode = false;
  renderer.highlightMovementTiles(game.selectedCell.x, game.selectedCell.z, false, getSelectedOwnedUnits());
  renderer.highlightAttackTiles(game.selectedCell.x, game.selectedCell.z, true);
  updateHUD();
}

function handleStopFireAction() {
  if (botSessionActive) return;
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

function getSelectedOwnedUnits() {
  if (!game.selectedCell) return [];
  const cell = game.getCell(game.selectedCell.x, game.selectedCell.z);
  return cell.units.filter(u => u.owner === playerId && game.selectedUnitIds.includes(u.id));
}

function canSelectedUnitsEnterCell(x, z) {
  const cell = game.getCell(x, z);
  if (!cell || cell.type === 'base' || cell.type === 'obstacle' || cell.type === 'resource') return false;
  return true;
}

function onCanvasClick(e) {
  if (game.gameOver) return;

  const result = renderer.raycastTile(e.clientX, e.clientY);

  if (result) {
    const { x, z } = result;
    const manualActionsEnabled = !botSessionActive;

    // --- Attack Mode Click logic ---
    if (manualActionsEnabled && isAttackMode) {
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
    if (manualActionsEnabled && isMoveMode) {
      const dist = getHexDistance(game.selectedCell.x, game.selectedCell.z, x, z);

      // Check if click is on adjacent cell (dist === 1)
      if (dist === 1 && canSelectedUnitsEnterCell(x, z)) {
        // Send move request
        sendAction("move", {
          unitIds: game.selectedUnitIds,
          toX: x,
          toZ: z
        });
        
        // Reset move mode green outlines
        isMoveMode = false;
        renderer.highlightMovementTiles(game.selectedCell.x, game.selectedCell.z, false, getSelectedOwnedUnits());
        
        // Keep selection on target cell
        game.selectedCell = { x, z };
        renderer.updateSelection(game.selectedCell);
        updateHUD();
        return;
      } else {
        // Clicked far away: cancel move mode and select clicked tile normally
        isMoveMode = false;
        renderer.highlightMovementTiles(game.selectedCell.x, game.selectedCell.z, false, getSelectedOwnedUnits());
      }
    }

    // --- Normal Selection click logic ---
    const isAlreadySelected = game.selectedCell && game.selectedCell.x === x && game.selectedCell.z === z;
    if (!isAlreadySelected) {
      baseActionMode = null;
    }
    game.selectedCell = { x, z };
    if (!isAlreadySelected) {
      game.selectAllUnitsInSelected(playerId);
    }
    renderer.updateSelection(game.selectedCell);

    // Auto-activate Move Mode if owned stationary units are present
    const cell = game.getCell(x, z);
    const ownedUnits = cell.units.filter(u => u.owner === playerId && game.selectedUnitIds.includes(u.id));
    const isAnyMoving = ownedUnits.some(u => u.isMoving);

    if (manualActionsEnabled && ownedUnits.length > 0 && !isAnyMoving) {
      isMoveMode = true;
      renderer.highlightMovementTiles(x, z, true, ownedUnits);
    } else {
      isMoveMode = false;
    }

    updateHUD();

  } else {
    // Clicked void - cancel modes and deselect
    if (isMoveMode) {
      isMoveMode = false;
      renderer.highlightMovementTiles(game.selectedCell.x, game.selectedCell.z, false, getSelectedOwnedUnits());
    }
    if (isAttackMode) {
      isAttackMode = false;
      renderer.highlightAttackTiles(game.selectedCell.x, game.selectedCell.z, false);
    }
    game.selectedCell = null;
    game.selectedUnitIds = [];
    baseActionMode = null;
    renderer.updateSelection(null);
    updateHUD();
  }
}

function onCanvasRightClick(e) {
  e.preventDefault();
  if (game.gameOver) return;
  if (botSessionActive) return;

  if (isMoveMode || isAttackMode) {
    const result = renderer.raycastTile(e.clientX, e.clientY);
    if (result) {
      const { x, z } = result;
      const dist = getHexDistance(game.selectedCell.x, game.selectedCell.z, x, z);

      // Check if click is on adjacent cell
      if (dist === 1 && canSelectedUnitsEnterCell(x, z)) {
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
        renderer.highlightMovementTiles(game.selectedCell.x, game.selectedCell.z, false, getSelectedOwnedUnits());
        
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
      
      const lastCell = game.getCell(lastHovered.x, lastHovered.z);
      const isBlocked = !canSelectedUnitsEnterCell(lastHovered.x, lastHovered.z);

      if (!isSelected && !(isMoveMode && isAdjacentToSelect && !isBlocked) && !(isAttackMode && isAttackRange)) {
        renderer.resetTileOutlineColor(lastHovered.x, lastHovered.z);
      }
    }

    if (hovered) {
      const isSelected = game.selectedCell && game.selectedCell.x === hovered.x && game.selectedCell.z === hovered.z;
      const isAdjacentToSelect = game.selectedCell && getHexDistance(game.selectedCell.x, game.selectedCell.z, hovered.x, hovered.z) === 1;
      const isAttackRange = game.selectedCell && getHexDistance(game.selectedCell.x, game.selectedCell.z, hovered.x, hovered.z) >= (artConfig.minRange ?? 1) && getHexDistance(game.selectedCell.x, game.selectedCell.z, hovered.x, hovered.z) <= (artConfig.maxRange ?? 2);
      
      const hoveredCell = game.getCell(hovered.x, hovered.z);
      const isBlocked = !canSelectedUnitsEnterCell(hovered.x, hovered.z);

      if (!isSelected && !(isMoveMode && isAdjacentToSelect && !isBlocked) && !(isAttackMode && isAttackRange)) {
        renderer.setTileOutlineColor(hovered.x, hovered.z, new THREE.Color(0xffffff));
      }
    }

    lastHovered = hovered;
  }
}

// Return to lobby and reinitialize setup
function handleRestartLobby() {
  handleDisconnectBot();
  endGameModal.classList.remove('show');
  lobbyScreen.classList.remove('hidden');
  
  // Reset Waiting views
  lobbyWaitingHost.classList.add('hidden');
  lobbyWaitingGuest.classList.add('hidden');
  lobbySetup.classList.remove('hidden');

  // Clear render canvas contents
  if (renderer) {
    const canvasElement = document.getElementById('game-canvas');
    canvasElement.removeEventListener('click', onCanvasClick);
    canvasElement.removeEventListener('mousemove', onCanvasMouseMove);
    canvasElement.removeEventListener('contextmenu', onCanvasRightClick);
    renderer.dispose();
    renderer = null;
  }

  // Clear timers
  if (gamePollInterval) clearInterval(gamePollInterval);
  if (lobbyPollInterval) clearInterval(lobbyPollInterval);
  gamePollInterval = null;
  lobbyPollInterval = null;

  // Clear codes
  roomId = null;
  playerId = null;
  game = null;
  baseActionMode = null;
  isMoveMode = false;
  isAttackMode = false;
}

// --- HUD Refresh Panel ---

function updateTopPlayerPanel(elements, panelPlayerId, label) {
  const player = game.players[panelPlayerId];
  let unitCount = 0;
  for (let x = 0; x < game.gridWidth; x++) {
    for (let z = 0; z < game.gridHeight; z++) {
      unitCount += game.grid[x][z].units.filter(unit => unit.owner === panelPlayerId).length;
    }
  }
  const color = player?.color || playerColor(panelPlayerId);
  const shadow = color;

  elements.panel.className = `top-player-panel p${panelPlayerId}`;
  elements.indicator.className = `player-indicator p${panelPlayerId}`;
  elements.indicator.style.background = color;
  elements.name.innerText = player?.name || playerLabel(panelPlayerId);
  elements.name.style.color = color;
  elements.name.style.textShadow = `0 0 10px ${shadow}`;
  elements.role.innerText = label;
  elements.role.style.color = color;
  elements.resources.innerText = player?.crystals ?? 0;
  elements.units.innerText = unitCount;
  elements.baseHp.innerText = player ? `${player.baseHp}/${player.maxBaseHp}` : '0/0';
}

function updateHUD() {
  // Update role tags and player colors
  const opponentId = Number(Object.keys(game.players).find(id => Number(id) !== playerId)) || (playerId === 1 ? 2 : 1);
  const ownLabel = botSessionActive ? '(You • Bot)' : '(You)';
  updateTopPlayerPanel({
    panel: ownPlayerPanel,
    indicator: ownPlayerIndicator,
    name: ownPlayerName,
    role: ownRoleTag,
    resources: ownResourceCount,
    units: ownUnitCount,
    baseHp: ownBaseHp
  }, playerId, ownLabel);
  updateTopPlayerPanel({
    panel: opponentPlayerPanel,
    indicator: opponentPlayerIndicator,
    name: opponentPlayerName,
    role: opponentRoleTag,
    resources: opponentResourceCount,
    units: opponentUnitCount,
    baseHp: opponentBaseHp
  }, opponentId, '(Opponent)');

  hudRoomCode.innerText = roomId;
  if (!techTreeModal.classList.contains('hidden')) {
    renderTechTreeModal();
  }
  const player = game.players[playerId];

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
      renderer.highlightMovementTiles(0, 0, false, []);
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
    } else if (cell.type === 'obstacle') {
      selectionName.innerText = 'Water';
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
    if (isOwnBase && !botSessionActive) {
      buildOptionsContainer.classList.remove('hidden');
      renderBaseActionButtons(player);
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

    if (botSessionActive) {
      if (isMoveMode) {
        isMoveMode = false;
        renderer.highlightMovementTiles(selectedCell.x, selectedCell.z, false, ownedSelectedUnits);
      }
      if (isAttackMode) {
        isAttackMode = false;
        renderer.highlightAttackTiles(selectedCell.x, selectedCell.z, false);
      }
    } else if (ownedSelectedUnits.length > 0) {
      const isAnyMoving = ownedSelectedUnits.some(u => u.isMoving);
      if (isAnyMoving) {
        if (isMoveMode) {
          isMoveMode = false;
          renderer.highlightMovementTiles(selectedCell.x, selectedCell.z, false, ownedSelectedUnits);
        }
      } else {
        if (!isMoveMode && !isAttackMode) {
          isMoveMode = true;
          renderer.highlightMovementTiles(selectedCell.x, selectedCell.z, true, ownedSelectedUnits);
        }
      }
    } else {
      if (isMoveMode) {
        isMoveMode = false;
        renderer.highlightMovementTiles(selectedCell.x, selectedCell.z, false, ownedSelectedUnits);
      }
    }

    // Visibility 3: Automatic gold gathering (gather button is hidden)
    btnGather.classList.add('hidden');

    // Visibility 4: Artillery Attack button options
    if (hasArtillerySelected && !botSessionActive) {
      btnAttack.classList.remove('hidden');
      btnAttack.disabled = false;
    } else {
      btnAttack.classList.add('hidden');
    }

    const hasFiringArtillery = ownedSelectedUnits.some(u => u.type === 'artillery' && u.attackTargetX !== null && u.attackTargetX !== undefined);
    if (hasFiringArtillery && !botSessionActive) {
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
