from copy import deepcopy
from unittest import TestCase

from codex.data.neuron_data_initializer import initialize_neuron_data
from codex.data.neuron_sets import (
    DEFAULT_NEURON_SET,
    NEURON_SET_ALL,
    NEURON_SET_SOMA,
    build_neuron_sets,
    paper_slug,
    resolve_neuron_set,
)
from tests.l1_fixture import AGGREGATE_ID, initialize_kwargs, l1_rows

ZWART = "paper-zwart-et-al-2016"


class DefinitionTest(TestCase):
    """Fixture: 1001 (Winding, soma), 1002 (Winding and Zwart), 1003 (no papers), one aggregate."""

    @classmethod
    def setUpClass(cls):
        cls.db = initialize_neuron_data(**initialize_kwargs())
        cls.sets = build_neuron_sets(cls.db.neuron_data)

    def test_winding_set_comes_first_and_is_the_default(self):
        self.assertEqual("winding", DEFAULT_NEURON_SET)
        self.assertEqual("winding", list(self.sets)[0])

    def test_choices_in_order(self):
        self.assertEqual(
            ["winding", NEURON_SET_ALL, NEURON_SET_SOMA, ZWART], list(self.sets)
        )

    def test_winding_paper_is_not_listed_twice(self):
        self.assertNotIn("paper-winding-pedigo-et-al-2023", self.sets)

    def test_members(self):
        self.assertEqual({1001, 1002}, self.sets["winding"].ids)
        self.assertEqual({1001, 1002, 1003}, self.sets[NEURON_SET_ALL].ids)
        self.assertEqual({1001}, self.sets[NEURON_SET_SOMA].ids)
        self.assertEqual({1002}, self.sets[ZWART].ids)

    def test_aggregates_are_no_members(self):
        for neuron_set in self.sets.values():
            self.assertNotIn(AGGREGATE_ID, neuron_set.ids)

    def test_labels_are_readable(self):
        self.assertEqual("Winding, Pedigo et al. 2023", self.sets["winding"].label)
        self.assertEqual("All skeletons", self.sets[NEURON_SET_ALL].label)
        self.assertEqual("Skeletons with a soma", self.sets[NEURON_SET_SOMA].label)
        self.assertEqual("Zwart et al. 2016", self.sets[ZWART].label)

    def test_papers_without_cells_are_not_offered(self):
        rows = deepcopy(l1_rows())
        rows["papers"].append(["9999", ""])
        db = initialize_neuron_data(**initialize_kwargs(rows))
        self.assertEqual(4, len(build_neuron_sets(db.neuron_data)))

    def test_without_a_winding_paper_the_default_choice_is_absent(self):
        rows = deepcopy(l1_rows())
        rows["papers"] = [rows["papers"][0], ["1002", "Zwart et al. 2016"]]
        db = initialize_neuron_data(**initialize_kwargs(rows))
        sets = build_neuron_sets(db.neuron_data)
        self.assertNotIn("winding", sets)
        self.assertEqual(NEURON_SET_ALL, resolve_neuron_set(None, list(sets)))


class ResolveTest(TestCase):
    KEYS = ["winding", "all", "soma", ZWART]

    def test_a_known_key_is_kept(self):
        self.assertEqual(ZWART, resolve_neuron_set(ZWART, self.KEYS))
        self.assertEqual("all", resolve_neuron_set("all", self.KEYS))

    def test_missing_or_unknown_key_gives_the_default(self):
        for requested in [None, "", "nonsense", "PAPER-X", "all "]:
            self.assertEqual("winding", resolve_neuron_set(requested, self.KEYS))

    def test_slug_of_a_paper_name(self):
        self.assertEqual(
            "winding-pedigo-et-al-2023", paper_slug("Winding, Pedigo et al. 2023")
        )
        self.assertEqual("imambocus-et-al", paper_slug("  Imambocus et al "))
        self.assertEqual("o-brien-x", paper_slug("O'Brien <x>"))


class ViewTest(TestCase):
    @classmethod
    def setUpClass(cls):
        cls.db = initialize_neuron_data(**initialize_kwargs())
        cls.view = cls.db.view("winding")

    def test_all_is_the_database_itself(self):
        self.assertIs(self.db, self.db.view("all"))

    def test_views_are_built_once(self):
        self.assertIs(self.view, self.db.view("winding"))

    def test_unknown_key_gives_the_default_view(self):
        self.assertIs(self.view, self.db.view("nonsense"))

    def test_view_knows_its_set(self):
        self.assertEqual("winding", self.view.neuron_set_key)
        self.assertEqual("all", self.db.neuron_set_key)

    def test_search_covers_the_members_only(self):
        self.assertEqual({1001, 1002}, set(self.view.search("")))
        self.assertEqual([], self.view.search("frag"))
        self.assertEqual([1003], self.db.search("frag"))

    def test_aggregates_stay_in_the_view_but_out_of_results(self):
        self.assertTrue(self.view.is_in_dataset(AGGREGATE_ID))
        self.assertNotIn(AGGREGATE_ID, self.view.search(""))
        self.assertEqual([AGGREGATE_ID], self.view.search("is_aggregate == true"))

    def test_non_members_are_not_in_the_view(self):
        self.assertFalse(self.view.is_in_dataset(1003))
        self.assertTrue(self.db.is_in_dataset(1003))

    def test_partner_sets_only_hold_members(self):
        self.assertEqual({1002}, self.view.input_sets()[1001])
        self.assertEqual({1002, 1003}, self.db.input_sets()[1001])

    def test_connection_rows_between_members_and_to_aggregates_are_kept(self):
        partners = {r[1] for r in self.view.cell_connections(1001) if r[0] == 1001}
        self.assertEqual({1002, AGGREGATE_ID}, partners)
        senders = {r[0] for r in self.view.cell_connections(1001) if r[1] == 1001}
        self.assertEqual({1002}, senders)

    def test_partner_counts_are_recomputed(self):
        base, view = self.db.get_neuron_data(1001), self.view.get_neuron_data(1001)
        self.assertEqual(2, base["input_cells"])
        self.assertEqual(1, view["input_cells"])
        self.assertEqual(3, base["input_synapses"])
        self.assertEqual(2, view["input_synapses"])

    def test_the_database_itself_is_not_changed_by_building_a_view(self):
        self.assertEqual(2, self.db.get_neuron_data(1001)["input_cells"])
        self.assertEqual({1002, 1003}, self.db.input_sets()[1001])

    def test_names_do_not_change_with_the_view(self):
        for rid in (1001, 1002):
            self.assertEqual(
                self.db.get_neuron_data(rid)["name"],
                self.view.get_neuron_data(rid)["name"],
            )

    def test_grouped_heatmap_counts_are_recomputed(self):
        base = self.db.grouped_synapse_counts["side"]
        view = self.view.grouped_synapse_counts["side"]
        self.assertEqual(1, base[("", "left")])
        self.assertNotIn(("", "left"), view)
        self.assertEqual(3, view[("left", "right")])

    def test_orphan_shares_keep_the_full_dataset_totals(self):
        rows = deepcopy(l1_rows())
        for r in rows["skeletons"][1:]:
            if r[0] == "1001":
                r[9] = "1"  # orphan_input_synapses, of 3 input synapses in all
        db = initialize_neuron_data(**initialize_kwargs(rows))
        view = db.view("winding")
        # in the view the cell has 2 input synapses, but the share is 1 of the 3 in the full data
        self.assertEqual(2, view.get_neuron_data(1001)["input_synapses"])
        self.assertEqual(
            [1001], view.search("orphan_input_share >= 0.3 && orphan_input_share <= 0.34")
        )
        self.assertEqual([], view.search("orphan_input_share >= 0.4"))

    def test_soma_view(self):
        self.assertEqual({1001}, set(self.db.view("soma").search("")))

    def test_paper_view(self):
        self.assertEqual({1002}, set(self.db.view(ZWART).search("")))

    def test_available_sets_are_listed_with_sizes(self):
        listed = {key: len(s.ids) for key, s in self.db.neuron_sets().items()}
        self.assertEqual({"winding": 2, "all": 3, "soma": 1, ZWART: 1}, listed)
