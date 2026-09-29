import json
import os
import struct
import tempfile
from unittest import TestCase

from codex.data.l1_meshes import (
    encode_mesh_fragment,
    mesh_manifest,
    mesh_volume_info,
    write_mesh_files,
)
from codex.data.l1_skeletons import volume_info

TRIANGLE = ([(0.0, 0.0, 0.0), (10.0, 0.0, 0.0), (0.0, 10.0, 0.0)], [(0, 1, 2)])


class EncodeMeshFragmentTest(TestCase):
    def test_binary_layout_follows_the_specification(self):
        vertices, faces = TRIANGLE
        data = encode_mesh_fragment(vertices, faces)
        self.assertEqual(4 + 3 * 12 + 12, len(data))
        self.assertEqual(3, struct.unpack_from("<I", data, 0)[0])
        self.assertEqual(
            (0.0, 0.0, 0.0, 10.0, 0.0, 0.0, 0.0, 10.0, 0.0),
            struct.unpack_from("<9f", data, 4),
        )
        self.assertEqual((0, 1, 2), struct.unpack_from("<3I", data, 4 + 36))

    def test_a_mesh_without_faces_is_just_its_vertices(self):
        data = encode_mesh_fragment([(1.0, 2.0, 3.0)], [])
        self.assertEqual(4 + 12, len(data))

    def test_face_indices_must_be_in_range(self):
        with self.assertRaises(ValueError):
            encode_mesh_fragment([(0.0, 0.0, 0.0)], [(0, 0, 1)])


class InfoTest(TestCase):
    def test_manifest_lists_the_fragment(self):
        self.assertEqual({"fragments": ["22.mesh"]}, mesh_manifest(22))

    def test_volume_info_declares_meshes_and_no_skeletons(self):
        info = mesh_volume_info()
        self.assertEqual("segmentation", info["type"])
        self.assertEqual("mesh", info["mesh"])
        self.assertEqual("segment_properties", info["segment_properties"])
        self.assertNotIn("skeletons", info)

    def test_volume_shares_the_dummy_scale_with_the_skeleton_volume(self):
        self.assertEqual(volume_info()["scales"], mesh_volume_info()["scales"])


class WriteMeshFilesTest(TestCase):
    def test_writes_manifests_fragments_and_info(self):
        meshes = {22: TRIANGLE, 61: TRIANGLE}
        with tempfile.TemporaryDirectory() as out:
            write_mesh_files(out, meshes, {22: "CNS", 61: "BRAIN_L"})
            self.assertEqual({"info", "mesh", "segment_properties"}, set(os.listdir(out)))
            self.assertEqual(
                {"22:0", "22.mesh", "61:0", "61.mesh"}, set(os.listdir(f"{out}/mesh"))
            )
            with open(f"{out}/mesh/22:0") as f:
                self.assertEqual({"fragments": ["22.mesh"]}, json.load(f))
            with open(f"{out}/mesh/61.mesh", "rb") as f:
                self.assertEqual(3, struct.unpack("<I", f.read(4))[0])
            with open(f"{out}/segment_properties/info") as f:
                info = json.load(f)
            self.assertEqual(["22", "61"], info["inline"]["ids"])
            self.assertEqual(["CNS", "BRAIN_L"], info["inline"]["properties"][0]["values"])
            with open(f"{out}/info") as f:
                self.assertEqual("mesh", json.load(f)["mesh"])
