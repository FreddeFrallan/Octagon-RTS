# Octagon-RTS Local Bot API

Bots run as local HTTP servers. The browser connects to the bot before hosting or joining a match, then sends the match session details after the player has a room and player id.

## Bot Server Contract

The browser expects these endpoints on the local bot:

```text
POST /handshake
POST /session
POST /stop
```

Bot servers should also respond to `OPTIONS` requests and allow browser CORS headers for local development.

`POST /handshake` request:

```json
{
  "protocol": "octagon-rts-bot-v1",
  "game": "Octagon-RTS",
  "pageOrigin": "http://localhost:8000"
}
```

Response:

```json
{
  "ok": true,
  "name": "Example Bot"
}
```

`POST /session` request:

```json
{
  "protocol": "octagon-rts-bot-v1",
  "gameServer": "http://localhost:8000",
  "roomId": "ABCD",
  "playerId": 1,
  "playerName": "Commander",
  "pollMs": 200
}
```

Response:

```json
{
  "ok": true,
  "name": "Example Bot"
}
```

`POST /stop` request:

```json
{
  "protocol": "octagon-rts-bot-v1",
  "roomId": "ABCD",
  "playerId": 1
}
```

Response:

```json
{
  "ok": true
}
```

After `/session`, the bot should poll with `events=0` so it does not consume the browser's one-shot animation events:

```text
GET <gameServer>/api/state?roomId=<roomId>&playerId=<playerId>&events=0
```

The state response includes:

- `status`, `winner`, `roomId`, `mapName`, `mapMode`, `fogOfWar`
- `players`, keyed by player id strings, including `crystals`, `baseHp`, `maxBaseHp`, `basePos`, and `techUpgrades`
- `gridSize`, `gridWidth`, `gridHeight`, and `grid[x][z]` cells with `x`, `z`, `type`, `owner`, `gold`, `maxGold`, and `visible`
- `units`, keyed by unit id, with unit stats, movement fields, and artillery target fields
- `techTree`, keyed by upgrade name
- `logs`
- `events`, empty when `events=0`

## Game Action API

Bots send actions to the game server:

```text
POST <gameServer>/api/action
```

Every action uses this envelope:

```json
{
  "roomId": "ABCD",
  "playerId": 1,
  "action": "build",
  "args": {}
}
```

Successful response:

```json
{
  "success": true
}
```

Errors return HTTP 400 with:

```json
{
  "error": "Reason"
}
```

Build a unit:

```json
{
  "roomId": "ABCD",
  "playerId": 1,
  "action": "build",
  "args": {
    "unitType": "worker"
  }
}
```

Valid `unitType` values are defined in `backend/units.json`; the current built-in unit types are `worker`, `mech`, and `artillery`.

Move one or more units to an adjacent passable cell:

```json
{
  "roomId": "ABCD",
  "playerId": 1,
  "action": "move",
  "args": {
    "unitIds": ["unit_1"],
    "toX": 4,
    "toZ": 5
  }
}
```

Buy a tech upgrade:

```json
{
  "roomId": "ABCD",
  "playerId": 1,
  "action": "upgrade",
  "args": {
    "upgradeName": "upgrade_worker_attack"
  }
}
```

Available upgrades are included in the polled state as `techTree`, and each player state includes purchased levels in `techUpgrades`.

Set artillery fire target:

```json
{
  "roomId": "ABCD",
  "playerId": 1,
  "action": "attack",
  "args": {
    "unitIds": ["unit_3"],
    "toX": 6,
    "toZ": 2
  }
}
```

Only stationary owned artillery can use `attack`. The target must be within the artillery range configured in `backend/units.json`.

Stop artillery fire:

```json
{
  "roomId": "ABCD",
  "playerId": 1,
  "action": "stop",
  "args": {
    "unitIds": ["unit_3"]
  }
}
```

## Examples

Run one of the examples, then use `http://127.0.0.1:8787` in the lobby bot URL field.

Python example:

```bash
python3 bots/python/example_bot.py
```

Use a different port:

```bash
python3 bots/python/example_bot.py --port 8788
```

Then enter the matching URL in the lobby:

```text
http://127.0.0.1:8788
```

Other Python flags:

```bash
python3 bots/python/example_bot.py --host 127.0.0.1 --port 8787 --name "Worker Bot"
```

JavaScript example:

```bash
node bots/javascript/exampleBot.js
```

Strategic Python bot:

```bash
python3 bots/python/strategic_bot/run_bot.py --port 8788
```

Then enter:

```text
http://127.0.0.1:8788
```

This example balances worker/resource play against combat pressure. Workers seek resources while avoiding enemies; mechs and artillery prioritize enemy workers, then enemy combat units, then the base.
