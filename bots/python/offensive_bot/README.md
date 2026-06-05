# Python Offensive Bot

This bot is a copied and tuned variant of the strategic bot. It keeps the same HTTP protocol and movement/pathfinding, but uses a speed-focused melee strategy:

- Builds at least 1 worker by default.
- Never builds more than 5 workers by default.
- Buys one artillery to form a `SneakyArtillery` squad.
- Spends remaining combat money on mechs.
- Only buys mech `moveSpeed` and `maxHp` upgrades.
- Prioritizes speed upgrades before HP upgrades.
- Uses a squad-planning layer; the initial mech squad is one mech pressing toward the enemy base.
- Uses `SneakyArtillery` squads with one artillery and one mech escort to flank through top/bottom lanes and shell the base.
- All squads still engage enemy units that block their immediate route.
- Tracks observed unit movement; artillery targets stationary units directly after 2 seconds, otherwise leads moving targets by one tile when possible.
- Defaults to 8 actions per tick instead of 6.

Run it:

```bash
python3 bots/python/offensive_bot/run_bot.py
```

It defaults to:

```text
http://127.0.0.1:8789
```

Use another port:

```bash
python3 bots/python/offensive_bot/run_bot.py --port 8791
```

Useful flags:

```bash
python3 bots/python/offensive_bot/run_bot.py --host 127.0.0.1 --port 8789 --name "Mech Rusher" --max-actions 10
```

Tune worker caps:

```bash
python3 bots/python/offensive_bot/run_bot.py --min-workers 2 --max-workers 5
python3 bots/python/offensive_bot/run_bot.py --min-workers 0 --max-workers 3
```

`--max-workers 5` means the bot will not intentionally build a sixth worker. If mechs are unaffordable and the bot already has 5 workers, it saves gold instead of adding more economy.

By default the bot prints accepted actions and rejected API calls. Use `--quiet` to suppress those logs.
