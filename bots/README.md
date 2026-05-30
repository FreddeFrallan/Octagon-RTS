# Octagon-RTS Local Bot API

Bots run as local HTTP servers. The browser connects to the bot before hosting or joining a match, then sends the match session details after the player has a room and player id.

## Bot Server Contract

The browser expects these endpoints on the local bot:

```text
POST /handshake
POST /session
POST /stop
```

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

After `/session`, the bot should poll with `events=0` so it does not consume the browser's one-shot animation events:

```text
GET <gameServer>/api/state?roomId=<roomId>&playerId=<playerId>&events=0
```

And send actions:

```text
POST <gameServer>/api/action
```

Action body:

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

Tech upgrade body:

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

Strategic Python bot:

```bash
python3 bots/python/strategic_bot/run_bot.py --port 8788
```

Then enter:

```text
http://127.0.0.1:8788
```

This example balances worker/resource play against combat pressure. Workers seek resources while avoiding enemies; mechs and artillery prioritize enemy workers, then enemy combat units, then the base.
