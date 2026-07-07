"""Render each task's chart to a PNG in assets/ (bypasses time-gating)."""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))

import plotly.io as pio
from data_prep import get_data
import tasks

# Redirect Kaleido's basemap fetch to local files (offline export only).
_TOPO = os.path.join(os.path.dirname(__file__), "data", "topojson") + os.sep
try:
    pio.kaleido.scope.topojson = f"file://{_TOPO}"
except Exception:
    pass

OUT = os.path.join(os.path.dirname(__file__), "assets")
os.makedirs(OUT, exist_ok=True)

apps = get_data()
specs = [
    (1, lambda: tasks.task1(apps)),
    (2, lambda: tasks.task2(apps, category="PHOTOGRAPHY")),
    (3, lambda: tasks.task3(apps)),
    (4, lambda: tasks.task4(apps)),
    (5, lambda: tasks.task5(apps)),
    (6, lambda: tasks.task6(apps)),
]
for i, fn in specs:
    fig, info = fn()
    fig.update_layout(width=1100, height=600)
    path = os.path.join(OUT, f"task{i}.png")
    fig.write_image(path, scale=2)
    print(f"task{i}.png  rows={info.get('rows')}")
print("done")
