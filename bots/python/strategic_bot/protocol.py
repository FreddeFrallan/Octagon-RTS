from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json

PROTOCOL = "octagon-rts-bot-v1"


def read_json(handler):
  length = int(handler.headers.get("Content-Length", 0))
  if length == 0:
    return {}
  return json.loads(handler.rfile.read(length).decode("utf-8"))


class BotHttpServer:
  def __init__(self, host, port, bot):
    self.host = host
    self.port = port
    self.bot = bot

  def serve_forever(self):
    bot = self.bot

    class Handler(BaseHTTPRequestHandler):
      def _send(self, status, payload):
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

      def do_OPTIONS(self):
        self._send(200, {"ok": True})

      def do_POST(self):
        try:
          payload = read_json(self)
        except json.JSONDecodeError:
          self._send(400, {"error": "Invalid JSON"})
          return

        if payload.get("protocol") != PROTOCOL:
          self._send(400, {"error": "Unsupported bot protocol"})
          return

        if self.path == "/handshake":
          self._send(200, {"ok": True, "name": bot.name})
          return

        if self.path == "/session":
          try:
            bot.start_session(payload)
          except KeyError as e:
            self._send(400, {"error": f"Missing session field: {e.args[0]}"})
            return
          self._send(200, {"ok": True, "name": bot.name})
          return

        if self.path == "/stop":
          bot.stop_session()
          self._send(200, {"ok": True})
          return

        self._send(404, {"error": "Not found"})

      def log_message(self, fmt, *args):
        return

    ThreadingHTTPServer((self.host, self.port), Handler).serve_forever()
