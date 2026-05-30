# Python Strategic Bot

This bot is a larger example that balances two objectives every strategy tick:

- Economy: workers path toward tiles adjacent to resource cells while choosing safer paths away from nearby enemies.
- Damage: mechs and artillery target the closest enemy threat, including the enemy base.

The build policy tracks what the bot has spent after a session starts and defaults to roughly 50% of spending on workers and 50% on combat units. Combat spending alternates between mechs and artillery, with at least some artillery kept in the army. When it is not building, it can buy useful tech upgrades for unit types it currently controls.

Movement uses simple breadth-first pathfinding over passable tiles, so units can route around resources, bases, and obstacles instead of only moving greedily toward a target.

Run it:

```bash
python3 bots/python/strategic_bot/run_bot.py
```

It defaults to:

```text
http://127.0.0.1:8788
```

Use another port:

```bash
python3 bots/python/strategic_bot/run_bot.py --port 8790
```

Then enter the matching URL in the game lobby before hosting or joining.

Useful flags:

```bash
python3 bots/python/strategic_bot/run_bot.py --host 127.0.0.1 --port 8788 --name "Strategist" --max-actions 6
```

`--max-actions` limits how many upgrade/move/attack orders the bot can send per tick. Lower it if you want a slower, easier-to-watch bot.

Tune worker versus attack spending:

```bash
python3 bots/python/strategic_bot/run_bot.py --worker-allocation 0.7
python3 bots/python/strategic_bot/run_bot.py --worker-allocation 30
```

`--worker-allocation 0.7` means about 70% worker spending and 30% attack spending. Values can be ratios from `0` to `1`, or percentages from `0` to `100`.

By default the bot prints accepted actions and rejected API calls. Use `--quiet` to suppress those logs.
