import re
from unittest import TestCase

from codex.data.neuron_data_initializer import (
    HEATMAP_GROUP_BY_ATTRIBUTES,
    NETWORK_GROUP_BY_ATTRIBUTES,
    initialize_neuron_data,
)
from codex.service.heatmaps import ALL, heatmap_data
from tests.l1_fixture import initialize_kwargs
from tests.app_client import make_test_client


class GroupByGroupTest(TestCase):
    """Fixture groups: MBON-a1, chos_v'ch_a1, A3_L and the aggregate (one cell each)."""

    @classmethod
    def setUpClass(cls):
        cls.db = initialize_neuron_data(**initialize_kwargs())

    def test_group_is_offered_for_heatmaps_and_networks(self):
        self.assertIn("group", HEATMAP_GROUP_BY_ATTRIBUTES)
        self.assertIn("group", NETWORK_GROUP_BY_ATTRIBUTES)

    def test_side_stays_the_default_choice(self):
        self.assertEqual("side", HEATMAP_GROUP_BY_ATTRIBUTES[0])

    def test_grouped_counts_exist_for_group(self):
        self.assertIn("group", self.db.grouped_synapse_counts)
        self.assertEqual(
            3, self.db.grouped_synapse_counts["group"][("MBON-a1", "chos_v'ch_a1")]
        )

    def test_the_heatmap_offers_group(self):
        data = heatmap_data(self.db, "Group", "Synapses")
        self.assertIn("Group", data["group_by_options"])

    def test_every_group_gets_a_row_and_a_column_when_there_are_few(self):
        data = heatmap_data(self.db, "Group", "Synapses")
        self.assertEqual(1 + 5, len(data["table"][0]))  # corner, All and 4 groups
        self.assertEqual(1 + 5, len(data["table"]))

    def test_the_heatmap_shows_the_largest_groups_when_there_are_many(self):
        data = heatmap_data(self.db, "Group", "Synapses", max_groups=2)
        self.assertEqual(1 + 3, len(data["table"][0]))  # corner, All and 2 groups
        self.assertEqual(1 + 3, len(data["table"]))

    def test_the_cap_is_explained(self):
        data = heatmap_data(self.db, "Group", "Synapses", max_groups=2)
        self.assertTrue(any("2 largest of 4" in e for e in data["explanations"]))

    def test_no_note_when_all_groups_are_shown(self):
        data = heatmap_data(self.db, "Group", "Synapses")
        self.assertFalse(any("largest of" in e for e in data["explanations"]))

    def test_all_row_still_counts_every_group(self):
        data = heatmap_data(self.db, "Group", "Synapses", max_groups=1)
        all_row = next(r for r in data["table"][1:] if ALL in re.sub("<[^>]*>", "", r[0][0]))
        # the "All" row has a cell for the All column and one group column
        self.assertEqual(1 + 2, len(all_row))


class GroupByPagesTest(TestCase):
    def test_pages_render_with_group(self):
        client = make_test_client()
        heatmap = client.get("/app/heatmaps?group_by=Group&count_type=Synapses")
        self.assertEqual(200, heatmap.status_code)
        network = client.get("/app/connectivity?cell_names_or_ids=29&group_by=group")
        self.assertEqual(200, network.status_code)
