from config import TECH_TREE_CONFIG


def update_passive_income(room):
  for player_id, player in room.players.items():
    if player.get("baseHp", 0) <= 0:
      continue

    income = passive_income_for_player(player)
    if income <= 0:
      continue

    player["crystals"] += income
    room.log(f"{player['name']} gained {income} passive gold.", "gather")


def passive_income_for_player(player):
  income = 0
  for upgrade_name, level in player.get("techUpgrades", {}).items():
    if level <= 0:
      continue

    upgrade = TECH_TREE_CONFIG.get(upgrade_name, {})
    if upgrade.get("type") != "PassiveIncome":
      continue

    income += level * upgrade.get("valueIncrease", 0)

  return income
