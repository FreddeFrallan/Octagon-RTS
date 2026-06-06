import json
import urllib.error
import urllib.request


def post_json(url, payload):
  data = json.dumps(payload).encode("utf-8")
  req = urllib.request.Request(
    url,
    data=data,
    headers={"Content-Type": "application/json"},
    method="POST"
  )
  with urllib.request.urlopen(req, timeout=2) as res:
    return json.loads(res.read().decode("utf-8"))


def get_json(url):
  with urllib.request.urlopen(url, timeout=2) as res:
    return json.loads(res.read().decode("utf-8"))


class ApiClientMixin:
  def fetch_state(self, current):
    return get_json(
      f"{current['gameServer']}/api/state"
      f"?roomId={current['roomId']}&playerId={current['playerId']}&events=0"
    )

  def action(self, current, action_name, args):
    try:
      result = post_json(f"{current['gameServer']}/api/action", {
        "roomId": current["roomId"],
        "playerId": current["playerId"],
        "action": action_name,
        "args": args
      })
      success = result.get("success", False)
      if success:
        self.log(f"{action_name} {args}")
      return success
    except urllib.error.HTTPError as e:
      message = e.reason
      try:
        payload = json.loads(e.read().decode("utf-8"))
        message = payload.get("error", message)
      except (json.JSONDecodeError, UnicodeDecodeError):
        pass
      self.log(f"{action_name} rejected: {message}")
      return False
