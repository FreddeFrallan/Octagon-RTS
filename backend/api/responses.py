import json


def send_json(handler, data):
  handler.send_response(200)
  handler.send_header('Content-Type', 'application/json')
  payload = json.dumps(data).encode('utf-8')
  handler.send_header('Content-Length', str(len(payload)))
  handler.end_headers()
  handler.wfile.write(payload)


def send_error_json(handler, msg):
  handler.send_response(400)
  handler.send_header('Content-Type', 'application/json')
  payload = json.dumps({"error": msg}).encode('utf-8')
  handler.send_header('Content-Length', str(len(payload)))
  handler.end_headers()
  handler.wfile.write(payload)
