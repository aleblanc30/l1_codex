from copy import deepcopy
from unittest import TestCase

from codex.data.neuron_data_initializer import (
    HEATMAP_GROUP_BY_ATTRIBUTES,
    NEURON_DATA_ATTRIBUTE_TYPES,
    NETWORK_GROUP_BY_ATTRIBUTES,
    initialize_neuron_data,
)
from tests.l1_fixture import (
    AGGREGATE_ID,
    AGGREGATE_NAME,
    initialize_kwargs,
    l1_rows,
)


class Test(TestCase):
    def test_group_by_attribute_types(self):
        for k in HEATMAP_GROUP_BY_ATTRIBUTES + NETWORK_GROUP_BY_ATTRIBUTES:
            self.assertEqual(NEURON_DATA_ATTRIBUTE_TYPES[k], str)


class InitializeNeuronDataTest(TestCase):
    def setUp(self):
        self.db = initialize_neuron_data(**initialize_kwargs())
        self.nd = self.db.neuron_data

    def test_all_neurons_and_aggregates_are_loaded(self):
        self.assertEqual({1001, 1002, 1003, AGGREGATE_ID}, set(self.nd))

    def test_attribute_types_match_the_declaration(self):
        for rid, nd in self.nd.items():
            self.assertEqual(
                NEURON_DATA_ATTRIBUTE_TYPES, {k: type(v) for k, v in nd.items()}, rid
            )

    def test_cell_types_papers_and_annotations_are_kept_verbatim(self):
        self.assertEqual(["MBON-a1"], self.nd[1001]["cell_type"])
        self.assertEqual(["chos_v'ch_a1", "Second, type"], self.nd[1002]["cell_type"])
        self.assertEqual(["Winding, Pedigo et al. 2023"], self.nd[1001]["papers"])
        self.assertEqual(
            ["Winding, Pedigo et al. 2023", "Zwart et al. 2016"],
            self.nd[1002]["papers"],
        )
        self.assertEqual(["Left", "3"], self.nd[1001]["annotations"])
        self.assertEqual(["Brain&SEZ <x>", "a, b"], self.nd[1002]["annotations"])

    def test_group_and_skeleton_name_keep_quotes_and_are_trimmed(self):
        self.assertEqual("chos_v'ch_a1", self.nd[1002]["group"])
        self.assertEqual("v'ch a1r", self.nd[1002]["skeleton_name"])

    def test_skeleton_measurements_and_flags(self):
        nd = self.nd[1001]
        self.assertEqual(500, nd["node_count"])
        self.assertEqual(1, nd["has_soma"])
        self.assertEqual(12345, nd["length_nm"])
        self.assertEqual(["10 20 30"], nd["position"])
        self.assertEqual(0, nd["is_aggregate"])
        self.assertEqual([], self.nd[1003]["position"])
        self.assertEqual(0, self.nd[1003]["length_nm"])
        self.assertEqual(1, self.nd[AGGREGATE_ID]["is_aggregate"])

    def test_mirror_twins_and_orphan_counts(self):
        self.assertEqual(1002, self.nd[1001]["mirror_twin_root_id"])
        self.assertEqual(1001, self.nd[1002]["mirror_twin_root_id"])
        self.assertEqual(0, self.nd[1003]["mirror_twin_root_id"])
        self.assertEqual(2, self.nd[1001]["orphan_output_synapses"])
        self.assertEqual(0, self.nd[1001]["orphan_input_synapses"])

    def test_side_comes_from_the_classification_file(self):
        self.assertEqual("left", self.nd[1001]["side"])
        self.assertEqual("right", self.nd[1002]["side"])
        self.assertEqual("", self.nd[1003]["side"])

    def test_neurotransmitter_is_unknown(self):
        for nd in self.nd.values():
            self.assertEqual("UNKNOWN", nd["nt_type"])

    def test_connection_derived_attributes(self):
        nd = self.nd[1001]
        self.assertEqual(2, nd["input_cells"])
        self.assertEqual(3, nd["input_synapses"])
        self.assertEqual(["A1_R", "A3_L"], nd["input_neuropils"])
        self.assertEqual(2, nd["output_cells"])
        self.assertEqual(8, nd["output_synapses"])
        self.assertEqual(["A1_L", "BRAIN_L"], nd["output_neuropils"])
        self.assertEqual(5, self.nd[AGGREGATE_ID]["input_synapses"])
        self.assertEqual(0, self.nd[AGGREGATE_ID]["output_cells"])

    def test_connection_rows_keep_the_unknown_neurotransmitter(self):
        self.assertEqual(
            {
                (1001, 1002, "A1_L", 3, "UNKNOWN"),
                (1002, 1001, "A1_R", 2, "UNKNOWN"),
                (1001, AGGREGATE_ID, "BRAIN_L", 5, "UNKNOWN"),
                (1003, 1001, "A3_L", 1, "UNKNOWN"),
            },
            {tuple(r) for r in self.db.connections_.all_rows()},
        )
        self.assertEqual(4, len(self.db.cell_connections(1001)))

    def test_names_are_group_plus_number_and_aggregates_keep_their_name(self):
        self.assertEqual("MBON-a1.1", self.nd[1001]["name"])
        self.assertEqual("chos_v'ch_a1.1", self.nd[1002]["name"])
        self.assertEqual("A3_L.1", self.nd[1003]["name"])
        self.assertEqual(AGGREGATE_NAME, self.nd[AGGREGATE_ID]["name"])

    def test_grouped_synapse_counts(self):
        counts = self.db.grouped_synapse_counts["side"]
        self.assertEqual(3, counts[("left", "right")])
        self.assertEqual(2, counts[("right", "left")])
        self.assertEqual(5, counts[("left", "left")])
        self.assertEqual(1, counts[("", "left")])

    def test_there_are_no_community_labels(self):
        self.assertEqual({}, dict(self.db.label_data))
        for nd in self.nd.values():
            self.assertEqual([], nd["label"])


class InitializeNeuronDataValidationTest(TestCase):
    def build(self, mutate):
        rows = deepcopy(l1_rows())
        mutate(rows)
        return initialize_neuron_data(**initialize_kwargs(rows))

    def test_unexpected_header_raises(self):
        for table in l1_rows():
            rows = deepcopy(l1_rows())
            rows[table][0][0] = "bogus"
            with self.assertRaises(ValueError, msg=table):
                initialize_neuron_data(**initialize_kwargs(rows))

    def test_duplicate_neuron_raises(self):
        with self.assertRaises(ValueError):
            self.build(lambda r: r["neurons"].append(r["neurons"][1]))

    def test_connection_to_unknown_neuron_raises(self):
        def add(rows):
            rows["connections"].append(["1001", "999", "A1_L", "1", "UNKNOWN"])

        with self.assertRaises(ValueError):
            self.build(add)

    def test_unknown_region_raises(self):
        def add(rows):
            rows["connections"].append(["1001", "1003", "AL_L", "1", "UNKNOWN"])

        with self.assertRaises(ValueError):
            self.build(add)

    def test_unknown_neurotransmitter_raises(self):
        def add(rows):
            rows["connections"].append(["1001", "1003", "A1_L", "1", "XYZ"])

        with self.assertRaises(ValueError):
            self.build(add)

    def test_known_neurotransmitter_is_accepted(self):
        def add(rows):
            rows["connections"].append(["1001", "1003", "A1_L", "1", "ach"])

        db = self.build(add)
        self.assertEqual(["A1_L"], db.neuron_data[1003]["input_neuropils"])
        self.assertIn((1001, 1003, "A1_L", 1, "ACH"), {tuple(r) for r in db.connections_.all_rows()})

    def test_unknown_root_id_in_a_per_neuron_table_raises(self):
        for table, row in [
            ("cell_types", ["999", "KC", ""]),
            ("papers", ["999", "Some paper"]),
            ("annotations", ["999", "Some annotation"]),
            ("classification", ["999", "", "", "", "", "", "left", ""]),
            ("skeletons", ["999", "x", "1", "0", "0", "", "", "0", "", ""]),
        ]:
            rows = deepcopy(l1_rows())
            rows[table].append(row)
            with self.assertRaises(ValueError, msg=table):
                initialize_neuron_data(**initialize_kwargs(rows))

    def test_header_only_optional_tables_are_accepted(self):
        def clear(rows):
            for table in ["cell_types", "papers", "annotations", "connections"]:
                rows[table] = rows[table][:1]

        db = self.build(clear)
        self.assertEqual([], db.neuron_data[1001]["cell_type"])
        self.assertEqual(0, db.neuron_data[1001]["input_cells"])
