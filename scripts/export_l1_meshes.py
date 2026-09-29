#!/usr/bin/env python3
"""Fetch the CNS and segment volumes of the L1 project and write them as neuroglancer meshes.

Reads the surface meshes stored in CATMAID (a few hundred to a few thousand vertices each), never
EM image data. Same guarded connection as export_l1.py.

Setup: poetry install --with export
Run:   poetry run python scripts/export_l1_meshes.py --out-dir data/l1_meshes
"""

import argparse
import sys

from codex.data.brain_regions import REGIONS
from codex.data.l1_export import region_code
from codex.data.l1_meshes import write_mesh_files

from export_l1 import DEFAULT_SERVER, connect


def fetch_meshes():
    import pymaid

    meshes, names = {}, {}
    table = pymaid.get_volume()
    for volume_id, name in zip(table["id"], table["name"]):
        volume_id, name = int(volume_id), str(name)
        try:
            code = region_code(name)
        except ValueError as e:
            print(f"warning: skipping volume: {e}")
            continue
        if code is not None and REGIONS[code][0] != volume_id:
            print(f"warning: {code} has volume id {volume_id}, expected {REGIONS[code][0]}")
        volume = pymaid.get_volume(name)
        meshes[volume_id] = (volume.vertices.tolist(), volume.faces.tolist())
        names[volume_id] = code or "CNS"
    return meshes, names


def parse_args(argv):
    p = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    p.add_argument("--server", default=DEFAULT_SERVER)
    p.add_argument("--project-id", type=int, default=1)
    p.add_argument("--out-dir", default="data/l1_meshes")
    p.add_argument("--max-threads", type=int, default=4)
    return p.parse_args(argv)


def main(argv=None):
    args = parse_args(argv)
    connect(args)
    meshes, names = fetch_meshes()
    write_mesh_files(args.out_dir, meshes, names)
    print(f"wrote {len(meshes)} meshes to {args.out_dir}: {sorted(names.values())}")


if __name__ == "__main__":
    sys.exit(main())
