import logging
import re
from unittest import TestCase

from codex.data.sorting import SORT_BY_OPTIONS
from codex.data.structured_search_filters import (
    SEARCH_ATTRIBUTE_NAMES,
    STRUCTURED_SEARCH_OPERATORS,
)
from codex.utils.stats import _make_data_stats
from tests import get_testing_neuron_db
from tests.app_client import make_test_client

PAGES_WITH_COMMUNITY_MARKUP_REMOVED = [
    "/",
    "/app/stats",
    "/app/explore",
    "/app/search?filter_string=KC",
    "/app/search?filter_string=*&page_size=5",
    "/app/cell_details?root_id=29",
    "/about_flywire",
]

OTHER_PAGES = [
    "/app/heatmaps",
    "/app/neuropils",
    "/app/connectivity?cell_names_or_ids=29",
    "/app/path_length",
    "/app/pathways?source_cell_id=29&target_cell_id=11995",
    "/app/motifs/",
    "/app/cell_coordinates/29",
    "/faq",
    "/about_codex",
    "/app/download_search_results?filter_string=KC",
]

# Text that only the community labeling features produce
COMMUNITY_MARKUP = [
    "Community Labels",
    "communityLabelsModal",
    "labeling_log",
    "leaderboard",
    "Contribute your annotation",
    "labeled cells",
    "# Labels",
    "label {contains}",
    "label {starts_with}",
    "label {not_contains}",
    "apply_filter('label",
]


class CommunityFeaturesHiddenTest(TestCase):
    @classmethod
    def setUpClass(cls):
        logging.disable(logging.CRITICAL)
        cls.client = make_test_client()
        cls.endpoints = {r.endpoint for r in cls.client.application.url_map.iter_rules()}

    @classmethod
    def tearDownClass(cls):
        logging.disable(logging.NOTSET)

    def test_community_routes_are_not_registered(self):
        self.assertNotIn("app.leaderboard", self.endpoints)
        self.assertNotIn("app.labeling_log", self.endpoints)

    def test_community_routes_are_not_served(self):
        self.assertEqual(404, self.client.get("/app/leaderboard").status_code)
        self.assertEqual(404, self.client.get("/app/labeling_log?root_id=29").status_code)

    def test_cell_details_accepts_only_get(self):
        self.assertEqual(405, self.client.post("/app/cell_details").status_code)

    def test_pages_still_render(self):
        for page in PAGES_WITH_COMMUNITY_MARKUP_REMOVED + OTHER_PAGES:
            self.assertEqual(200, self.client.get(page).status_code, page)

    def test_pages_have_no_community_markup(self):
        for page in PAGES_WITH_COMMUNITY_MARKUP_REMOVED:
            body = self.client.get(page).get_data(as_text=True)
            for text in COMMUNITY_MARKUP:
                self.assertNotIn(text, body, f"{text!r} found on {page}")

    def test_home_page_counts_typed_cells(self):
        body = self.client.get("/").get_data(as_text=True)
        self.assertIn("typed cells", body)
        self.assertNotIn("labeled", body)

    def test_csv_download_has_no_label_column(self):
        response = self.client.get("/app/download_search_results?filter_string=KC")
        header = response.get_data(as_text=True).splitlines()[0].split(",")
        self.assertNotIn("label", header)
        self.assertIn("root_id", header)

    def test_label_is_not_a_search_attribute(self):
        self.assertNotIn("label", SEARCH_ATTRIBUTE_NAMES)

    def test_search_operator_examples_do_not_mention_labels(self):
        for operator in STRUCTURED_SEARCH_OPERATORS:
            self.assertIsNone(
                re.search(r"\blabel\b", operator.description), operator.name
            )

    def test_there_is_no_label_count_sort_option(self):
        self.assertNotIn("labels", SORT_BY_OPTIONS)
        self.assertNotIn("-labels", SORT_BY_OPTIONS)


class StatsWithoutLabelsTest(TestCase):
    def test_data_stats_have_no_label_entries(self):
        neuron_data = list(get_testing_neuron_db().neuron_data.values())
        stats = _make_data_stats(neuron_data)
        self.assertNotIn("Top Labels", stats)
        self.assertNotIn("- With label(s)", stats[""])
        self.assertIn("- Classified", stats[""])
