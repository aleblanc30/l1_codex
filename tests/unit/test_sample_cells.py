import html
import logging
import re
from copy import deepcopy
from random import Random
from unittest import TestCase

from codex.data.neuron_data_initializer import initialize_neuron_data
from codex.service.sample_cells import sample_network_cells, sample_pathway_cells
from codex.utils.graph_algos import reachable_nodes
from tests.app_client import make_test_client
from tests.l1_fixture import AGGREGATE_ID, _connection, initialize_kwargs, l1_rows

REGION = "A1_L"


def network_rows(edges, extra_cells=range(2001, 2013)):
    """The fixture plus cells 2001..2012 and the given connections (pre, post, synapses)."""
    rows = deepcopy(l1_rows())
    for rid in extra_cells:
        row = {"root_id": rid, "group": f"g{rid}", "nt_type": "UNKNOWN"}
        rows["neurons"].append([str(row.get(c, "")) for c in rows["neurons"][0]])
    for pre, post, count in edges:
        rows["connections"].append(
            [str(v) for v in _connection(pre, post, REGION, count).values()]
        )
    return rows


# a chain 2001 -> 2002 -> ... -> 2010, plus a hub 2011 that sends to and receives from cells of the chain
CHAIN = [(2000 + i, 2001 + i, 8) for i in range(1, 10)]
HUB = [(2011, 2002, 9), (2011, 2003, 7), (2004, 2011, 6), (2005, 2011, 12), (2011, 2006, 5)]


def make_db(edges=CHAIN + HUB):
    return initialize_neuron_data(**initialize_kwargs(network_rows(edges)))


class NetworkSampleTest(TestCase):
    @classmethod
    def setUpClass(cls):
        cls.db = make_db()

    def sample(self, seed=0, **kwargs):
        return sample_network_cells(self.db, rng=Random(seed), **kwargs)

    def test_cells_are_real_cells_of_the_database(self):
        for seed in range(20):
            for rid in self.sample(seed):
                self.assertTrue(self.db.is_in_dataset(rid))
                self.assertNotIn(rid, self.db.aggregate_ids)

    def test_the_sample_has_several_cells_and_no_more_than_asked(self):
        for seed in range(20):
            cells = self.sample(seed, size=5)
            self.assertTrue(2 <= len(cells) <= 5, cells)
            self.assertEqual(len(cells), len(set(cells)))

    def test_every_cell_is_a_partner_of_the_first_one(self):
        ins, outs = self.db.input_output_partner_sets()
        for seed in range(20):
            first, *others = self.sample(seed)
            for rid in others:
                self.assertTrue(rid in outs[first] or rid in ins[first], (first, rid))

    def test_the_first_cell_is_well_connected(self):
        ins, outs = self.db.input_output_partner_sets()
        for seed in range(20):
            first = self.sample(seed)[0]
            self.assertGreaterEqual(len(ins[first]) + len(outs[first]), 3)

    def test_the_same_seed_gives_the_same_sample(self):
        self.assertEqual(self.sample(4), self.sample(4))

    def test_different_seeds_give_different_samples(self):
        self.assertGreater(len({tuple(self.sample(s)) for s in range(30)}), 1)

    def test_synapse_threshold_leaves_out_weak_partners(self):
        ins, outs = self.db.input_output_partners_with_synapse_counts()
        for seed in range(20):
            first, *others = self.sample(seed, min_synapse_count=6)
            for rid in others:
                strength = max(outs[first].get(rid, 0), ins[first].get(rid, 0))
                self.assertGreaterEqual(strength, 6)

    def test_a_cell_with_a_type_is_preferred_as_the_first_cell(self):
        rows = network_rows(CHAIN + HUB)
        rows["cell_types"].append(["2011", "MBON-x"])
        rows["cell_types"].append(["2003", "MBIN-y"])
        db = initialize_neuron_data(**initialize_kwargs(rows))
        firsts = {sample_network_cells(db, rng=Random(s))[0] for s in range(30)}
        self.assertEqual({2011, 2003}, firsts)

    def test_untyped_cells_are_used_when_no_connected_cell_has_a_type(self):
        firsts = {sample_network_cells(self.db, rng=Random(s))[0] for s in range(30)}
        self.assertGreater(len(firsts), 1)

    def test_a_database_without_connections_gives_no_sample(self):
        db = initialize_neuron_data(**initialize_kwargs(network_rows([])))
        self.assertEqual([], sample_network_cells(db, rng=Random(1)))

    def test_lonely_cells_are_not_enough(self):
        db = make_db([(2001, 2002, 8)])
        self.assertEqual([], sample_network_cells(db, rng=Random(1)))


class PathwaySampleTest(TestCase):
    @classmethod
    def setUpClass(cls):
        cls.db = make_db()

    def sample(self, seed=0, **kwargs):
        return sample_pathway_cells(self.db, rng=Random(seed), **kwargs)

    def test_sizes_are_within_the_limits(self):
        for seed in range(20):
            sources, targets = self.sample(seed, num_sources=2, num_targets=3)
            self.assertTrue(1 <= len(sources) <= 2)
            self.assertTrue(1 <= len(targets) <= 3)

    def test_sources_and_targets_are_different_cells(self):
        for seed in range(20):
            sources, targets = self.sample(seed)
            self.assertFalse(set(sources) & set(targets))

    def test_every_target_can_be_reached_from_a_source(self):
        outs = self.db.output_sets()
        for seed in range(20):
            sources, targets = self.sample(seed)
            reached = reachable_nodes(sources, outs)
            for target in targets:
                self.assertIn(target, reached, (sources, target))

    def test_targets_are_at_least_two_steps_away_when_such_cells_exist(self):
        outs = self.db.output_sets()
        for seed in range(20):
            sources, targets = self.sample(seed)
            reached = reachable_nodes(sources, outs)
            for target in targets:
                self.assertGreaterEqual(reached[target], 2)

    def test_targets_are_not_very_far_away(self):
        outs = self.db.output_sets()
        for seed in range(20):
            sources, targets = self.sample(seed)
            reached = reachable_nodes(sources, outs)
            for target in targets:
                self.assertLessEqual(reached[target], 3)

    def test_aggregates_are_never_used(self):
        for seed in range(20):
            sources, targets = self.sample(seed)
            self.assertNotIn(AGGREGATE_ID, sources + targets)

    def test_the_same_seed_gives_the_same_sample(self):
        self.assertEqual(self.sample(3), self.sample(3))

    def test_direct_partners_are_used_when_nothing_is_further_away(self):
        db = make_db([(2001, 2002, 8), (2001, 2003, 8), (2001, 2004, 8), (2005, 2001, 8)])
        sources, targets = sample_pathway_cells(db, rng=Random(1))
        self.assertTrue(sources and targets)
        reached = reachable_nodes(sources, db.output_sets())
        for target in targets:
            self.assertEqual(1, reached[target])

    def test_a_database_without_connections_gives_no_sample(self):
        db = initialize_neuron_data(**initialize_kwargs(network_rows([])))
        self.assertEqual(([], []), sample_pathway_cells(db, rng=Random(1)))


class SampleButtonsTest(TestCase):
    """The buttons on the pathways and network pages, on the real data and its neuron sets."""

    @classmethod
    def setUpClass(cls):
        logging.disable(logging.CRITICAL)

    @classmethod
    def tearDownClass(cls):
        logging.disable(logging.NOTSET)

    def setUp(self):
        self.client = make_test_client()

    def test_pathway_sample_shows_a_table_with_paths(self):
        for neuron_set in ["winding", "all", "soma"]:
            for _ in range(4):
                response = self.client.get(
                    "/app/path_length?source_cell_names_or_ids=__sample_cells__"
                    f"&target_cell_names_or_ids=__sample_cells__&neuron_set={neuron_set}"
                )
                self.assertEqual(200, response.status_code, neuron_set)
                page = response.get_data(as_text=True)
                self.assertIn("<table", page)
                # a distance of 1 or more is shown as a link to the pathway
                self.assertRegex(page, r"pathways\?source_cell_id=")

    def test_network_sample_shows_a_network(self):
        for neuron_set in ["winding", "all", "soma"]:
            for _ in range(4):
                response = self.client.get(
                    f"/app/connectivity?cell_names_or_ids=__sample_cells__&neuron_set={neuron_set}"
                )
                self.assertEqual(200, response.status_code, neuron_set)
                # the network is drawn in an iframe, whose page is an escaped attribute
                page = html.unescape(response.get_data(as_text=True))
                nodes = re.search(r'const nodeslist = (\[.*?\]);', page)
                self.assertIsNotNone(nodes, neuron_set)
                self.assertGreaterEqual(nodes.group(1).count('"id"'), 2)

    def test_the_random_cell_button_still_works(self):
        for _ in range(4):
            response = self.client.get("/app/cell_details?cell_names_or_id=%7Brandom_cell%7D")
            self.assertEqual(200, response.status_code)
