#!/usr/bin/env python3
"""Export the L1 larval CATMAID project to Codex data files.

Reads skeletons, annotations, connectors and region volumes through pymaid, never any EM
image data, and writes gzipped CSVs (see codex/data/l1_export.py for the schema).
Requests are throttled and every intermediate result is cached on disk, so an interrupted
run resumes where it stopped and a re-run does not hit the server again.

Setup: poetry install --with export
Run:   poetry run python scripts/export_l1.py --out-dir static/data/l1_export

The 'papers' annotation tree supplies publications and 'MB nomenclature' supplies cell types
by default. Use --limit for a trial run; partners outside the trial set then count as
orphaned sites, so trial output is only good for checking the pipeline.
"""

import argparse
import csv
import gzip
import json
import os
import pickle
import sys
import time
from datetime import datetime, timezone

from codex.data.l1_export import (
    L1_EXPORT_SCHEMA,
    aggregate_ids_in,
    assign_regions,
    build_connection_rows,
    build_export_tables,
    build_mirror_twins,
    chunked,
    is_image_endpoint,
    region_code,
)

DEFAULT_SERVER = "https://l1em.catmaid.virtualflybrain.org"
# Bump when the shape of cached results changes, so stale caches are not reused.
CACHE_VERSION = 2


class Cache:
    def __init__(self, directory):
        self.directory = directory
        os.makedirs(directory, exist_ok=True)

    def _path(self, key):
        return os.path.join(self.directory, f"v{CACHE_VERSION}_{key}.pkl")

    def has(self, key):
        return os.path.exists(self._path(key))

    def get(self, key, compute):
        path = self._path(key)
        if os.path.exists(path):
            with open(path, "rb") as f:
                return pickle.load(f)
        value = compute()
        with open(path + ".tmp", "wb") as f:
            pickle.dump(value, f)
        os.replace(path + ".tmp", path)
        return value


def connect(args):
    import pymaid

    remote = pymaid.CatmaidInstance(
        args.server,
        api_token=os.environ.get("CATMAID_API_TOKEN"),
        project_id=args.project_id,
        max_threads=args.max_threads,
    )
    pymaid.set_pbars(hide=True)
    original_fetch = remote.fetch

    def guarded_fetch(url, *fetch_args, **fetch_kwargs):
        for u in [url] if isinstance(url, str) else url:
            if is_image_endpoint(u):
                raise RuntimeError(f"Refusing to request image-related endpoint: {u}")
        return original_fetch(url, *fetch_args, **fetch_kwargs)

    remote.fetch = guarded_fetch
    return remote


def list_skeleton_ids(remote, project_id):
    url = remote.make_url(project_id, "skeletons/")
    return sorted(int(s) for s in remote.fetch(url))


def fetch_annotations(ids, cache):
    import pymaid

    annotations = {}
    for batch in chunked(ids, 1000):
        result = cache.get(
            f"annotations_{batch[0]}_{len(batch)}",
            lambda b=batch: pymaid.get_annotations(b),
        )
        annotations.update({int(k): sorted(v) for k, v in result.items()})
    return {skeleton: annotations.get(skeleton, []) for skeleton in ids}


def sub_annotation_names(parent):
    import pymaid

    result = pymaid.get_annotated(
        parent, include_sub_annotations=True, raise_not_found=False
    )
    if len(result) == 0:
        raise RuntimeError(f"Annotation not found: {parent}")
    return set(result[result["type"] == "annotation"]["name"])


def load_region_volumes():
    import pymaid

    volumes = {}
    for name in pymaid.get_volume()["name"]:
        try:
            code = region_code(str(name))
        except ValueError as e:
            print(f"warning: skipping volume: {e}")
            continue
        if code is not None:
            volumes[code] = pymaid.get_volume(str(name))
    return volumes


def regions_for_points(points, volumes):
    import navis
    import numpy as np

    points = np.asarray(points, dtype=float).reshape(-1, 3)
    if len(points) == 0:
        return []
    containment = {
        code: [bool(v) for v in navis.in_volume(points, volume)]
        for code, volume in volumes.items()
    }
    return assign_regions(len(points), containment)


def summarize_neuron(neuron, volumes):
    import numpy as np

    nodes = neuron.nodes
    soma_ids = [] if neuron.soma is None else list(np.atleast_1d(neuron.soma))
    if soma_ids:
        anchor = nodes[nodes.node_id.isin(soma_ids)]
    else:
        anchor = nodes[nodes.type == "root"]
    if anchor.empty:
        anchor = nodes.head(1)
    position = tuple(float(v) for v in anchor.iloc[0][["x", "y", "z"]])

    connectors = neuron.connectors
    connectors = connectors[connectors.type.isin([0, 1])]
    connectors = connectors.drop_duplicates("connector_id")
    connector_regions = dict(
        zip(
            (int(c) for c in connectors.connector_id),
            regions_for_points(connectors[["x", "y", "z"]].values, volumes),
        )
    )
    summary = {
        "skeleton_id": int(neuron.id),
        "name": str(neuron.neuron_name),
        "node_count": int(neuron.n_nodes),
        "cable_length_nm": float(neuron.cable_length),
        "has_soma": bool(soma_ids),
        "position_xyz": position,
        "position_region": regions_for_points([position], volumes)[0],
    }
    return summary, connector_regions


def fetch_neuron_batch(batch, volumes):
    import pymaid

    fetched = pymaid.get_neuron(batch, raise_missing=False)
    if isinstance(fetched, pymaid.CatmaidNeuron):
        neurons = [fetched]
    else:
        neurons = list(fetched)
    results = [summarize_neuron(neuron, volumes) for neuron in neurons]
    return results, sorted(set(batch) - {s["skeleton_id"] for s, _ in results})


def fetch_neurons(ids, batch_size, delay, cache, volumes):
    summaries, connector_regions, missing = [], {}, []
    for i, batch in enumerate(chunked(ids, batch_size)):
        cached = cache.has(f"neurons_{batch[0]}_{len(batch)}")
        results, batch_missing = cache.get(
            f"neurons_{batch[0]}_{len(batch)}",
            lambda b=batch: fetch_neuron_batch(b, volumes),
        )
        for summary, regions in results:
            summaries.append(summary)
            connector_regions.update(regions)
        missing.extend(batch_missing)
        done = min((i + 1) * batch_size, len(ids))
        print(f"neurons {done}/{len(ids)}", flush=True)
        if not cached:
            time.sleep(delay)
    return summaries, connector_regions, missing


def fetch_connector_details(connector_ids, cache, delay, chunk_size=5000):
    import pymaid

    def details(chunk):
        table = pymaid.get_connector_details(chunk)
        rows = []
        for r in table.itertuples():
            pre = r.presynaptic_to
            posts = r.postsynaptic_to
            rows.append(
                {
                    "connector_id": int(r.connector_id),
                    "pre": None if pre is None or pre != pre else int(pre),
                    "posts": [int(p) for p in posts]
                    if isinstance(posts, (list, tuple))
                    else [],
                }
            )
        return rows

    connectors = []
    for chunk in chunked(sorted(connector_ids), chunk_size):
        connectors.extend(
            cache.get(f"connectors_{chunk[0]}_{len(chunk)}", lambda c=chunk: details(c))
        )
        time.sleep(delay)
    return connectors


def write_tables(tables, out_dir):
    os.makedirs(out_dir, exist_ok=True)
    for name, rows in tables.items():
        with gzip.open(os.path.join(out_dir, name), "wt", newline="") as f:
            csv.writer(f).writerows(rows)


def parse_args(argv):
    p = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    p.add_argument("--server", default=DEFAULT_SERVER)
    p.add_argument("--project-id", type=int, default=1)
    p.add_argument("--out-dir", default="static/data/l1_export")
    p.add_argument("--cache-dir", default="static/l1_export_cache")
    p.add_argument("--batch-size", type=int, default=50)
    p.add_argument("--max-threads", type=int, default=4)
    p.add_argument(
        "--delay", type=float, default=1.0, help="seconds between request batches"
    )
    p.add_argument("--limit", type=int, help="only the first N skeletons (trial run)")
    p.add_argument("--paper-parent", default="papers")
    p.add_argument(
        "--cell-type-parent", action="append", default=None, help="repeatable"
    )
    return p.parse_args(argv)


def main(argv=None):
    args = parse_args(argv)
    cell_type_parents = args.cell_type_parent or ["MB nomenclature"]
    cache = Cache(args.cache_dir)
    remote = connect(args)

    ids = cache.get("skeleton_ids", lambda: list_skeleton_ids(remote, args.project_id))
    if args.limit:
        ids = ids[: args.limit]
    print(f"{len(ids)} skeletons")

    annotations = fetch_annotations(ids, cache)
    paper_names = cache.get(
        "paper_names", lambda: sub_annotation_names(args.paper_parent)
    )
    cell_type_names = cache.get(
        "cell_type_names",
        lambda: set().union(*(sub_annotation_names(p) for p in cell_type_parents)),
    )
    volumes = load_region_volumes()
    print(f"{len(volumes)} region volumes")

    summaries, connector_regions, missing = fetch_neurons(
        ids, args.batch_size, args.delay, cache, volumes
    )
    if missing:
        print(f"warning: {len(missing)} skeletons could not be fetched: {missing[:10]}")
    real_ids = {s["skeleton_id"] for s in summaries}

    connectors = fetch_connector_details(connector_regions, cache, args.delay)
    rows, orphan_stats, skipped = build_connection_rows(
        connectors, connector_regions, real_ids
    )
    tables = build_export_tables(
        summaries=summaries,
        annotations=annotations,
        paper_names=paper_names,
        cell_type_names=cell_type_names,
        connection_rows=rows,
        orphan_stats=orphan_stats,
        twins=build_mirror_twins({s: annotations[s] for s in real_ids}),
    )
    write_tables(tables, args.out_dir)

    manifest = {
        "exported_at": datetime.now(timezone.utc).isoformat(),
        "server": args.server,
        "project_id": args.project_id,
        "trial_limit": args.limit,
        "skeletons": len(summaries),
        "connection_rows": len(rows),
        "orphan_aggregates": len(aggregate_ids_in(rows)),
        "skipped_synapse_links": skipped,
        "files": {name: len(rows) - 1 for name, rows in tables.items()},
        "schema": L1_EXPORT_SCHEMA,
    }
    with open(os.path.join(args.out_dir, "manifest.json"), "w") as f:
        json.dump(manifest, f, indent=2)
    print(json.dumps({k: v for k, v in manifest.items() if k != "schema"}, indent=2))


if __name__ == "__main__":
    sys.exit(main())
