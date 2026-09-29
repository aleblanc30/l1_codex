"""Links to the neuroglancer viewer for L1 cells and regions.

Neuroglancer is a web application that runs in the browser. A link carries the description of the
scene after "#!" and neuroglancer loads the data it names straight from the URLs in that
description. The scene here is 3D only: skeletons of the selected cells inside the outline of the
nervous system (there is no EM image layer, because neuroglancer cannot read CATMAID tile stacks).

The skeleton and mesh files are served from this repository (data/l1_skeletons and data/l1_meshes,
see scripts/export_l1_skeletons.py and scripts/export_l1_meshes.py). Set CODEX_DATA_REF to use another
branch or tag, CODEX_DATA_HOST_URL for another host, and CODEX_NEUROGLANCER_URL for another
neuroglancer deployment.
"""

import json
import os
import random
import urllib.parse

from codex.data.brain_regions import COLORS, REGIONS

NEUROGLANCER_URL = os.environ.get(
    "CODEX_NEUROGLANCER_URL", "https://neuroglancer-demo.appspot.com"
).rstrip("/")
_DATA_HOST_URL = os.environ.get(
    "CODEX_DATA_HOST_URL",
    "https://raw.githubusercontent.com/aleblanc30/l1_codex/"
    + os.environ.get("CODEX_DATA_REF", "main"),
).rstrip("/")
SKELETONS_URL = f"{_DATA_HOST_URL}/data/l1_skeletons"
MESHES_URL = f"{_DATA_HOST_URL}/data/l1_meshes"

# The CATMAID volume that outlines the whole CNS, and the centre of its bounding box in nanometres
CNS_VOLUME_ID = 22
CNS_CENTER_NM = (53018, 60486, 126547)

_CNS_COLOR = "#b5b5b5"

# The CNS is about 240 micrometers long along z. Neuroglancer looks down the z axis by default, which
# shows the brain end-on, so the view is rotated by 90 degrees around x to show the whole CNS from the side.
_SIDE_VIEW_ORIENTATION = [0.7071067811865476, 0, 0, 0.7071067811865476]
_PROJECTION_SCALE = 300000


def _url(state):
    return f"{NEUROGLANCER_URL}/#!{urllib.parse.quote(json.dumps(state, separators=(',', ':')))}"


def _cns_layer(alpha):
    return {
        "type": "segmentation",
        "source": f"precomputed://{MESHES_URL}",
        "name": "CNS",
        "segments": [str(CNS_VOLUME_ID)],
        "segmentColors": {str(CNS_VOLUME_ID): _CNS_COLOR},
        "objectAlpha": alpha,
    }


def _state(layers, selected_layer, position):
    return {
        "dimensions": {axis: [1e-9, "m"] for axis in "xyz"},
        "position": list(position or CNS_CENTER_NM),
        "layers": layers,
        "layout": "3d",
        "projectionOrientation": _SIDE_VIEW_ORIENTATION,
        "projectionScale": _PROJECTION_SCALE,
        "showSlices": False,
        "showAxisLines": False,
        "showDefaultAnnotations": False,
        "perspectiveViewBackgroundColor": "#ffffff",
        "selectedLayer": selected_layer,
    }


def url_for_root_ids(root_ids, show_side_panel=None, position=None):
    if show_side_panel is None:
        show_side_panel = len(root_ids) > 1
    neurons = {
        "type": "segmentation",
        "source": f"precomputed://{SKELETONS_URL}",
        "name": "neurons",
        "tab": "segments",
        # BEWARE: JSON can't handle big ints
        "segments": [str(rid) for rid in root_ids],
        "skeletonRendering": {"mode2d": "lines_and_points", "mode3d": "lines", "lineWidth3d": 2},
    }
    state = _state(
        [_cns_layer(alpha=0.05), neurons],
        {"layer": "neurons", "visible": bool(show_side_panel)},
        position,
    )
    return _url(state)


def url_for_random_sample(root_ids, sample_size=50):
    # make the random subset selections deterministic across executions
    rng = random.Random(420)
    if len(root_ids) > sample_size:
        # make a sorted sample to preserve original order
        root_ids = [
            root_ids[i] for i in sorted(rng.sample(range(len(root_ids)), sample_size))
        ]
    return url_for_root_ids(root_ids)


def url_for_neuropils(segment_ids=None):
    if not segment_ids:
        segment_ids = [segment_id for segment_id, _ in REGIONS.values()]
    # exclude "dummy" regions, e.g. unassigned, which by convention have negative ids
    selected = {s for s in segment_ids if s >= 0}
    regions = {
        "type": "segmentation",
        "source": f"precomputed://{MESHES_URL}",
        "name": "regions",
        "tab": "segments",
        "segments": [str(s) for s in segment_ids if s in selected],
        "segmentColors": {
            str(segment_id): COLORS[key]
            for key, (segment_id, _) in REGIONS.items()
            if segment_id in selected
        },
        "objectAlpha": 0.7,
    }
    state = _state(
        [_cns_layer(alpha=0.03), regions],
        {"layer": "regions", "visible": False},
        None,
    )
    return _url(state)
