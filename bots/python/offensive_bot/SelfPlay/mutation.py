import random
from collections import OrderedDict

from SelfPlay.genome import (
  GENE_METADATA,
  GENE_REPAIR_RULES,
  GENE_TYPE_BOOL,
  GENE_TYPE_CATEGORY,
  GENE_TYPE_FLOAT,
  GENE_TYPE_INT,
  GENE_TYPE_TEXT,
  StrategyGenome
)


def create_offspring(parent_a, parent_b, mutation_rate=0.1, rng=None):
  if rng is None:
    rng = random.Random()
  validate_parent_keys(parent_a, parent_b)

  child_genes = OrderedDict()
  for key in GENE_METADATA:
    selected_parent = parent_a if rng.random() < 0.5 else parent_b
    value = selected_parent.genes[key]
    child_genes[key] = mutate_value(key, value, mutation_rate, rng)

  repair_genes(child_genes)
  return StrategyGenome(child_genes)


def validate_parent_keys(parent_a, parent_b):
  expected = set(GENE_METADATA)
  parent_a_keys = set(parent_a.genes)
  parent_b_keys = set(parent_b.genes)
  if parent_a_keys != expected:
    missing = sorted(expected - parent_a_keys)
    extra = sorted(parent_a_keys - expected)
    raise ValueError(f"parent_a genome keys do not match metadata; missing={missing}, extra={extra}")
  if parent_b_keys != expected:
    missing = sorted(expected - parent_b_keys)
    extra = sorted(parent_b_keys - expected)
    raise ValueError(f"parent_b genome keys do not match metadata; missing={missing}, extra={extra}")


def mutate_value(key, value, mutation_rate, rng):
  meta = GENE_METADATA[key]
  if not meta.mutable or rng.random() >= mutation_rate:
    return value

  if meta.gene_type == GENE_TYPE_TEXT:
    return value
  if meta.gene_type == GENE_TYPE_BOOL:
    return not value
  if meta.gene_type == GENE_TYPE_CATEGORY:
    return mutate_category(meta, value, rng)
  if meta.gene_type == GENE_TYPE_INT:
    return mutate_number(meta, value, rng, integer=True)
  if meta.gene_type == GENE_TYPE_FLOAT:
    return mutate_number(meta, value, rng, integer=False)
  return value


def mutate_category(meta, value, rng):
  choices = [option for option in meta.options if option != value]
  if not choices:
    return value
  return rng.choice(choices)


def mutate_number(meta, value, rng, integer):
  step = meta.step or 1
  direction = -1 if rng.random() < 0.5 else 1
  mutated = value + direction * step
  mutated = max(meta.minimum, min(meta.maximum, mutated))
  if integer:
    return int(round(mutated))
  return round(float(mutated), 3)


def repair_genes(genes):
  for left, operator, right in GENE_REPAIR_RULES:
    if operator != "<=":
      raise ValueError(f"Unsupported repair operator: {operator}")
    if genes[left] > genes[right]:
      genes[left] = genes[right]

  for key, meta in GENE_METADATA.items():
    genes[key] = clamp_to_metadata(meta, genes[key])


def clamp_to_metadata(meta, value):
  if meta.gene_type == GENE_TYPE_INT:
    return int(max(meta.minimum, min(meta.maximum, value)))
  if meta.gene_type == GENE_TYPE_FLOAT:
    return round(float(max(meta.minimum, min(meta.maximum, value))), 3)
  if meta.gene_type == GENE_TYPE_CATEGORY and value not in meta.options:
    return meta.options[0]
  if meta.gene_type == GENE_TYPE_BOOL:
    return bool(value)
  return value
