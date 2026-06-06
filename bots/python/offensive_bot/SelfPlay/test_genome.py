#!/usr/bin/env python3
import json
import sys
import unittest
from pathlib import Path


BOT_ROOT = Path(__file__).resolve().parents[1]
if str(BOT_ROOT) not in sys.path:
  sys.path.insert(0, str(BOT_ROOT))

from SelfPlay.genome import GENE_METADATA, GENE_REPAIR_RULES, PHASE_KEYS, TECH_UPGRADE_NAMES, StrategyGenome


class StrategyGenomeTest(unittest.TestCase):
  def load_default_strategy(self):
    default_path = BOT_ROOT / "StrategyInstances" / "default.json"
    with default_path.open("r", encoding="utf-8") as file:
      return json.load(file)

  def test_default_strategy_round_trips_through_genome(self):
    default_strategy = self.load_default_strategy()
    genome = StrategyGenome.from_strategy_instance(default_strategy)

    self.assertEqual(
      0,
      genome.genes["phases.early_game.buildOrder.artillery.targetCount"]
    )
    self.assertEqual(
      0,
      genome.genes["phases.early_game.completionCriteria.unitCounts.artillery"]
    )
    self.assertEqual(default_strategy, genome.to_strategy_instance())

  def test_all_genes_have_metadata(self):
    genome = StrategyGenome.from_strategy_instance(self.load_default_strategy())

    self.assertEqual(set(genome.genes), set(GENE_METADATA))

  def test_default_genes_are_valid_for_metadata(self):
    genome = StrategyGenome.from_strategy_instance(self.load_default_strategy())

    invalid = [
      key for key, value in genome.genes.items()
      if not GENE_METADATA[key].contains(value)
    ]

    self.assertEqual([], invalid)

  def test_upgrade_genes_cover_all_phases_and_tech_upgrades(self):
    genome = StrategyGenome.from_strategy_instance(self.load_default_strategy())

    for phase in PHASE_KEYS:
      self.assertIn(f"phases.{phase}.upgradeAllocation", genome.genes)
      for upgrade_name in TECH_UPGRADE_NAMES:
        counter_key = f"phases.{phase}.upgrades.{upgrade_name}.counterWeight"
        max_level_key = f"phases.{phase}.upgrades.{upgrade_name}.maxLevel"

        self.assertIn(counter_key, genome.genes)
        self.assertIn(max_level_key, genome.genes)
        self.assertEqual(0.0, GENE_METADATA[counter_key].minimum)
        self.assertEqual(1.0, GENE_METADATA[counter_key].maximum)
        self.assertEqual(0, GENE_METADATA[max_level_key].minimum)
        self.assertEqual(30, GENE_METADATA[max_level_key].maximum)

  def test_repair_rules_reference_known_genes(self):
    known_genes = set(GENE_METADATA)

    for left, operator, right in GENE_REPAIR_RULES:
      self.assertIn(left, known_genes)
      self.assertIn(right, known_genes)
      self.assertEqual("<=", operator)


if __name__ == "__main__":
  unittest.main()
