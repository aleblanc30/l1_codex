import json
import random
import urllib.parse
from unittest import TestCase

from codex.data.brain_regions import COLORS, REGIONS
from codex.utils import nglui


def state_of(url):
    return json.loads(urllib.parse.unquote(url.split("#!", 1)[1]))


def layers_by_name(state):
    return {layer["name"]: layer for layer in state["layers"]}


class DefaultsTest(TestCase):
    def test_default_hosts(self):
        self.assertEqual("https://neuroglancer-demo.appspot.com", nglui.NEUROGLANCER_URL)
        base = "https://raw.githubusercontent.com/aleblanc30/l1_codex/"
        self.assertTrue(nglui.SKELETONS_URL.startswith(base))
        self.assertTrue(nglui.SKELETONS_URL.endswith("/data/l1_skeletons"))
        self.assertTrue(nglui.MESHES_URL.startswith(base))
        self.assertTrue(nglui.MESHES_URL.endswith("/data/l1_meshes"))

    def test_cns_volume(self):
        self.assertEqual(22, nglui.CNS_VOLUME_ID)
        self.assertEqual(3, len(nglui.CNS_CENTER_NM))


class UrlForRootIdsTest(TestCase):
    def setUp(self):
        self.url = nglui.url_for_root_ids([29, 11995])
        self.state = state_of(self.url)

    def test_url_points_at_the_neuroglancer_app(self):
        self.assertTrue(self.url.startswith(f"{nglui.NEUROGLANCER_URL}/#!"))

    def test_neurons_come_from_the_skeleton_source(self):
        neurons = layers_by_name(self.state)["neurons"]
        self.assertEqual("segmentation", neurons["type"])
        self.assertEqual(f"precomputed://{nglui.SKELETONS_URL}", neurons["source"])
        self.assertEqual(["29", "11995"], neurons["segments"])

    def test_the_cns_outline_comes_from_the_mesh_source(self):
        cns = layers_by_name(self.state)["CNS"]
        self.assertEqual(f"precomputed://{nglui.MESHES_URL}", cns["source"])
        self.assertEqual([str(nglui.CNS_VOLUME_ID)], cns["segments"])
        self.assertLess(cns["objectAlpha"], 0.5)

    def test_the_view_is_3d_only(self):
        self.assertEqual("3d", self.state["layout"])
        self.assertFalse(self.state["showSlices"])
        self.assertNotIn("image", {layer["type"] for layer in self.state["layers"]})

    def test_the_cns_is_seen_from_the_side(self):
        # a quaternion (x, y, z, w) of unit length: 90 degrees around the x axis
        x, y, z, w = self.state["projectionOrientation"]
        self.assertAlmostEqual(1.0, x * x + y * y + z * z + w * w)
        self.assertAlmostEqual(0.7071, x, places=3)
        self.assertGreater(self.state["projectionScale"], 100000)

    def test_coordinates_are_nanometres(self):
        self.assertEqual(
            {axis: [1e-9, "m"] for axis in "xyz"}, self.state["dimensions"]
        )

    def test_the_view_is_centred_on_the_cns_by_default(self):
        self.assertEqual(list(nglui.CNS_CENTER_NM), self.state["position"])

    def test_the_view_can_be_centred_on_a_position(self):
        state = state_of(nglui.url_for_root_ids([29], position=(1, 2, 3)))
        self.assertEqual([1, 2, 3], state["position"])

    def test_side_panel_defaults_to_visible_for_several_cells(self):
        self.assertTrue(self.state["selectedLayer"]["visible"])
        one = state_of(nglui.url_for_root_ids([29]))
        self.assertFalse(one["selectedLayer"]["visible"])
        self.assertEqual("neurons", one["selectedLayer"]["layer"])

    def test_side_panel_can_be_forced(self):
        self.assertFalse(
            state_of(nglui.url_for_root_ids([29, 30], show_side_panel=0))["selectedLayer"]["visible"]
        )
        self.assertTrue(
            state_of(nglui.url_for_root_ids([29], show_side_panel=1))["selectedLayer"]["visible"]
        )

    def test_url_stays_short_for_many_cells(self):
        # only ids go into the link, so it grows by about 40 characters per cell
        self.assertLess(len(nglui.url_for_root_ids(list(range(10_000_000, 10_000_050)))), 3000)


class UrlForRandomSampleTest(TestCase):
    def test_sample_is_capped_deterministic_and_keeps_order(self):
        ids = list(range(1000, 2000))
        first = layers_by_name(state_of(nglui.url_for_random_sample(ids, sample_size=50)))["neurons"]["segments"]
        second = layers_by_name(state_of(nglui.url_for_random_sample(ids, sample_size=50)))["neurons"]["segments"]
        self.assertEqual(first, second)
        self.assertEqual(50, len(first))
        self.assertEqual(sorted(first, key=int), first)

    def test_small_selections_are_kept_whole(self):
        segments = layers_by_name(state_of(nglui.url_for_random_sample([5, 6, 7])))["neurons"]["segments"]
        self.assertEqual(["5", "6", "7"], segments)

    def test_global_random_state_is_left_alone(self):
        random.seed(1)
        expected = random.random()
        random.seed(1)
        nglui.url_for_random_sample(list(range(1000)))
        self.assertEqual(expected, random.random())


class UrlForNeuropilsTest(TestCase):
    def test_selected_regions_are_shown_with_their_colors(self):
        state = state_of(nglui.url_for_neuropils([REGIONS["A1_L"][0], REGIONS["BRAIN_R"][0]]))
        regions = layers_by_name(state)["regions"]
        self.assertEqual(f"precomputed://{nglui.MESHES_URL}", regions["source"])
        self.assertEqual({"83", "62"}, set(regions["segments"]))
        self.assertEqual(COLORS["A1_L"], regions["segmentColors"]["83"])
        self.assertEqual(COLORS["BRAIN_R"], regions["segmentColors"]["62"])

    def test_unassigned_pseudo_region_is_left_out(self):
        regions = layers_by_name(state_of(nglui.url_for_neuropils([83, -1])))["regions"]
        self.assertEqual(["83"], regions["segments"])

    def test_no_selection_shows_every_region(self):
        regions = layers_by_name(state_of(nglui.url_for_neuropils()))["regions"]
        self.assertEqual(26, len(regions["segmentColors"]))

    def test_view_is_3d_only_with_the_cns_outline(self):
        state = state_of(nglui.url_for_neuropils([83]))
        self.assertEqual("3d", state["layout"])
        self.assertIn("CNS", layers_by_name(state))
        self.assertNotIn("image", {layer["type"] for layer in state["layers"]})
