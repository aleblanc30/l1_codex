import json
import logging
import urllib.parse
from unittest import TestCase

from codex.configuration import MAX_NEURONS_FOR_DOWNLOAD
from codex.utils import nglui
from tests.app_client import make_test_client

CHROME = {
    "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}

# Strings that only the FlyWire viewer and thumbnails produced
FLYWIRE_VIEWER_MARKUP = [
    "flywire_url",
    "flywire_neuropil_url",
    "skeleton_thumbnail",
    "ngl.flywire.ai",
    "flywire-data",
    "Open in Flywire",
    "point_to",
]

PAGES = [
    "/",
    "/app/search?filter_string=KC",
    "/app/search?filter_string=999999999999999999",
    "/app/cell_details?root_id=29",
    "/app/neuropils",
    "/app/connectivity?cell_names_or_ids=29",
]


def state_of(response):
    return json.loads(urllib.parse.unquote(response.headers["Location"].split("#!", 1)[1]))


class ViewerRoutesTest(TestCase):
    @classmethod
    def setUpClass(cls):
        logging.disable(logging.CRITICAL)
        cls.client = make_test_client()

    @classmethod
    def tearDownClass(cls):
        logging.disable(logging.NOTSET)

    def get(self, path):
        return self.client.get(path, headers=CHROME)

    def test_cell_route_redirects_to_neuroglancer(self):
        response = self.get("/app/neuroglancer_url?root_ids=29&root_ids=11995")
        self.assertEqual(302, response.status_code)
        self.assertTrue(response.headers["Location"].startswith(nglui.NEUROGLANCER_URL))
        neurons = [l for l in state_of(response)["layers"] if l["name"] == "neurons"][0]
        self.assertEqual(["29", "11995"], neurons["segments"])

    def test_a_single_cell_is_centered_on_its_soma(self):
        state = state_of(self.get("/app/neuroglancer_url?root_ids=29"))
        self.assertEqual([37250, 3898, 52500], state["position"])

    def test_several_cells_are_centered_on_the_cns(self):
        state = state_of(self.get("/app/neuroglancer_url?root_ids=29&root_ids=11995"))
        self.assertEqual(list(nglui.CNS_CENTER_NM), state["position"])

    def test_search_results_route_shows_a_sample_of_the_results(self):
        response = self.get("/app/search_results_neuroglancer_url?filter_string=KC")
        self.assertEqual(302, response.status_code)
        neurons = [l for l in state_of(response)["layers"] if l["name"] == "neurons"][0]
        self.assertTrue(0 < len(neurons["segments"]) <= MAX_NEURONS_FOR_DOWNLOAD)

    def test_neuropil_route_shows_the_selected_regions(self):
        response = self.get("/app/neuroglancer_neuropil_url?selected=A1_L,BRAIN_L")
        self.assertEqual(302, response.status_code)
        regions = [l for l in state_of(response)["layers"] if l["name"] == "regions"][0]
        self.assertEqual({"83", "61"}, set(regions["segments"]))

    def test_unsupported_browsers_get_a_warning_first(self):
        response = self.client.get("/app/neuroglancer_url?root_ids=29")
        self.assertEqual(200, response.status_code)
        self.assertIn("Proceed anyway", response.get_data(as_text=True))

    def test_flywire_named_routes_are_gone(self):
        for path in [
            "/app/flywire_url?root_ids=29",
            "/app/search_results_flywire_url?filter_string=KC",
            "/app/flywire_neuropil_url?selected=A1_L",
            "/skeleton_thumbnail_url?cell_or_neuropil=29",
        ]:
            self.assertEqual(404, self.get(path).status_code, path)

    def test_pages_have_no_flywire_viewer_or_thumbnail_markup(self):
        for page in PAGES:
            response = self.get(page)
            self.assertEqual(200, response.status_code, page)
            body = response.get_data(as_text=True)
            for text in FLYWIRE_VIEWER_MARKUP:
                self.assertNotIn(text, body, f"{text!r} found on {page}")

    def test_cell_page_embeds_the_neuroglancer_view_and_has_no_swc_download(self):
        body = self.get("/app/cell_details?root_id=29").get_data(as_text=True)
        self.assertIn('title="neuroglancer"', body)
        self.assertIn("/app/neuroglancer_url?", body)
        self.assertNotIn("SWC", body)

    def test_search_results_link_each_cell_to_the_3d_viewer(self):
        body = self.get("/app/search?filter_string=KC").get_data(as_text=True)
        self.assertIn("/app/neuroglancer_url?", body)
        self.assertNotIn("<img", body.split("<tbody>")[1].split("</tbody>")[0])
