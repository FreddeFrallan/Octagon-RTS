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

Run one of the examples, then use `http://127.0.0.1:8787` in the lobby bot URL field.
