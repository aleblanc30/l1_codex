#!/usr/bin/env python3
"""Fetch the L1 skeletons from CATMAID and write them as neuroglancer precomputed skeletons.

Reads skeleton nodes only, never EM image data (same guarded, throttled connection as
export_l1.py). Each skeleton is simplified (see --tolerance-nm) and written as soon as it is
fetched, and files that already exist are skipped, so an interrupted run resumes.

Setup: poetry install --with export
Run:   poetry run python scripts/export_l1_skeletons.py --out-dir static/data/l1_skeletons

The output folder is a neuroglancer segmentation source: serve it from a static host that sends
CORS headers and point a segmentation layer at it.
"""

import argparse
import json
import os
import sys
import time

from codex.data.l1_export import chunked
from codex.data.l1_skeletons import (
    simplify_skeleton,
    write_info_files,
    write_skeleton_file,
)

from export_l1 import DEFAULT_SERVER, Cache, connect, list_skeleton_ids

NAMES_FILE = "names.json"


def fetch_batch(batch, tolerance_nm):
    """{skeleton id: (vertices, edges, radii, name, original node count)} for the skeletons of a batch."""
    import pymaid

    fetched = pymaid.get_neuron(
        batch, with_connectors=False, with_tags=False, raise_missing=False
    )
    if isinstance(fetched, pymaid.CatmaidNeuron):
        neurons = [fetched]
    else:
        neurons = list(fetched)
    result = {}
    for neuron in neurons:
        nodes = neuron.nodes
        vertices, edges, radii = simplify_skeleton(
            nodes.node_id.tolist(),
            nodes.parent_id.tolist(),
            nodes[["x", "y", "z"]].values.tolist(),
            [max(r, 0.0) for r in nodes.radius.tolist()],
            tolerance_nm,
        )
        result[int(neuron.id)] = (
            vertices,
            edges,
            radii,
            str(neuron.neuron_name),
            len(nodes),
        )
    return result


def load_names(out_dir):
    path = os.path.join(out_dir, NAMES_FILE)
    if not os.path.exists(path):
        return {}
    with open(path) as f:
        return {int(k): v for k, v in json.load(f).items()}


def save_names(out_dir, names):
    with open(os.path.join(out_dir, NAMES_FILE + ".tmp"), "w") as f:
        json.dump(names, f)
    os.replace(
        os.path.join(out_dir, NAMES_FILE + ".tmp"), os.path.join(out_dir, NAMES_FILE)
    )


def parse_args(argv):
    p = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    p.add_argument("--server", default=DEFAULT_SERVER)
    p.add_argument("--project-id", type=int, default=1)
    p.add_argument("--out-dir", default="static/data/l1_skeletons")
    p.add_argument("--cache-dir", default="static/l1_export_cache")
    p.add_argument("--batch-size", type=int, default=25)
    p.add_argument("--max-threads", type=int, default=4)
    p.add_argument(
        "--delay", type=float, default=1.0, help="seconds between request batches"
    )
    p.add_argument(
        "--tolerance-nm",
        type=float,
        default=200.0,
        help="largest deviation from the original path (0 keeps every node)",
    )
    p.add_argument("--limit", type=int, help="only the first N skeletons (trial run)")
    return p.parse_args(argv)


def main(argv=None):
    args = parse_args(argv)
    os.makedirs(args.out_dir, exist_ok=True)
    cache = Cache(args.cache_dir)
    remote = connect(args)

    ids = cache.get("skeleton_ids", lambda: list_skeleton_ids(remote, args.project_id))
    if args.limit:
        ids = ids[: args.limit]
    names = load_names(args.out_dir)
    todo = [
        i
        for i in ids
        if not os.path.exists(os.path.join(args.out_dir, "skeletons", str(i)))
    ]
    print(f"{len(ids)} skeletons, {len(todo)} still to fetch")

    original_nodes = kept_nodes = 0
    for done, batch in enumerate(chunked(todo, args.batch_size), start=1):
        for skeleton_id, (vertices, edges, radii, name, count) in fetch_batch(
            batch, args.tolerance_nm
        ).items():
            write_skeleton_file(args.out_dir, skeleton_id, vertices, edges, radii)
            names[skeleton_id] = name
            original_nodes += count
            kept_nodes += len(vertices)
        save_names(args.out_dir, names)
        print(f"skeletons {min(done * args.batch_size, len(todo))}/{len(todo)}", flush=True)
        time.sleep(args.delay)

    write_info_files(args.out_dir, {i: names.get(i, str(i)) for i in ids})
    size = sum(
        os.path.getsize(os.path.join(args.out_dir, "skeletons", f))
        for f in os.listdir(os.path.join(args.out_dir, "skeletons"))
    )
    print(
        json.dumps(
            {
                "skeletons_written": len(os.listdir(os.path.join(args.out_dir, "skeletons"))) - 1,
                "nodes_fetched_this_run": original_nodes,
                "nodes_kept_this_run": kept_nodes,
                "total_bytes": size,
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    sys.exit(main())
