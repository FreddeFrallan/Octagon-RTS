#!/usr/bin/env python3
import argparse
import json
import random
import sys
import tempfile
import signal
from concurrent.futures import ProcessPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path
from tqdm import tqdm

ROOT = Path(__file__).resolve().parents[4]
BACKEND = ROOT / "backend"
BOT_ROOT = Path(__file__).resolve().parents[1]

for path in (str(BACKEND), str(BOT_ROOT)):
    if path not in sys.path:
        sys.path.insert(0, path)

from offline_simulation.runner import run_offline_simulation
from SelfPlay.genome import StrategyGenome
from SelfPlay.mutation import create_offspring
from strategy import OffensiveBot

DEFAULT_STRATEGY_PATH = BOT_ROOT / "StrategyInstances" / "default.json"
DEFAULT_RUNS_DIR = BOT_ROOT / "SelfPlay" / "Runs"


# Inherit from BaseException so generic `except Exception:` blocks
# inside the game simulation don't accidentally swallow the timeout.
class TimeoutException(BaseException):
    pass


def timeout_handler(signum, frame):
    raise TimeoutException("Game execution exceeded wall-time limit")


def parse_args():
    parser = argparse.ArgumentParser(
        description="Optimize offensive bot genomes through randomized population self-play.")
    parser.add_argument("--num-games-per-round", type=int, default=10,
                        help="Random paired games per population slot each generation. Default: 10")
    parser.add_argument("--population-size", type=int, default=20,
                        help="Number of genomes per generation, including one static default genome. Default: 20")
    parser.add_argument("--num-procs", type=int, default=10, help="Parallel worker processes. Default: 10")
    parser.add_argument("--num-rounds", type=int, default=10, help="Number of generations to run. Default: 10")
    parser.add_argument("--max-ticks", type=int, default=10000, help="Maximum ticks per game. Default: 10000")
    parser.add_argument("--mutation-rate", type=float, default=0.12, help="Per-gene mutation chance. Default: 0.12")
    parser.add_argument("--seed", type=int, default=None, help="Random seed for reproducible parent selection.")
    parser.add_argument("--runs-dir", default=str(DEFAULT_RUNS_DIR),
                        help=f"Parent folder for timestamped run outputs. Default: {DEFAULT_RUNS_DIR}")
    parser.add_argument("--timeout", type=int, default=20,
                        help="Wall-time limit per game in seconds. Default: 45")
    parser.add_argument("--max-retries", type=int, default=3,
                        help="Number of times to retry a game if it times out or fails. Default: 3")
    return parser.parse_args()


def load_default_genome():
    with DEFAULT_STRATEGY_PATH.open("r", encoding="utf-8") as file:
        return StrategyGenome.from_strategy_instance(json.load(file))


def make_initial_population(default_genome, population_size, mutation_rate, rng):
    population = [default_genome]
    while len(population) < population_size:
        population.append(create_offspring(default_genome, default_genome, mutation_rate=mutation_rate, rng=rng))
    return population


def evaluate_game(player_one_index, player_one_strategy, player_two_index, player_two_strategy, max_ticks, timeout, max_retries):
    for attempt in range(max_retries):
        try:
            # Set the wall-time alarm for this specific execution attempt
            if timeout > 0:
                signal.signal(signal.SIGALRM, timeout_handler)
                signal.alarm(timeout)

            # Use a TemporaryDirectory so files are guaranteed to exist for the full game duration
            with tempfile.TemporaryDirectory() as temp_dir:
                p1_file = Path(temp_dir) / "p1.json"
                p2_file = Path(temp_dir) / "p2.json"

                with p1_file.open("w", encoding="utf-8") as f:
                    json.dump(player_one_strategy, f)
                with p2_file.open("w", encoding="utf-8") as f:
                    json.dump(player_two_strategy, f)

                def factory_1():
                    return OffensiveBot(verbose=False, strategy_instance_path=str(p1_file))

                def factory_2():
                    return OffensiveBot(verbose=False, strategy_instance_path=str(p2_file))

                bot_factories = [factory_1, factory_2]

                result = run_offline_simulation(
                    player_count=2,
                    bot_factories=bot_factories,
                    max_ticks=max_ticks
                )

                player_one_score = score_result(result.room.winner, 1, result.ticks, max_ticks)
                player_two_score = score_result(result.room.winner, 2, result.ticks, max_ticks)

                # Disable the alarm if the simulation finishes cleanly
                if timeout > 0:
                    signal.alarm(0)

                return {
                    "playerOneIndex": player_one_index,
                    "playerTwoIndex": player_two_index,
                    "playerOneScore": player_one_score,
                    "playerTwoScore": player_two_score,
                    "winner": result.room.winner,
                    "ticks": result.ticks
                }

        except TimeoutException:
            if timeout > 0:
                signal.alarm(0)
            # Silent catch to allow the loop to retry

        except Exception as e:
            if timeout > 0:
                signal.alarm(0)
            print(f"\nGame error (P{player_one_index} vs P{player_two_index}) on attempt {attempt + 1}: {e}", file=sys.stderr)

    # Fallback if the game exhausts all retries (returns a 0-score draw to avoid crashing the whole generation)
    return {
        "playerOneIndex": player_one_index,
        "playerTwoIndex": player_two_index,
        "playerOneScore": 0,
        "playerTwoScore": 0,
        "winner": None,
        "ticks": max_ticks
    }


def score_result(winner, candidate_player_id, ticks, max_ticks):
    speed_score = max_ticks - ticks
    if winner == candidate_player_id:
        return max_ticks + speed_score
    if winner is None:
        return 0
    return -(max_ticks + speed_score)


def evaluate_population(population, num_games_per_round, max_ticks, num_procs, rng, round_index, timeout, max_retries):
    strategies = [genome.to_strategy_instance() for genome in population]
    total_games = len(population) * num_games_per_round
    tasks = [
        random_pairing_task(strategies, max_ticks, rng, timeout, max_retries)
        for _ in range(total_games)
    ]

    results = [
        {
            "genome": genome,
            "index": genome_index,
            "staticDefault": genome_index == 0,
            "score": 0,
            "wins": 0,
            "losses": 0,
            "draws": 0,
            "ticks": 0,
            "games": 0
        }
        for genome_index, genome in enumerate(population)
    ]

    with ProcessPoolExecutor(max_workers=num_procs) as executor:
        futures = [executor.submit(evaluate_game, *task) for task in tasks]

        # Wrap as_completed with tqdm for the progress bar
        progress_bar = tqdm(as_completed(futures), total=total_games, desc=f"Round {round_index:02d} Games")
        for future in progress_bar:
            game = future.result()
            aggregate_match(results, game)

    for result in results:
        result["averageScore"] = result["score"] / max(1, result["games"])
        result["averageTicks"] = result["ticks"] / max(1, result["games"])

    return sorted(results, key=lambda item: item["averageScore"], reverse=True)


def random_pairing_task(strategies, max_ticks, rng, timeout, max_retries):
    player_one_index, player_two_index = rng.sample(range(len(strategies)), 2)
    if rng.random() < 0.5:
        player_one_index, player_two_index = player_two_index, player_one_index
    return (
        player_one_index,
        strategies[player_one_index],
        player_two_index,
        strategies[player_two_index],
        max_ticks,
        timeout,
        max_retries
    )


def aggregate_match(results, game):
    aggregate_player_result(
        results[game["playerOneIndex"]],
        game["playerOneScore"],
        game["winner"],
        1,
        game["ticks"]
    )
    aggregate_player_result(
        results[game["playerTwoIndex"]],
        game["playerTwoScore"],
        game["winner"],
        2,
        game["ticks"]
    )


def aggregate_player_result(result, score, winner, player_id, ticks):
    result["score"] += score
    result["ticks"] += ticks
    result["games"] += 1
    if winner is None:
        result["draws"] += 1
    elif winner == player_id:
        result["wins"] += 1
    else:
        result["losses"] += 1


def next_generation(default_genome, evaluated, population_size, mutation_rate, rng):
    elite_count = max(2, population_size // 4)
    mutable_elites = [
        item["genome"]
        for item in evaluated
        if not item["staticDefault"]
    ][:elite_count]
    if len(mutable_elites) < 2:
        mutable_elites = [item["genome"] for item in evaluated[:elite_count]]

    next_population = [default_genome]
    for elite in mutable_elites:
        if len(next_population) >= population_size:
            break
        next_population.append(elite)

    while len(next_population) < population_size:
        parent_a = rng.choice(mutable_elites)
        parent_b = rng.choice(mutable_elites)
        next_population.append(create_offspring(parent_a, parent_b, mutation_rate=mutation_rate, rng=rng))

    return next_population


def print_round(round_index, evaluated):
    best = evaluated[0]
    default = next(item for item in evaluated if item["staticDefault"])
    print(
        f"round={round_index} "
        f"best_avg_score={best['averageScore']:.2f} "
        f"wins={best['wins']} losses={best['losses']} draws={best['draws']} "
        f"avg_ticks={best['averageTicks']:.1f} "
        f"default_avg_score={default['averageScore']:.2f}",
        flush=True
    )


def create_run_dir(parent_dir):
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    run_dir = Path(parent_dir) / timestamp
    suffix = 1
    while run_dir.exists():
        run_dir = Path(parent_dir) / f"{timestamp}_{suffix}"
        suffix += 1
    run_dir.mkdir(parents=True)
    return run_dir


def write_round_best(run_dir, round_index, result):
    output_path = run_dir / f"round_{round_index:04d}.json"
    with output_path.open("w", encoding="utf-8") as file:
        json.dump(result["genome"].to_strategy_instance(), file, indent=2)
        file.write("\n")
    return output_path


def best_mutable(evaluated):
    return next(item for item in evaluated if not item["staticDefault"])


def main():
    args = parse_args()
    if args.population_size < 2:
        raise ValueError("--population-size must be at least 2")
    if args.num_games_per_round < 1:
        raise ValueError("--num-games-per-round must be at least 1")
    if args.num_procs < 1:
        raise ValueError("--num-procs must be at least 1")

    rng = random.Random(args.seed)
    default_genome = load_default_genome()
    population = make_initial_population(default_genome, args.population_size, args.mutation_rate, rng)
    best = None
    run_dir = create_run_dir(args.runs_dir)
    print(f"run_dir={run_dir}\n", flush=True)

    for round_index in range(1, args.num_rounds + 1):
        evaluated = evaluate_population(population, args.num_games_per_round, args.max_ticks, args.num_procs, rng,
                                        round_index, args.timeout, args.max_retries)
        print_round(round_index, evaluated)
        round_best_mutable = best_mutable(evaluated)
        written_path = write_round_best(run_dir, round_index, round_best_mutable)
        print(f"saved_round_best={written_path}\n", flush=True)
        if best is None or round_best_mutable["averageScore"] > best["averageScore"]:
            best = round_best_mutable
        population = next_generation(default_genome, evaluated, args.population_size, args.mutation_rate, rng)

    print(
        f"best score={best['averageScore']:.2f} "
        f"wins={best['wins']} losses={best['losses']} draws={best['draws']} "
        f"avg_ticks={best['averageTicks']:.1f}"
    )
    print(f"run_dir={run_dir}")


if __name__ == "__main__":
    main()