#!/usr/bin/env python3
import json
import random
import sys
import unittest
from pathlib import Path


BOT_ROOT = Path(__file__).resolve().parents[1]
if str(BOT_ROOT) not in sys.path:
  sys.path.insert(0, str(BOT_ROOT))

from SelfPlay.genome import GENE_METADATA, StrategyGenome
from SelfPlay.mutation import create_offspring


class MutationTest(unittest.TestCase):
  def load_default_genome(self):
    default_path = BOT_ROOT / "StrategyInstances" / "default.json"
    with default_path.open("r", encoding="utf-8") as file:
      return StrategyGenome.from_strategy_instance(json.load(file))

  def test_create_offspring_returns_valid_genome(self):
    parent_a = self.load_default_genome()
    parent_b = self.load_default_genome()

    offspring = create_offspring(parent_a, parent_b, mutation_rate=1.0, rng=random.Random(7))

    self.assertEqual(set(GENE_METADATA), set(offspring.genes))
    invalid = [
      key for key, value in offspring.genes.items()
      if not GENE_METADATA[key].contains(value)
    ]
    self.assertEqual([], invalid)

  def test_offspring_can_decode_to_strategy_instance(self):
    parent_a = self.load_default_genome()
    parent_b = self.load_default_genome()

    offspring = create_offspring(parent_a, parent_b, mutation_rate=1.0, rng=random.Random(13))
    strategy = offspring.to_strategy_instance()

    self.assertIn("phases", strategy)
    self.assertIn("early_game", strategy["phases"])
    self.assertIn("buildOrder", strategy["phases"]["early_game"])

  def test_repairs_cross_gene_constraints(self):
    parent_a = self.load_default_genome()
    parent_b = self.load_default_genome()
    parent_a.genes["unitLimits.minWorkers"] = 20
    parent_a.genes["unitLimits.maxWorkers"] = 0
    parent_b.genes["unitLimits.minWorkers"] = 20
    parent_b.genes["unitLimits.maxWorkers"] = 0

    offspring = create_offspring(parent_a, parent_b, mutation_rate=0.0, rng=random.Random(1))

    self.assertLessEqual(
      offspring.genes["unitLimits.minWorkers"],
      offspring.genes["unitLimits.maxWorkers"]
    )


if __name__ == "__main__":
  unittest.main()
