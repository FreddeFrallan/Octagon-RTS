def get_neighbors(x, z, grid_width=8, grid_height=None):
  if grid_height is None:
    grid_height = grid_width

  # Pointy-topped odd-r offset coordinates
  neighbors = []
  if z % 2 == 0:
    coords = [(x-1, z), (x+1, z), (x-1, z-1), (x, z-1), (x-1, z+1), (x, z+1)]
  else:
    coords = [(x-1, z), (x+1, z), (x, z-1), (x+1, z-1), (x, z+1), (x+1, z+1)]

  for nx, nz in coords:
    if 0 <= nx < grid_width and 0 <= nz < grid_height:
      neighbors.append((nx, nz))
  return neighbors


def offset_to_cube(col, row):
  x = col - (row - (row & 1)) // 2
  z = row
  y = -x - z
  return x, y, z


def get_hex_distance(x1, z1, x2, z2):
  ax, ay, az = offset_to_cube(x1, z1)
  bx, by, bz = offset_to_cube(x2, z2)
  return max(abs(ax - bx), abs(ay - by), abs(az - bz))
