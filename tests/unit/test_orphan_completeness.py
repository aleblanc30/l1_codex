import logging
from unittest import TestCase

from codex.utils.formatting import orphan_completeness
from tests import get_testing_neuron_db
from tests.app_client import make_test_client


def cell(**overrides):
    nd = {
        "is_aggregate": 0,
        "total_input_synapses": 3,
        "orphan_input_synapses": 1,
        "total_output_synapses": 8,
        "orphan_output_synapses": 2,
    }
    nd.update(overrides)
    return nd


class CaptionTest(TestCase):
    def test_both_directions_with_percentages_and_counts(self):
        text = orphan_completeness(cell())
        self.assertIn("33% of input synapses (1 of 3)", text)
        self.assertIn("25% of output synapses (2 of 8)", text)

    def test_the_note_says_that_counts_understate_connectivity(self):
        self.assertIn("understate", orphan_completeness(cell()))

    def test_a_direction_without_synapses_is_left_out(self):
        text = orphan_completeness(cell(total_input_synapses=0, orphan_input_synapses=0))
        self.assertNotIn("input", text)
        self.assertIn("25% of output synapses (2 of 8)", text)

    def test_a_tiny_share_is_not_shown_as_zero(self):
        text = orphan_completeness(
            cell(total_output_synapses=1000, orphan_output_synapses=2)
        )
        self.assertIn("<1% of output synapses (2 of 1,000)", text)

    def test_a_cell_without_orphaned_synapses_says_so_without_the_note(self):
        text = orphan_completeness(
            cell(orphan_input_synapses=0, orphan_output_synapses=0)
        )
        self.assertIn("0% of input synapses (0 of 3)", text)
        self.assertNotIn("understate", text)

    def test_nothing_for_cells_without_synapses(self):
        self.assertIsNone(
            orphan_completeness(cell(total_input_synapses=0, total_output_synapses=0))
        )

    def test_nothing_for_aggregates(self):
        self.assertIsNone(orphan_completeness(cell(is_aggregate=1)))

    def test_the_share_never_exceeds_one_hundred_percent(self):
        text = orphan_completeness(cell(orphan_output_synapses=99))
        self.assertIn("100% of output synapses", text)


class CellPageTest(TestCase):
    @classmethod
    def setUpClass(cls):
        logging.disable(logging.CRITICAL)

    @classmethod
    def tearDownClass(cls):
        logging.disable(logging.NOTSET)

    def test_the_cell_page_shows_the_indicator(self):
        page = make_test_client().get("/app/cell_details?root_id=29").get_data(as_text=True)
        self.assertIn("of output synapses", page)
        self.assertIn("Orphaned synapses", page)

    def test_the_page_of_an_aggregate_has_no_indicator(self):
        aggregate_id = sorted(get_testing_neuron_db().aggregate_ids)[0]
        page = make_test_client().get(f"/app/cell_details?root_id={aggregate_id}")
        self.assertEqual(200, page.status_code)
        self.assertNotIn("Orphaned synapses", page.get_data(as_text=True))
