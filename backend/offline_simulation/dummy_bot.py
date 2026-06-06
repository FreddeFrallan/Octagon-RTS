class DummyBot:
  def __init__(self, name="Offline Dummy Bot"):
    self.name = name

  def force_tick(self, player_state):
    return None
