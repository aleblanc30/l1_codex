from copy import deepcopy
from unittest import TestCase

from codex.data.neuron_data_initializer import initialize_neuron_data
from codex.data.structured_search_filters import (
    OP_GREATER_EQUAL,
    OP_LESS_EQUAL,
    parse_search_query,
)
from tests.l1_fixture import AGGREGATE_ID, _connection, initialize_kwargs, l1_rows


class ParsingTest(TestCase):
    def test_greater_equal_shorthand_is_parsed(self):
        _, free_form, structured = parse_search_query("node_count >= 100")
        self.assertEqual([], free_form)
        self.assertEqual(
            [{"op": OP_GREATER_EQUAL, "lhs": "node_count", "rhs": "100"}], structured
        )

    def test_less_equal_shorthand_is_parsed(self):
        _, _, structured = parse_search_query("node_count <= 100")
        self.assertEqual(
            [{"op": OP_LESS_EQUAL, "lhs": "node_count", "rhs": "100"}], structured
        )

    def test_operator_names_are_parsed(self):
        _, _, structured = parse_search_query("node_count {gte} 100")
        self.assertEqual(OP_GREATER_EQUAL, structured[0]["op"])
        _, _, structured = parse_search_query("node_count {lte} 100")
        self.assertEqual(OP_LESS_EQUAL, structured[0]["op"])

    def test_existing_shorthands_are_not_mistaken_for_the_new_ones(self):
        for query, op in [
            ("cell_type >> KC", "{contains}"),
            ("cell_type !> KC", "{not_contains}"),
            ("cell_type << KC", "{in}"),
            ("cell_type !< KC", "{not_in}"),
            ("side == left", "{equal}"),
            ("side != left", "{not_equal}"),
        ]:
            _, _, structured = parse_search_query(query)
            self.assertEqual(op, structured[0]["op"], query)

    def test_chained_numeric_terms_are_parsed(self):
        chaining, _, structured = parse_search_query(
            "node_count >= 10 && node_count <= 100"
        )
        self.assertEqual("{and}", chaining)
        self.assertEqual([OP_GREATER_EQUAL, OP_LESS_EQUAL], [t["op"] for t in structured])


class SearchTest(TestCase):
    """Fixture: 1001 (500 nodes, soma), 1002 (40 nodes), 1003 (5 nodes) and one orphan aggregate."""

    @classmethod
    def setUpClass(cls):
        cls.db = initialize_neuron_data(**initialize_kwargs())

    def search(self, query):
        return set(self.db.search(query))

    def test_node_count_lower_bound_is_inclusive(self):
        self.assertEqual({1001, 1002}, self.search("node_count >= 40"))

    def test_node_count_upper_bound_is_inclusive(self):
        self.assertEqual({1002, 1003}, self.search("node_count <= 40"))

    def test_node_count_range_by_chaining(self):
        self.assertEqual({1002}, self.search("node_count >= 10 && node_count <= 100"))

    def test_numeric_comparison_is_numeric_and_not_alphabetic(self):
        # "500" sorts before "60" as text
        self.assertEqual({1001}, self.search("node_count >= 60"))

    def test_node_count_equality(self):
        self.assertEqual({1001}, self.search("node_count == 500"))

    def test_numeric_operator_on_a_text_attribute_is_rejected(self):
        with self.assertRaises(ValueError):
            self.db.search("side >= left")

    def test_non_numeric_value_for_a_numeric_operator_is_rejected(self):
        with self.assertRaises(ValueError):
            self.db.search("node_count >= many")

    def test_decimal_bound_for_a_count(self):
        self.assertEqual({1001}, self.search("node_count >= 40.5"))

    def test_soma_true(self):
        self.assertEqual({1001}, self.search("has_soma == true"))

    def test_soma_false(self):
        self.assertEqual({1002, 1003}, self.search("has_soma == false"))

    def test_soma_rejects_other_values(self):
        with self.assertRaises(ValueError):
            self.db.search("has_soma == maybe")

    def test_soma_presence_by_has_operator(self):
        self.assertEqual({1001}, self.search("$$ has_soma"))
        self.assertEqual({1002, 1003}, self.search("!$ has_soma"))

    def test_paper_substring(self):
        self.assertEqual({1002}, self.search("papers >> Zwart"))
        self.assertEqual({1001, 1002}, self.search("papers >> Winding"))

    def test_paper_exclusion(self):
        self.assertEqual({1003}, self.search("papers !> Winding"))

    def test_annotation_substring_ignores_case(self):
        self.assertEqual({1001}, self.search("annotations >> left"))

    def test_annotation_with_markup_characters(self):
        self.assertEqual({1002}, self.search("annotations >> Brain&SEZ"))

    def test_annotation_absence(self):
        self.assertEqual({1003}, self.search("!$ annotations"))

    def test_raw_orphan_synapse_counts(self):
        self.assertEqual({1001}, self.search("orphan_output_synapses >= 1"))
        self.assertEqual(set(), self.search("orphan_input_synapses >= 1"))

    def test_orphan_output_share_is_orphan_synapses_over_output_synapses(self):
        # 1001 sends 3 + 5 synapses of which 2 go to orphaned sites: 25%
        self.assertEqual({1001}, self.search("orphan_output_share >= 0.2"))
        self.assertEqual({1002, 1003}, self.search("orphan_output_share <= 0.1"))

    def test_orphan_share_of_a_cell_without_synapses_is_zero(self):
        rows = deepcopy(l1_rows())
        rows["connections"] = rows["connections"][:1]  # header only
        db = initialize_neuron_data(**initialize_kwargs(rows))
        self.assertEqual({1001, 1002, 1003}, set(db.search("orphan_input_share <= 0")))

    def test_orphan_share_never_exceeds_one(self):
        rows = deepcopy(l1_rows())
        for r in rows["skeletons"][1:]:
            if r[0] == "1001":
                r[8] = "999"  # orphan_output_synapses, more than the cell's output
        db = initialize_neuron_data(**initialize_kwargs(rows))
        self.assertEqual([], db.search("orphan_output_share >= 1.01"))
        self.assertEqual([1001], db.search("orphan_output_share >= 1"))


class AggregateVisibilityTest(TestCase):
    @classmethod
    def setUpClass(cls):
        cls.db = initialize_neuron_data(**initialize_kwargs())

    def test_empty_query_lists_real_cells_only(self):
        self.assertNotIn(AGGREGATE_ID, self.db.search(""))
        self.assertEqual({1001, 1002, 1003}, set(self.db.search("")))

    def test_free_text_does_not_list_aggregates(self):
        self.assertEqual([], self.db.search("orphaned"))
        self.assertNotIn(AGGREGATE_ID, self.db.search("BRAIN_L"))

    def test_structured_query_on_another_attribute_does_not_list_aggregates(self):
        self.assertNotIn(AGGREGATE_ID, self.db.search("side == left"))
        self.assertEqual({1001}, set(self.db.search("side == left")))

    def test_aggregates_are_found_by_asking_for_them(self):
        self.assertEqual([AGGREGATE_ID], self.db.search("is_aggregate == true"))

    def test_aggregates_are_found_by_the_has_operator(self):
        self.assertEqual([AGGREGATE_ID], self.db.search("$$ is_aggregate"))

    def test_real_cells_are_found_by_is_aggregate_false(self):
        self.assertEqual(
            {1001, 1002, 1003}, set(self.db.search("is_aggregate == false"))
        )

    def test_asking_for_aggregates_in_an_or_chain_keeps_the_other_results(self):
        self.assertEqual(
            {1001, AGGREGATE_ID}, set(self.db.search("MBON || is_aggregate == true"))
        )

    def test_an_aggregate_is_found_by_its_id(self):
        self.assertEqual([AGGREGATE_ID], self.db.search(str(AGGREGATE_ID)))
        self.assertEqual([AGGREGATE_ID], self.db.search(f"id == {AGGREGATE_ID}"))

    def test_upstream_and_downstream_operators_skip_aggregates(self):
        self.assertEqual([1002], self.db.search("{downstream} 1001"))


class AggregatePartnersTest(TestCase):
    @classmethod
    def setUpClass(cls):
        cls.db = initialize_neuron_data(**initialize_kwargs())

    def test_aggregates_are_not_output_partners(self):
        self.assertEqual({1002}, self.db.output_sets()[1001])

    def test_aggregates_are_not_input_partners(self):
        rows = deepcopy(l1_rows())
        rows["connections"].append(
            [str(v) for v in _connection(AGGREGATE_ID, 1001, "BRAIN_L", 4).values()]
        )
        db = initialize_neuron_data(**initialize_kwargs(rows))
        self.assertEqual({1002, 1003}, db.input_sets()[1001])

    def test_aggregates_have_no_partners_themselves(self):
        self.assertEqual(set(), self.db.input_sets()[AGGREGATE_ID])
        self.assertEqual(set(), self.db.output_sets()[AGGREGATE_ID])

    def test_synapse_weighted_partners_skip_aggregates(self):
        ins, outs = self.db.input_output_partners_with_synapse_counts()
        self.assertEqual({1002: 3}, outs[1001])
        self.assertEqual({}, ins[AGGREGATE_ID])

    def test_min_synapse_threshold_still_applies(self):
        self.assertEqual(set(), self.db.output_sets(min_syn_count=4)[1001])

    def test_the_aggregate_stays_in_the_cell_connection_table(self):
        partners = {r[1] for r in self.db.cell_connections(1001) if r[0] == 1001}
        self.assertIn(AGGREGATE_ID, partners)

    def test_reciprocal_counts_leave_out_aggregates(self):
        rows = deepcopy(l1_rows())
        rows["connections"].append(
            [str(v) for v in _connection(AGGREGATE_ID, 1001, "BRAIN_L", 4).values()]
        )
        db = initialize_neuron_data(**initialize_kwargs(rows))
        counts = db.grouped_reciprocal_connection_counts["side"]
        # 1001 (left) and the aggregate (left) send to each other, which must not count
        self.assertNotIn(("left", "left"), counts)
        self.assertEqual(2, counts[("left", "right")])
