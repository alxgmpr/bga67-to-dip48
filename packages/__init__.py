"""Package data modules: one per BGA package.  See the suite spec."""
import importlib
import string

# JEDEC ball naming skips I, O, Q, S, X, Z in some standards; each package
# declares the exact row letters it uses, in top-to-bottom order.
def ball_xy(module, ball):
    rows, n_cols = module.GRID
    row, col = ball[0], int(ball[1:])
    assert row in rows and 1 <= col <= n_cols, ball
    pitch = module.PITCH_MM
    x = (col - 1 - (n_cols - 1) / 2) * pitch
    y = (rows.index(row) - (len(rows) - 1) / 2) * pitch
    return x, y


def load(name):
    return importlib.import_module('packages.' + name)
