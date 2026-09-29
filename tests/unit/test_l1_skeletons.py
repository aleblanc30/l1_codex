import json
import os
import struct
import tempfile
from unittest import TestCase

from codex.data.l1_skeletons import (
    encode_skeleton,
    segment_properties_info,
    simplify_skeleton,
    skeleton_info,
    volume_info,
    write_info_files,
    write_skeleton_file,
    write_skeleton_files,
)


def chain(points):
    """Nodes 1..n in a chain from the root, given their positions."""
    ids = list(range(1, len(points) + 1))
    parents = [-1] + ids[:-1]
    return ids, parents, points, [10.0] * len(points)


class SimplifySkeletonTest(TestCase):
    def test_collinear_chain_keeps_only_its_ends(self):
        ids, parents, pos, radii = chain([(i * 100.0, 0.0, 0.0) for i in range(5)])
        vertices, edges, out_radii = simplify_skeleton(
            ids, parents, pos, radii, tolerance_nm=1.0
        )
        self.assertEqual([(0.0, 0.0, 0.0), (400.0, 0.0, 0.0)], vertices)
        self.assertEqual([(0, 1)], edges)
        self.assertEqual([10.0, 10.0], out_radii)

    def test_a_bend_larger_than_the_tolerance_is_kept(self):
        pos = [(0.0, 0.0, 0.0), (100.0, 0.0, 0.0), (200.0, 500.0, 0.0)]
        vertices, edges, _ = simplify_skeleton(*chain(pos), tolerance_nm=50.0)
        self.assertEqual(pos, vertices)
        self.assertEqual([(0, 1), (1, 2)], edges)

    def test_a_deviation_smaller_than_the_tolerance_is_dropped(self):
        pos = [(0.0, 0.0, 0.0), (100.0, 5.0, 0.0), (200.0, 0.0, 0.0)]
        vertices, _, _ = simplify_skeleton(*chain(pos), tolerance_nm=50.0)
        self.assertEqual([(0.0, 0.0, 0.0), (200.0, 0.0, 0.0)], vertices)

    def test_branch_points_and_leaves_are_always_kept(self):
        #   1 - 2 - 3 - 4      node 3 branches to 5
        #            \\ 5
        ids = [1, 2, 3, 4, 5]
        parents = [-1, 1, 2, 3, 3]
        pos = [(0.0, 0.0, 0.0), (100.0, 0.0, 0.0), (200.0, 0.0, 0.0), (300.0, 0.0, 0.0), (200.0, 100.0, 0.0)]
        vertices, edges, _ = simplify_skeleton(ids, parents, pos, [1.0] * 5, tolerance_nm=1.0)
        self.assertEqual(
            [(0.0, 0.0, 0.0), (200.0, 0.0, 0.0), (300.0, 0.0, 0.0), (200.0, 100.0, 0.0)],
            vertices,
        )
        self.assertEqual({(0, 1), (1, 2), (1, 3)}, set(edges))

    def test_zero_tolerance_keeps_every_node(self):
        pos = [(i * 100.0, 0.0, 0.0) for i in range(6)]
        vertices, edges, _ = simplify_skeleton(*chain(pos), tolerance_nm=0)
        self.assertEqual(pos, vertices)
        self.assertEqual([(i, i + 1) for i in range(5)], edges)

    def test_children_listed_before_their_parents(self):
        ids = [3, 2, 1]
        parents = [2, 1, -1]
        pos = [(200.0, 0.0, 0.0), (100.0, 0.0, 0.0), (0.0, 0.0, 0.0)]
        vertices, edges, _ = simplify_skeleton(ids, parents, pos, [1.0] * 3, tolerance_nm=0)
        self.assertEqual(3, len(vertices))
        self.assertEqual(2, len(edges))

    def test_a_node_with_a_missing_parent_starts_a_new_tree(self):
        ids = [1, 2, 3]
        parents = [-1, 1, 999]
        pos = [(0.0, 0.0, 0.0), (100.0, 0.0, 0.0), (5000.0, 0.0, 0.0)]
        vertices, edges, _ = simplify_skeleton(ids, parents, pos, [1.0] * 3, tolerance_nm=0)
        self.assertEqual(3, len(vertices))
        self.assertEqual([(0, 1)], edges)

    def test_single_node(self):
        vertices, edges, radii = simplify_skeleton([7], [-1], [(1.0, 2.0, 3.0)], [4.0], 10.0)
        self.assertEqual([(1.0, 2.0, 3.0)], vertices)
        self.assertEqual([], edges)
        self.assertEqual([4.0], radii)

    def test_empty_skeleton(self):
        self.assertEqual(([], [], []), simplify_skeleton([], [], [], [], 10.0))

    def test_radius_follows_the_kept_nodes(self):
        ids, parents, pos, _ = chain([(0.0, 0.0, 0.0), (100.0, 0.0, 0.0), (200.0, 400.0, 0.0)])
        _, _, radii = simplify_skeleton(ids, parents, pos, [1.0, 2.0, 3.0], tolerance_nm=10.0)
        self.assertEqual([1.0, 2.0, 3.0], radii)


class EncodeSkeletonTest(TestCase):
    def test_binary_layout_follows_the_specification(self):
        vertices = [(1.0, 2.0, 3.0), (4.0, 5.0, 6.0), (7.0, 8.0, 9.0)]
        edges = [(0, 1), (1, 2)]
        radii = [0.5, 1.5, 2.5]
        data = encode_skeleton(vertices, edges, radii)
        self.assertEqual(8 + 3 * 12 + 2 * 8 + 3 * 4, len(data))
        num_vertices, num_edges = struct.unpack_from("<II", data, 0)
        self.assertEqual((3, 2), (num_vertices, num_edges))
        self.assertEqual(
            (1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0, 9.0),
            struct.unpack_from("<9f", data, 8),
        )
        self.assertEqual((0, 1, 1, 2), struct.unpack_from("<4I", data, 8 + 36))
        self.assertEqual((0.5, 1.5, 2.5), struct.unpack_from("<3f", data, 8 + 36 + 16))

    def test_no_edges(self):
        data = encode_skeleton([(1.0, 2.0, 3.0)], [], [9.0])
        self.assertEqual((1, 0), struct.unpack_from("<II", data, 0))
        self.assertEqual(8 + 12 + 4, len(data))

    def test_radius_count_must_match_vertices(self):
        with self.assertRaises(ValueError):
            encode_skeleton([(0.0, 0.0, 0.0)], [], [1.0, 2.0])

    def test_edge_indices_must_be_in_range(self):
        with self.assertRaises(ValueError):
            encode_skeleton([(0.0, 0.0, 0.0)], [(0, 1)], [1.0])


class InfoFilesTest(TestCase):
    def test_skeleton_info(self):
        info = skeleton_info()
        self.assertEqual("neuroglancer_skeletons", info["@type"])
        self.assertEqual(12, len(info["transform"]))
        self.assertEqual(
            [{"id": "radius", "data_type": "float32", "num_components": 1}],
            info["vertex_attributes"],
        )
        # segment properties are declared once, by the volume that the skeletons belong to
        self.assertNotIn("segment_properties", info)

    def test_volume_info_points_at_the_skeletons(self):
        info = volume_info()
        self.assertEqual("neuroglancer_multiscale_volume", info["@type"])
        self.assertEqual("segmentation", info["type"])
        self.assertEqual("uint64", info["data_type"])
        self.assertEqual("skeletons", info["skeletons"])
        self.assertEqual("segment_properties", info["segment_properties"])
        self.assertEqual(1, len(info["scales"]))

    def test_segment_properties_label_every_id(self):
        info = segment_properties_info({29: "KC #0", 30: "v'ada"})
        self.assertEqual("neuroglancer_segment_properties", info["@type"])
        self.assertEqual(["29", "30"], info["inline"]["ids"])
        (prop,) = info["inline"]["properties"]
        self.assertEqual({"id": "label", "type": "label"}, {k: prop[k] for k in ("id", "type")})
        self.assertEqual(["KC #0", "v'ada"], prop["values"])


class WriteSkeletonFilesTest(TestCase):
    def test_writes_the_directory_tree(self):
        skeletons = {
            29: ([(0.0, 0.0, 0.0), (10.0, 0.0, 0.0)], [(0, 1)], [1.0, 2.0]),
            30: ([(5.0, 5.0, 5.0)], [], [3.0]),
        }
        with tempfile.TemporaryDirectory() as out:
            write_skeleton_files(out, skeletons, {29: "KC #0", 30: "v'ada"})
            self.assertEqual({"info", "skeletons", "segment_properties"}, set(os.listdir(out)))
            self.assertEqual({"info", "29", "30"}, set(os.listdir(f"{out}/skeletons")))
            with open(f"{out}/info") as f:
                self.assertEqual("segmentation", json.load(f)["type"])
            with open(f"{out}/skeletons/info") as f:
                self.assertEqual("neuroglancer_skeletons", json.load(f)["@type"])
            with open(f"{out}/segment_properties/info") as f:
                self.assertEqual(["29", "30"], json.load(f)["inline"]["ids"])
            with open(f"{out}/skeletons/29", "rb") as f:
                self.assertEqual((2, 1), struct.unpack("<II", f.read(8)))

    def test_ids_without_a_name_get_their_id_as_label(self):
        with tempfile.TemporaryDirectory() as out:
            write_skeleton_files(out, {5: ([(0.0, 0.0, 0.0)], [], [1.0])}, {})
            with open(f"{out}/segment_properties/info") as f:
                self.assertEqual(["5"], json.load(f)["inline"]["properties"][0]["values"])


class StreamingWritersTest(TestCase):
    def test_a_skeleton_file_is_written_whole_and_leaves_no_temporary_file(self):
        with tempfile.TemporaryDirectory() as out:
            write_skeleton_file(out, 29, [(0.0, 0.0, 0.0), (1.0, 0.0, 0.0)], [(0, 1)], [1.0, 1.0])
            self.assertEqual(["29"], os.listdir(f"{out}/skeletons"))
            with open(f"{out}/skeletons/29", "rb") as f:
                self.assertEqual((2, 1), struct.unpack("<II", f.read(8)))

    def test_info_files_are_written_without_any_skeleton(self):
        with tempfile.TemporaryDirectory() as out:
            write_info_files(out, {29: "KC #0"})
            with open(f"{out}/info") as f:
                self.assertEqual("skeletons", json.load(f)["skeletons"])
            with open(f"{out}/skeletons/info") as f:
                self.assertEqual("neuroglancer_skeletons", json.load(f)["@type"])
            with open(f"{out}/segment_properties/info") as f:
                self.assertEqual(["KC #0"], json.load(f)["inline"]["properties"][0]["values"])
