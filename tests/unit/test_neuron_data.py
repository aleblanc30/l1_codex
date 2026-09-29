import os
import string
from collections import defaultdict
from unittest import TestCase

from codex.data.auto_naming import assign_names_from_annotations
from codex.data.brain_regions import REGIONS, HEMISPHERES
from codex.data.local_data_loader import (
    read_csv,
)
from codex.data.neuron_data_initializer import (
    NEURON_DATA_ATTRIBUTE_TYPES,
)
from codex.data.structured_search_filters import STRUCTURED_SEARCH_ATTRIBUTES
from codex.data.versions import (
    DEFAULT_DATA_SNAPSHOT_VERSION,
)
from codex.utils.formatting import (
    make_web_safe,
    is_proper_textual_annotation,
)
from codex.utils.parsing import tokenize
from tests import TEST_DATA_ROOT_PATH, log_dev_url_for_root_ids, get_testing_neuron_db
from codex.data.neurotransmitters import (
    NEURO_TRANSMITTER_CHOICES,
    NEURO_TRANSMITTER_NAMES,
)


class NeuronDataTest(TestCase):
    @classmethod
    def setUpClass(cls):
        cls.neuron_db = get_testing_neuron_db()

    def all_annotations(self):
        for nd in self.neuron_db.neuron_data.values():
            for attrib_name, attrib_value in nd.items():
                if isinstance(attrib_value, dict):
                    for k, v in attrib_value.items():
                        yield attrib_name, k
                        yield attrib_name, v
                elif isinstance(attrib_value, list) or isinstance(attrib_value, set):
                    for v in attrib_value:
                        yield attrib_name, v
                else:
                    yield attrib_name, attrib_value

    def test_index_data(self):
        # 5,013 skeletons plus the 54 aggregate nodes for orphaned synaptic sites
        self.assertEqual(5013 + 54, len(self.neuron_db.neuron_data))

        def check_num_values_missing(attrib, expected_count):
            num_missing = len(
                [1 for nd in self.neuron_db.neuron_data.values() if not nd[attrib]]
            )
            self.assertLessEqual(
                num_missing,
                expected_count,
                f"Too many missing values for attribute: {attrib}",
            )

        # Attributes that the L1 export does not fill are missing for every cell
        everything = len(self.neuron_db.neuron_data)
        expected_missing_value_bounds = {
            "mirror_twin_root_id": 3900,
            "similar_cell_scores": everything,
            "nt_type_score": everything,
            "ach_avg": everything,
            "da_avg": everything,
            "gaba_avg": everything,
            "glut_avg": everything,
            "oct_avg": everything,
            "ser_avg": everything,
            "flow": everything,
            "super_class": everything,
            "class": everything,
            "sub_class": everything,
            "hemilineage": everything,
            "nerve": everything,
            "connectivity_tag": everything,
            "area_nm": everything,
            "size_nm": everything,
            "cell_type": 3900,
            "side": 3600,
            "papers": 54,
            "annotations": 54,
            "position": 54,
            "length_nm": 54,
            "node_count": 54,
            "has_soma": 800,
            "is_aggregate": 5013,
            "input_cells": 950,
            "input_neuropils": 950,
            "input_synapses": 950,
            "total_input_synapses": 950,
            "output_cells": 1200,
            "output_neuropils": 1200,
            "output_synapses": 1200,
            "total_output_synapses": 1200,
            "orphan_output_synapses": 1400,
            "orphan_input_synapses": 1650,
        }

        for k in NEURON_DATA_ATTRIBUTE_TYPES.keys():
            check_num_values_missing(k, expected_missing_value_bounds.get(k, 0))

    def test_annotations_web_safe(self):
        # Names, cell types and annotations are kept verbatim (quotes, apostrophes and so on), and the pages
        # escape them when they render (see test_html_escaping*). What is checked here is that the stored
        # attributes are trimmed and free of control characters, and that verbatim really means unchanged.
        # Raw annotations are working notes of the CATMAID users, so they are excluded.
        verbatim_examples = 0
        for attrib_name, attrib_value in self.all_annotations():
            if not isinstance(attrib_value, str):
                continue
            if attrib_value != make_web_safe(attrib_value):
                verbatim_examples += 1
            if attrib_name == "annotations":
                continue
            self.assertEqual(
                attrib_value.strip(),
                attrib_value,
                f"Untrimmed text '{attrib_value}' for attribute '{attrib_name}'",
            )
            self.assertTrue(
                attrib_value.isprintable(),
                f"Control characters in '{attrib_value!r}' for attribute '{attrib_name}'",
            )
        self.assertGreater(verbatim_examples, 0)

    def test_annotations_meaningful(self):
        # nt_type is the UNKNOWN placeholder until a curated table exists, and the raw annotations are working
        # notes of the CATMAID users, some of them numeric or symbols only
        excluded_attributes = ["position", "nt_type", "annotations"]
        empty_vals, nonempty_vals = 0, 0
        for attrib_name, attrib_value in self.all_annotations():
            self.assertIsNotNone(
                attrib_value,
                f"Annotation is absent ('{attrib_value}') for attribute '{attrib_name}'",
            )
            if attrib_value == "":
                empty_vals += 1
                continue
            nonempty_vals += 1
            if not isinstance(attrib_value, str) or attrib_name in excluded_attributes:
                continue
            self.assertTrue(
                is_proper_textual_annotation(attrib_value),
                f"Meaningless annotation '{attrib_value}' for attribute '{attrib_name}'",
            )

        # Attributes the export does not fill are empty for every cell (flow, class, hemilineage and others)
        self.assertGreater(
            nonempty_vals, 2 * empty_vals, f"Too many empty annotations: {empty_vals}"
        )

    def test_annotations(self):
        neurons_with_cell_types = [
            n for n in self.neuron_db.neuron_data.values() if n["cell_type"]
        ]
        self.assertEqual(1203, len(neurons_with_cell_types))

        neurons_with_papers = [
            n for n in self.neuron_db.neuron_data.values() if n["papers"]
        ]
        self.assertEqual(5013, len(neurons_with_papers))

        for n in self.neuron_db.neuron_data.values():
            for col in [
                "input_neuropils",
                "output_neuropils",
                "cell_type",
                "papers",
                "position",
            ]:
                self.assertEqual(len(set(n[col])), len(n[col]))
            self.assertEqual(len(n["papers"]) > 0, not n["is_aggregate"])

        # closest term search
        self.assertEqual(
            self.neuron_db.closest_token("mpnn", case_sensitive=False), ("mpn", 1)
        )
        self.assertEqual(
            self.neuron_db.closest_token("blobe", case_sensitive=False), ("alone", 2)
        )

        # don't suggest in structured queries
        self.assertEqual(
            self.neuron_db.closest_token("BLO==BE", case_sensitive=True), (None, None)
        )
        self.assertEqual(
            self.neuron_db.closest_token("BLOBE && Lb3", case_sensitive=False),
            (None, None),
        )
        # nor for cell ids
        self.assertEqual(
            self.neuron_db.closest_token("12345", case_sensitive=False), (None, None)
        )

    def test_search(self):
        # search results
        self.assertEqual(225, len(self.neuron_db.search("kc")))
        self.assertEqual(445, len(self.neuron_db.search("da")))
        self.assertEqual(0, len(self.neuron_db.search("dadadeadbeef")))
        # word prefixes and substrings of skeleton names, cell types and papers
        self.assertGreater(len(self.neuron_db.search("Eichler")), 300)

    def test_structured_search(self):
        # structured search
        unknown_rids = self.neuron_db.search("nt_type == unknown")
        self.assertEqual(5013, len(unknown_rids))  # aggregates are left out of results
        self.assertEqual(0, len(self.neuron_db.search("nt_type != unknown")))
        for rid in unknown_rids:
            self.assertEqual("UNKNOWN", self.neuron_db.get_neuron_data(rid)["nt_type"])

        # a transmitter that no neuron has yet
        self.assertEqual(0, len(self.neuron_db.search("nt_type == ACH")))
        self.assertEqual(
            len(unknown_rids), len(self.neuron_db.search("nt_type != ACH"))
        )

        left_rids = self.neuron_db.search("side == left")
        right_rids = self.neuron_db.search("side == right")
        self.assertEqual(787, len(left_rids))
        self.assertEqual(0, len(self.neuron_db.search("side == left && side == right")))
        left_or_right_rids = self.neuron_db.search("side == left || side == right")
        self.assertEqual(len(left_rids) + len(right_rids), len(left_or_right_rids))

        ids_with_name = self.neuron_db.search("{has} name")
        ids_without_name = self.neuron_db.search("{not} name")
        self.assertEqual(5013, len(ids_with_name))
        self.assertEqual(0, len(ids_without_name))

        ids_with_cell_type = self.neuron_db.search("$$ cell_type")
        ids_without_cell_type = self.neuron_db.search("!$ cell_type")
        self.assertEqual(1203, len(ids_with_cell_type))
        self.assertEqual(
            len(self.neuron_db.search("{has} name")),
            len(ids_with_cell_type) + len(ids_without_cell_type),
        )
        self.assertEqual(
            set(ids_with_cell_type),
            set(
                [
                    nd["root_id"]
                    for nd in self.neuron_db.neuron_data.values()
                    if nd["cell_type"] and not nd["is_aggregate"]
                ]
            ),
        )

    def test_structured_search_case(self):
        # case sensitive vs insensitive search
        self.assertEqual(
            223, len(self.neuron_db.search("cell_type == kc", case_sensitive=False))
        )
        self.assertEqual(
            0, len(self.neuron_db.search("cell_type == kc", case_sensitive=True))
        )
        self.assertEqual(
            223, len(self.neuron_db.search("cell_type == KC", case_sensitive=True))
        )

        # starts with op
        self.assertEqual(808, len(self.neuron_db.search("cell_type {starts_with} M")))
        self.assertEqual(808, len(self.neuron_db.search("cell_type {starts_with} m")))
        self.assertEqual(
            42,
            len(
                self.neuron_db.search("cell_type {starts_with} m", case_sensitive=True)
            ),
        )
        self.assertEqual(232, len(self.neuron_db.search("id {starts_with} 2")))

    def test_structured_search_lists(self):
        # explicit searches
        many_root_ids = list(self.neuron_db.neuron_data.keys())[:30]
        root_id_search_explicit = self.neuron_db.search(
            " || ".join([f"id == {rid}" for rid in many_root_ids])
        )
        self.assertEqual(set(root_id_search_explicit), set(many_root_ids))
        root_id_search_membership = self.neuron_db.search(
            f"id << {','.join([str(rid) for rid in many_root_ids])}"
        )
        self.assertEqual(set(root_id_search_explicit), set(root_id_search_membership))
        self.assertEqual(
            len(self.neuron_db.neuron_data),
            len(many_root_ids)
            + len(
                self.neuron_db.search(
                    " && ".join([f"id != {rid}" for rid in many_root_ids])
                )
            ),
        )
        self.assertEqual(
            len(self.neuron_db.neuron_data),
            len(many_root_ids)
            + len(
                self.neuron_db.search(
                    f"id !< {','.join([str(rid) for rid in many_root_ids])}"
                )
            ),
        )

    def test_structured_search_misc(self):
        self.assertEqual(0, len(self.neuron_db.search("kc && nt_type != unknown")))

        # a single number that is a cell id finds that cell only
        self.assertEqual([29], self.neuron_db.search("29"))
        for query in ["29 11995", "29,11995", "29, 11995"]:
            found = self.neuron_db.search(query)
            self.assertIn(29, found, query)
            self.assertIn(11995, found, query)
        self.assertEqual([29, 11995], sorted(self.neuron_db.search("id << 29,11995")))

    def test_structured_search_operator_combos(self):
        # {and} chains free form terms, as && does
        self.assertEqual(
            224, len(self.neuron_db.search("kc {and} Winding && nt_type != gaba"))
        )
        self.assertEqual(
            109, len(self.neuron_db.search("kc {and} Winding && side == left"))
        )
        self.assertEqual(
            115, len(self.neuron_db.search("kc {and} Winding && side != left"))
        )

    def test_downstream_upstream_queries(self):
        rid = 29  # a Kenyon cell
        self.assertEqual("KC", self.neuron_db.get_neuron_data(rid)["cell_type"][0])
        downstream = self.neuron_db.search("{downstream} " + str(rid))
        self.assertEqual(87, len(downstream))

        upstream = self.neuron_db.search("{upstream} " + str(rid))
        self.assertEqual(69, len(upstream))

        reciprocal = self.neuron_db.search("{reciprocal} " + str(rid))
        self.assertEqual(41, len(reciprocal))

        # aggregate nodes never appear as partners
        for rids in (downstream, upstream, reciprocal):
            self.assertFalse(set(rids) & self.neuron_db.aggregate_ids)

    def test_neuropil_queries(self):
        self.assertEqual(
            2051, len(self.neuron_db.search("input_neuropil {equal} BRAIN_L"))
        )
        self.assertEqual(479, len(self.neuron_db.search("input_neuropil {equal} A1_L")))
        self.assertEqual(
            516, len(self.neuron_db.search("input_neuropil {in} A1_L,A2_L"))
        )

    def test_contains_queries(self):
        self.assertEqual(223, len(self.neuron_db.search("cell_type {contains} KC")))
        self.assertEqual(
            len(
                self.neuron_db.search(
                    "cell_type {contains} KC && cell_type {not_contains} KC"
                )
            ),
            0,
        )
        self.assertEqual(
            223,
            len(
                self.neuron_db.search(
                    "cell_type {contains} KC && cell_type {not_contains} mPN"
                )
            ),
        )

    def test_not_connected_cells(self):
        connected_cells = set(self.neuron_db.input_sets().keys()).union(
            set(self.neuron_db.output_sets().keys())
        )
        not_connected_cells = set(self.neuron_db.neuron_data.keys()) - connected_cells
        self.assertGreater(3500, len(not_connected_cells))

    def test_nt_score_stats(self):
        for nd in self.neuron_db.neuron_data.values():
            scores_list = [
                nd[f"{nt_type.lower()}_avg"] for nt_type in NEURO_TRANSMITTER_NAMES
            ]
            for s in scores_list:
                self.assertGreaterEqual(1, s)
                self.assertLessEqual(0, s)
            total = sum(scores_list)
            self.assertGreaterEqual(1.05, total)
            self.assertLessEqual(0.0, total, nd)

    def test_neuropils(self):
        res = set()
        for nd in self.neuron_db.neuron_data.values():
            for p in nd["input_neuropils"]:
                res.add(p)
            for p in nd["output_neuropils"]:
                res.add(p)
        self.assertEqual(set(REGIONS.keys()), res)

    def test_classes(self):
        # the export has no classes, sub classes, super classes, hemilineages or connectivity tags yet
        self.assertEqual([], self.neuron_db.unique_values("class"))

    def test_super_classes(self):
        self.assertEqual([], self.neuron_db.unique_values("super_class"))

    def test_sub_classes(self):
        self.assertEqual([], self.neuron_db.unique_values("sub_class"))

    def test_cell_types(self):
        # the MB nomenclature sub-annotations
        expected_list_length = 856
        self.assertEqual(
            expected_list_length, len(self.neuron_db.unique_values("cell_type"))
        )

    def test_hemilineage(self):
        self.assertEqual([], self.neuron_db.unique_values("hemilineage"))

    def test_connectivity_tag(self):
        self.assertEqual([], self.neuron_db.unique_values("connectivity_tag"))

    def test_sizes(self):
        # skeleton cable length is in the export, surface area and volume are not
        for nd in self.neuron_db.neuron_data.values():
            ln = nd["length_nm"]
            self.assertFalse(nd["area_nm"])
            self.assertFalse(nd["size_nm"])
            if nd["is_aggregate"]:
                self.assertEqual(0, ln)
            else:
                self.assertGreater(ln, 0)
                self.assertGreater(nd["node_count"], 0)

    def test_get_neuron_data(self):
        self.assertGreater(len(self.neuron_db.get_neuron_data(root_id=29)), 5)
        self.assertGreater(len(self.neuron_db.get_neuron_data(root_id="29")), 5)

    def test_thumbnails(self):
        # Run this first to collect existing skeleton root ids:
        # gsutil du gs://flywire-data/codex/skeleton_thumbnails | grep png | cut -d"/" -f 6 | cut -d "." -f 1 > static/raw_data/thumbnails_tmp.csv
        fname = f"{TEST_DATA_ROOT_PATH}/../raw_data/{DEFAULT_DATA_SNAPSHOT_VERSION}/thumbnails_tmp.csv"
        if os.path.isfile(fname):
            content = set([int(r[0]) for r in read_csv(fname)])
            self.assertEqual(
                [], [r for r in self.neuron_db.neuron_data.keys() if r not in content]
            )

    def test_attribute_coverage(self):
        # Attributes of the L1 export that are filled for most of the 5,013 skeletons.
        sparse_attrs = {
            "similar_cell_scores",
            "mirror_twin_root_id",
            "cell_type",
            "side",
            "is_aggregate",
            "has_soma",
            "input_cells",
            "input_synapses",
            "input_neuropils",
            "total_input_synapses",
            "output_cells",
            "output_synapses",
            "output_neuropils",
            "total_output_synapses",
            "orphan_output_synapses",
            "orphan_input_synapses",
        }
        # Attributes that the export does not provide (yet), so that they are empty for every cell
        empty_attrs = {
            "nt_type_score",
            "ach_avg",
            "da_avg",
            "gaba_avg",
            "glut_avg",
            "oct_avg",
            "ser_avg",
            "flow",
            "super_class",
            "class",
            "sub_class",
            "hemilineage",
            "nerve",
            "connectivity_tag",
            "area_nm",
            "size_nm",
        }
        num_cells = len(self.neuron_db.neuron_data)
        for k, v in NEURON_DATA_ATTRIBUTE_TYPES.items():
            num_vals = len([n[k] for n in self.neuron_db.neuron_data.values() if n[k]])
            if k in empty_attrs:
                self.assertEqual(0, num_vals, k)
            elif k in sparse_attrs:
                continue
            else:
                self.assertGreater(num_vals / num_cells, 0.85, k)

    def test_connection_filters(self):
        rid_list = sorted(self.neuron_db.neuron_data.keys())[:100]
        cons = self.neuron_db.connections(
            rid_list, induced=False, min_syn_count=5, nt_type="UNKNOWN"
        )
        self.assertGreater(len(cons), 0)
        for r in cons:
            self.assertTrue(r[0] in rid_list or r[1] in rid_list)
            self.assertGreaterEqual(r[3], 5)
            self.assertEqual("UNKNOWN", r[4])

        # no connection has a known transmitter yet
        self.assertEqual(
            0, len(self.neuron_db.connections(rid_list, induced=False, nt_type="GABA"))
        )

        rid_list = sorted(self.neuron_db.neuron_data.keys())[:2000]
        cons = self.neuron_db.connections(rid_list, induced=True)
        self.assertGreater(len(cons), 0)
        for r in cons:
            self.assertTrue(r[0] in rid_list and r[1] in rid_list)

    def test_connection_query_consistency(self):
        for rid in sorted(self.neuron_db.neuron_data.keys())[10000:10020]:
            cons1 = sorted(self.neuron_db.cell_connections(rid))
            cons2 = sorted(
                self.neuron_db.connections_._rows_from_predicates(
                    rids_predicate=lambda x, y: rid == x or rid == y
                )
            )
            self.assertEqual(cons1, cons2)

    def test_nt_types_consistency(self):
        # Every connection and every cell has the UNKNOWN transmitter until a curated table is provided
        for r in self.neuron_db.connections_.all_rows():
            self.assertTrue(r[4] in NEURO_TRANSMITTER_CHOICES.keys())
            self.assertEqual("UNKNOWN", r[4])
        for nd in self.neuron_db.neuron_data.values():
            self.assertEqual("UNKNOWN", nd["nt_type"])

    def test_find_similar_cells(self):
        cell_ids = sorted(self.neuron_db.neuron_data.keys())[1000:1020]
        similar_cell_scores = {}
        for cell_id in cell_ids:
            dct = self.neuron_db.get_similar_connectivity_cells(
                cell_id, with_same_attributes="side"
            )
            for k, v in dct.items():
                if k in cell_ids:
                    continue
                if k not in similar_cell_scores or v > similar_cell_scores[k]:
                    similar_cell_scores[k] = v
        self.assertGreater(len(similar_cell_scores), 0)
        # super_class is empty for every cell, so requiring it to match does not remove candidates
        for k in similar_cell_scores:
            self.assertIn(k, self.neuron_db.neuron_data)

    def test_dynamic_ranges(self):
        # Only attributes with values in the export have a range
        self.assertEqual(
            {
                "data_nt_type_range": ["UNKNOWN"],
                "data_side_range": ["left", "right"],
            },
            self.neuron_db.dynamic_ranges(),
        )

        for attr in STRUCTURED_SEARCH_ATTRIBUTES:
            if attr.name in ["input_neuropils", "output_neuropils"]:
                self.assertEqual(set(attr.value_range), set(REGIONS.keys()))
            elif attr.name in ["input_hemisphere", "output_hemisphere"]:
                self.assertEqual(set(attr.value_range), set(HEMISPHERES))
            else:
                data_range_key = f"data_{attr.name}_range"
                if not attr.value_range:
                    self.assertTrue(
                        data_range_key not in self.neuron_db.dynamic_ranges(), attr.name
                    )
                else:
                    # the values in the data are among the allowed ones (no cell is on the midline yet)
                    self.assertLessEqual(
                        set(self.neuron_db.dynamic_ranges().get(data_range_key, [])),
                        set(attr.value_range),
                        attr.name,
                    )

    def test_naming(self):
        all_nds = list(self.neuron_db.neuron_data.values())

        # all names are unique ignoring case
        self.assertEqual(len(set([nd["name"].lower() for nd in all_nds])), len(all_nds))

        # check names have 1 or 2 parts (and if 2, second is counter)
        for nd in all_nds:
            name_parts = nd["name"].split(".")
            suffix = name_parts[-1]

            # region based name
            if nd["name"] == nd["group"] or nd["name"].startswith(f'{nd["group"]}.'):
                group_parts = nd["group"].split(".")
                if len(name_parts) > len(group_parts):
                    self.assertEqual(len(name_parts), len(group_parts) + 1)
                    self.assertFalse(suffix in "LR", f'{nd["group"]} {nd["name"]}')
                    self.assertGreater(int(suffix), 0)
                continue

            base_name = name_parts[0]
            self.assertGreater(len(base_name), 1)
            if len(name_parts) == 2:
                self.assertTrue(suffix in ["L", "R"] or int(suffix) > 0)
            else:
                self.assertEqual(len(name_parts), 1, name_parts)

            # check forbidden substrings
            for fbd in [
                " ",
                ".",
                ",",
                "?",
                "ascending",
                "descending",
                "unclassified",
                "clone",
                "test",
                "odd",
                "putative",
                "fbbt_",
                "eye_",
                "murthy",
                "seung",
            ]:
                self.assertTrue(fbd not in base_name.lower())

        # Check that for pairs, L/R is used instead of running index.
        # Also check that for singleton basenames, no running index is appended
        base_name_to_neurons = defaultdict(list)
        for nd in self.neuron_db.neuron_data.values():
            if nd["name"] == nd["group"] or nd["name"].startswith(nd["group"] + "."):
                continue
            name_parts = nd["name"].split(".")
            if len(name_parts) == 2:
                base_name_to_neurons[name_parts[0]].append(nd)
            else:
                self.assertFalse(name_parts[-1] in ["L", "R"], name_parts)

        for n, lst in base_name_to_neurons.items():
            if len(lst) == 2:
                s0, s1 = lst[0]["side"], lst[1]["side"]
                if s0 != s1 and s0 in ["left", "right"] and s1 in ["left", "right"]:
                    self.assertEqual(
                        s0[0].upper(), lst[0]["name"].split(".")[-1], lst[0]["name"]
                    )
                    self.assertEqual(
                        s1[0].upper(), lst[1]["name"].split(".")[-1], lst[1]["name"]
                    )

        for bn, lst in base_name_to_neurons.items():
            if len(lst) == 1:
                self.assertFalse(
                    lst[0]["name"].split(".")[-1].isnumeric(), lst[0]["name"]
                )

    def test_alternative_naming(self):
        neuron_data = self.neuron_db.neuron_data
        old_names = {rid: nd["name"] for rid, nd in neuron_data.items()}
        assign_names_from_annotations(neuron_data)

        def strip_id(n):
            parts = n.split(".")
            if parts[-1].isnumeric():
                return ".".join(parts[:-1])
            else:
                return n

        diff_count = 0
        for rid, nd in neuron_data.items():
            if strip_id(old_names[rid]) != strip_id(nd["name"]):
                diff_count += 1
                log_dev_url_for_root_ids(f'{old_names[rid]} -> {nd["name"]}', [rid])
        self.assertEqual(0, diff_count)

    def test_connectivity_tags(self):
        ct_counts = defaultdict(int)
        for nd in self.neuron_db.neuron_data.values():
            for ct in nd["connectivity_tag"]:
                ct_counts[ct] += 1
        self.assertEqual({}, dict(ct_counts))
