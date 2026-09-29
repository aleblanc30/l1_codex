"""Neuroglancer precomputed skeleton files for the L1 neurons.

Pure functions: simplification of a skeleton, encoding in neuroglancer's binary format, and the
small JSON info files that make the skeletons usable as a segmentation source. Neuroglancer reads
skeletons of a segmentation layer from the "skeletons" folder of its volume, one file per segment id.
"""

import json
import math
import os
import struct


def _distance_to_segment(p, a, b):
    ab = [b[i] - a[i] for i in range(3)]
    ap = [p[i] - a[i] for i in range(3)]
    length_sq = sum(c * c for c in ab)
    if length_sq == 0:
        return math.sqrt(sum(c * c for c in ap))
    t = max(0.0, min(1.0, sum(ap[i] * ab[i] for i in range(3)) / length_sq))
    return math.sqrt(sum((ap[i] - t * ab[i]) ** 2 for i in range(3)))


def _mark_significant_nodes(chain, positions, tolerance, keep):
    """Douglas-Peucker along a chain of node indices: mark the nodes that deviate by more than tolerance."""
    stack = [(0, len(chain) - 1)]
    while stack:
        lo, hi = stack.pop()
        if hi - lo < 2:
            continue
        a, b = positions[chain[lo]], positions[chain[hi]]
        farthest, farthest_distance = -1, -1.0
        for j in range(lo + 1, hi):
            distance = _distance_to_segment(positions[chain[j]], a, b)
            if distance > farthest_distance:
                farthest, farthest_distance = j, distance
        if farthest_distance > tolerance:
            keep[chain[farthest]] = True
            stack.append((lo, farthest))
            stack.append((farthest, hi))


def simplify_skeleton(node_ids, parent_ids, positions, radii, tolerance_nm):
    """Reduce a skeleton to its roots, branch points, leaves and the nodes needed to stay within
    tolerance_nm of the original path.

    Returns (vertices, edges, radii): vertices in the order of the input nodes, and edges as
    (parent index, child index) pairs into the vertices. A node whose parent is not in the
    skeleton starts a new tree.
    """
    n = len(node_ids)
    if n == 0:
        return [], [], []
    index = {node_id: i for i, node_id in enumerate(node_ids)}
    parent = [index.get(p, -1) if p is not None else -1 for p in parent_ids]
    positions = [tuple(float(c) for c in p) for p in positions]

    if tolerance_nm and tolerance_nm > 0:
        child_count = [0] * n
        for p in parent:
            if p >= 0:
                child_count[p] += 1
        keep = [parent[i] < 0 or child_count[i] != 1 for i in range(n)]
        for i in range(n):
            if not (keep[i] and parent[i] >= 0):
                continue
            chain, current = [i], parent[i]
            while not keep[current] and len(chain) <= n:
                chain.append(current)
                current = parent[current]
            chain.append(current)
            if len(chain) > 2:
                _mark_significant_nodes(chain, positions, tolerance_nm, keep)
    else:
        keep = [True] * n

    new_index = {}
    for i in range(n):
        if keep[i]:
            new_index[i] = len(new_index)
    vertices, out_radii, edges = [], [], []
    for i, j in new_index.items():
        vertices.append(positions[i])
        out_radii.append(float(radii[i]))
        ancestor = parent[i]
        while ancestor >= 0 and not keep[ancestor]:
            ancestor = parent[ancestor]
        if ancestor >= 0:
            edges.append((new_index[ancestor], j))
    return vertices, edges, out_radii


def encode_skeleton(vertices, edges, radii):
    """A skeleton file: vertex and edge counts, float32 positions, uint32 edge pairs, float32 radius."""
    if len(radii) != len(vertices):
        raise ValueError("There must be one radius per vertex")
    if any(not (0 <= a < len(vertices) and 0 <= b < len(vertices)) for a, b in edges):
        raise ValueError("Edge refers to a vertex that does not exist")
    flat_positions = [c for v in vertices for c in v]
    flat_edges = [i for e in edges for i in e]
    return (
        struct.pack("<II", len(vertices), len(edges))
        + struct.pack(f"<{len(flat_positions)}f", *flat_positions)
        + struct.pack(f"<{len(flat_edges)}I", *flat_edges)
        + struct.pack(f"<{len(radii)}f", *radii)
    )


def skeleton_info():
    return {
        "@type": "neuroglancer_skeletons",
        "transform": [1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0],
        "vertex_attributes": [
            {"id": "radius", "data_type": "float32", "num_components": 1}
        ],
    }


def volume_info():
    """A segmentation volume that only carries skeletons. Its single chunk is never read in a 3D view."""
    return {
        "@type": "neuroglancer_multiscale_volume",
        "type": "segmentation",
        "data_type": "uint64",
        "num_channels": 1,
        "scales": [
            {
                "key": "1",
                "size": [1, 1, 1],
                "resolution": [1, 1, 1],
                "chunk_sizes": [[1, 1, 1]],
                "encoding": "raw",
                "voxel_offset": [0, 0, 0],
            }
        ],
        "skeletons": "skeletons",
        "segment_properties": "segment_properties",
    }


def segment_properties_info(names):
    ids = sorted(names)
    return {
        "@type": "neuroglancer_segment_properties",
        "inline": {
            "ids": [str(i) for i in ids],
            "properties": [
                {"id": "label", "type": "label", "values": [names[i] for i in ids]}
            ],
        },
    }


def write_skeleton_file(out_dir, segment_id, vertices, edges, radii):
    folder = os.path.join(out_dir, "skeletons")
    os.makedirs(folder, exist_ok=True)
    path = os.path.join(folder, str(segment_id))
    with open(path + ".tmp", "wb") as f:
        f.write(encode_skeleton(vertices, edges, radii))
    os.replace(path + ".tmp", path)


def write_info_files(out_dir, names):
    """The volume, skeleton and segment properties info files. names maps a segment id to its label."""
    os.makedirs(os.path.join(out_dir, "skeletons"), exist_ok=True)
    os.makedirs(os.path.join(out_dir, "segment_properties"), exist_ok=True)

    def write_json(path, content):
        with open(os.path.join(out_dir, path), "w") as f:
            json.dump(content, f)

    write_json("info", volume_info())
    write_json("skeletons/info", skeleton_info())
    write_json("segment_properties/info", segment_properties_info(names))


def write_skeleton_files(out_dir, skeletons, names):
    """Write the volume, its skeleton files and its segment properties under out_dir.

    skeletons maps a segment id to (vertices, edges, radii). names maps ids to labels, and an id
    without a name is labelled with itself.
    """
    for segment_id, (vertices, edges, radii) in skeletons.items():
        write_skeleton_file(out_dir, segment_id, vertices, edges, radii)
    write_info_files(out_dir, {i: names.get(i, str(i)) for i in skeletons})
