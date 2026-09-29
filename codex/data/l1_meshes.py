"""Neuroglancer legacy mesh files for the CNS and segment volumes of the L1 project.

Same idea as l1_skeletons.py: pure functions that encode meshes and write a folder that neuroglancer
can use as a segmentation source. The ids are the CATMAID volume ids.
"""

import json
import os
import struct

from codex.data.l1_skeletons import segment_properties_info, segmentation_volume_info


def encode_mesh_fragment(vertices, faces):
    """A mesh fragment: vertex count, float32 vertex positions, then uint32 vertex index triplets."""
    if any(not (0 <= i < len(vertices)) for face in faces for i in face):
        raise ValueError("Face refers to a vertex that does not exist")
    flat_positions = [c for v in vertices for c in v]
    flat_faces = [i for face in faces for i in face]
    return (
        struct.pack("<I", len(vertices))
        + struct.pack(f"<{len(flat_positions)}f", *flat_positions)
        + struct.pack(f"<{len(flat_faces)}I", *flat_faces)
    )


def _fragment_name(segment_id):
    return f"{segment_id}.mesh"


def mesh_manifest(segment_id):
    return {"fragments": [_fragment_name(segment_id)]}


def mesh_volume_info():
    return segmentation_volume_info(mesh="mesh", segment_properties="segment_properties")


def write_mesh_files(out_dir, meshes, names):
    """meshes maps a segment id to (vertices, faces). names maps ids to labels."""
    mesh_dir = os.path.join(out_dir, "mesh")
    os.makedirs(mesh_dir, exist_ok=True)
    os.makedirs(os.path.join(out_dir, "segment_properties"), exist_ok=True)
    for segment_id, (vertices, faces) in meshes.items():
        with open(os.path.join(mesh_dir, _fragment_name(segment_id)), "wb") as f:
            f.write(encode_mesh_fragment(vertices, faces))
        with open(os.path.join(mesh_dir, f"{segment_id}:0"), "w") as f:
            json.dump(mesh_manifest(segment_id), f)
    with open(os.path.join(out_dir, "info"), "w") as f:
        json.dump(mesh_volume_info(), f)
    with open(os.path.join(out_dir, "segment_properties", "info"), "w") as f:
        json.dump(
            segment_properties_info({i: names.get(i, str(i)) for i in meshes}), f
        )
