# Python Offensive Bot

This bot is a copied and tuned variant of the strategic bot. It keeps the same HTTP protocol and movement/pathfinding, but uses a phased offensive build plan:

- Early-game: builds a worker economy first, then creates the configured hunter force.
- Mid-game: stops worker production, reserves enough gold for configured base-close towers, upgrades passive income to the configured level, then spends surplus gold on attack units.
- Late-game: ignores worker count, stops tower spending, and focuses on combat unit production, upgrades, and attacking.
- Build phases only advance. Once the bot reaches mid-game or late-game, unit losses do not move it back to an earlier build plan.
- Build phases are selected by `GeneralStrategy/build_order.py`; each phase delegates build and upgrade decisions to a `GamePlan` instance configured by a strategy JSON file.
- Non-worker units use tactical states: `WAITING`, `MOVING`, and `COMBAT`, with state-specific behavior maps for mechs, artillery, and power towers.
- Mechs allocate into `MechSquad` virtual units called `shuttleSquad`; mech movement tactics are calculated for squads at the configured minimum size.
- Artillery forms `SneakyArtillery` squads using the configured artillery count and mech escort count.
- In artillery combat state, artillery keeps strategic aiming behavior, but retreats from nearby enemy mechs while reloading.
- Spends remaining late-game combat money on mechs.
- Uses a squad-planning layer; early mech squads hunt workers, while later mech squads press toward the enemy base.
- Uses `SneakyArtillery` squads to flank through top/bottom lanes and shell the base.
- All squads still engage enemy units that block their immediate route.
- Tracks observed unit movement; artillery can lead moving targets by one tile when possible.
- Defaults to 8 actions per tick instead of 6.

Strategy layout:

- `strategy.py`: session lifecycle, main tick loop, and high-level orchestration.
- `api_client.py`: state fetch and action POST helpers.
- `orders.py`: order construction, interleaving, and duplicate-order throttling.
- `GeneralStrategy/settings.py`: strategy enums, phase thresholds, unit costs, and shared constants.
- `GeneralStrategy/build_order.py`: build phase progression and current `GamePlan` selection.
- `GeneralStrategy/navigation.py`: hex-grid distance, neighbor, passability, and pathfinding helpers.
- `StrategyInstances/default.json`: default strategy instance that mirrors the current offensive bot behavior.
- `StrategyInstances/strategy_instance.py`: strategy JSON loading and access helpers.
- `GamePlans/game_plan.py`: abstract `GamePlan` base class and shared build/upgrade helpers.
- `GamePlans/early_game.py`: early worker and hunter-force build plan.
- `GamePlans/mid_game.py`: tower reservation, passive-income upgrade, and surplus combat build plan.
- `GamePlans/late_game.py`: late combat build and mech upgrade plan.
- `Squads/squad.py`: abstract squad base class for virtual multi-unit actors.
- `Squads/MechSquad/squad.py`: mech squad implementation using the `shuttleSquad` virtual unit.
- `Units/combat_planner.py`: worker/combat order planner glue and unit micro delegation.
- `Units/queries.py`: own/enemy unit filtering, target selection helpers, and resource lookup.
- `Units/tracker.py`: observed unit movement tracking.
- `Units/tactical_state.py`: per-unit tactical state and combat-context detection.
- `Units/Worker/micro.py`: worker gathering movement and worker order planning.
- `Units/Mech/micro.py`: mech squads, worker hunting, blockers, and base pressure.
- `Units/Artillery/micro.py`: artillery flanking, target prediction, and shell target selection.
- `Units/PowerTower/micro.py`: tower reservation, placement goals, and build orders.

Main settings:

- `StrategyInstances/default.json`: bot name, action cap, worker/tower caps, squad sizes, micro behavior, `completionCriteria` for phase transitions, phase build orders, combat build thresholds, and late-game upgrade rules.
- `GeneralStrategy/settings.py`: unit costs, enum identities, tactical constants, micro behavior defaults, and fallback values when a strategy JSON omits a field.
- `squads.mech.minimumUnits`: minimum mech count for a `shuttleSquad`.
- `squads.sneakyArtillery.artilleryCount` and `mechEscortCount`: flanking squad composition.
- `micro.mech`: enemy search range, base standoff, blocker adjacency, and tower avoidance.
- `micro.artillery`: range, escort spacing, shell prediction, combat context, retreat threat range, and tower priority.
- `micro.worker`: resource safety, danger scoring, adjacency, and tower avoidance.
- `micro.powerTower`: combat context, worker safety, and preferred base placement distance.
- `micro.orders`: repeated order throttling and duplicate attack-target suppression.
- `DEFAULT_*_STRATEGY` and `DEFAULT_*_STATE_BEHAVIORS`: selected high-level and tactical-state behavior modes.

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
python3 bots/python/offensive_bot/run_bot.py --strategy-instance bots/python/offensive_bot/StrategyInstances/default.json
```

Tune worker caps:

```bash
python3 bots/python/offensive_bot/run_bot.py --min-workers 2 --max-workers 5
python3 bots/python/offensive_bot/run_bot.py --min-workers 0 --max-workers 3
```

The phased plan uses the values in `StrategyInstances/default.json` unless `--strategy-instance` points at another JSON file. CLI flags such as `--max-workers` override the loaded strategy instance for that run.

By default the bot prints accepted actions and rejected API calls. Use `--quiet` to suppress those logs.

Offline simulation:

```bash
PYTHONPATH=bots/python/offensive_bot python3 -m backend.offline_simulation --players 2 --bot strategy:create_offline_bot --bot strategy:create_offline_bot --ticks 1000
```

The offline runner instantiates the bot class directly and calls `force_tick(player_state)`. In that mode the offensive bot returns the action JSON it would normally POST to `/api/action`, without using HTTP.
