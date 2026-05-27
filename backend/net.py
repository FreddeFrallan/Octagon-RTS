import errno
import socket
import socketserver
from http.server import HTTPServer


def get_local_ip():
  try:
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.connect(("8.8.8.8", 80))
    ip = sock.getsockname()[0]
    sock.close()
    return ip
  except Exception:
    return "127.0.0.1"


class ThreadingHTTPServer(socketserver.ThreadingMixIn, HTTPServer):
  pass


def create_server(host, port, handler_cls):
  try:
    return ThreadingHTTPServer((host, port), handler_cls)
  except OSError as e:
    if e.errno != errno.EADDRINUSE:
      raise

    bind_addr = "localhost" if host in ("0.0.0.0", "::", "127.0.0.1") else host
    print("="*60)
    print(f"Cannot start server: {bind_addr}:{port} is already in use.")
    print("Another Octagon-RTS server or another app is already using that port.")
    print(f"Stop the existing process, or start this server on another port:")
    print(f"  PORT={port + 1} python3 backend/server.py")
    print(f"  PORT={port + 1} ./start-localhost.sh")
    print("="*60)
    raise SystemExit(1) from e
