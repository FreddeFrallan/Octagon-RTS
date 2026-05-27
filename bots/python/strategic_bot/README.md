# Python Strategic Bot

This bot is a larger example that balances two objectives every strategy tick:

- Economy: workers prefer resource cells while choosing safer paths away from nearby enemies.
- Damage: mechs and artillery prioritize enemy workers, then enemy combat units, then the enemy base.

The build policy tracks what the bot has spent after a session starts and tries to keep roughly 50% of spending on workers and 50% on combat units. Combat spending alternates between mechs and artillery, with at least some artillery kept in the army.

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

`--max-actions` limits how many build/move/attack orders the bot can send per tick. Lower it if you want a slower, easier-to-watch bot.
