from http.server import SimpleHTTPRequestHandler
import json
import urllib.parse

from api.actions import handle_action
from api.lobby import get_rooms, get_state, host_room, join_room, set_map_settings, set_room_map, start_room
from api.responses import send_error_json, send_json
from net import get_local_ip
from static_files import translate_static_path


class GameRequestHandler(SimpleHTTPRequestHandler):
  def translate_path(self, path):
    return translate_static_path(path)

  def end_headers(self):
    self.send_header('Access-Control-Allow-Origin', '*')
    self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
    self.send_header('Access-Control-Allow-Headers', 'Content-Type')
    super().end_headers()

  def do_OPTIONS(self):
    self.send_response(200)
    self.end_headers()

  def do_GET(self):
    url = urllib.parse.urlparse(self.path)
    if url.path.startswith('/api/rooms'):
      send_json(self, get_rooms())
    elif url.path.startswith('/api/ip'):
      send_json(self, {"ip": get_local_ip()})
    elif url.path.startswith('/api/state'):
      data, error = get_state(url.query)
      if error:
        send_error_json(self, error)
      else:
        send_json(self, data)
    else:
      super().do_GET()

  def do_POST(self):
    url = urllib.parse.urlparse(self.path)
    content_length = int(self.headers.get('Content-Length', 0))
    body = self.rfile.read(content_length).decode('utf-8') if content_length > 0 else ""
    data = json.loads(body) if body else {}

    if url.path.startswith('/api/host'):
      payload, error = host_room(data)
    elif url.path.startswith('/api/join'):
      payload, error = join_room(data)
    elif url.path.startswith('/api/start'):
      payload, error = start_room(data)
    elif url.path.startswith('/api/map-settings'):
      payload, error = set_map_settings(data)
    elif url.path.startswith('/api/map'):
      payload, error = set_room_map(data)
    elif url.path.startswith('/api/action'):
      payload, error = handle_action(data)
    else:
      self.send_response(404)
      self.end_headers()
      return

    if error:
      send_error_json(self, error)
    else:
      send_json(self, payload)
