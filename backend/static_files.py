import os
import urllib.parse


def translate_static_path(path):
  parsed_path = urllib.parse.urlparse(path).path
  base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
  if parsed_path == "/units.json":
    return os.path.join(base_dir, "backend", "units.json")
  if parsed_path == "/tech_tree.json":
    return os.path.join(base_dir, "backend", "tech_tree.json")
  if parsed_path == "/map.json":
    return os.path.join(base_dir, "backend", "map.json")

  rel_path = parsed_path.lstrip('/')
  if not rel_path:
    rel_path = 'index.html'
  return os.path.join(base_dir, "frontend", rel_path)
