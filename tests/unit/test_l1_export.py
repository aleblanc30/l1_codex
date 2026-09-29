from unittest import TestCase

from codex.data.l1_export import (
    L1_EXPORT_SCHEMA,
    L1_REGIONS,
    NT_UNKNOWN,
    ORPHAN_ID_BASE,
    UNASSIGNED_REGION,
    aggregate_ids_in,
    assign_regions,
    build_connection_rows,
    build_export_tables,
    build_mirror_twins,
    cell_types_for,
    chunked,
    describe_aggregate,
    is_image_endpoint,
    normalize_side,
    orphan_aggregate_id,
    orphan_aggregate_name,
    papers_for,
    region_code,
)

SEGMENT_VOLUME_NAMES = (
    ["Brain Hemisphere left", "Brain Hemisphere right", "SEZ_left", "SEZ_right"]
    + [f"T{i}_{s}" for i in (1, 2, 3) for s in ("left", "right")]
    + [f"A{i}_{s}" for i in range(1, 9) for s in ("left", "right")]
)


class RegionCodeTest(TestCase):
    def test_segment_volumes_map_to_short_codes(self):
        self.assertEqual("A1_L", region_code("A1_left"))
        self.assertEqual("A8_R", region_code("A8_right"))
        self.assertEqual("T3_L", region_code("T3_left"))
        self.assertEqual("SEZ_R", region_code("SEZ_right"))
        self.assertEqual("BRAIN_L", region_code("Brain Hemisphere left"))
        self.assertEqual("BRAIN_R", region_code("Brain Hemisphere right"))

    def test_whole_cns_volume_has_no_region(self):
        self.assertIsNone(region_code("cns"))

    def test_unrecognized_volume_raises(self):
        with self.assertRaises(ValueError):
            region_code("mystery volume")

    def test_every_segment_volume_maps_to_a_known_region(self):
        for name in SEGMENT_VOLUME_NAMES:
            self.assertIn(region_code(name), L1_REGIONS, name)

    def test_regions_are_unique_and_end_with_unassigned(self):
        self.assertEqual(len(L1_REGIONS), len(set(L1_REGIONS)))
        self.assertEqual(UNASSIGNED_REGION, L1_REGIONS[-1])
        self.assertEqual(26 + 1, len(L1_REGIONS))


class AssignRegionsTest(TestCase):
    def test_point_in_one_volume_gets_that_region(self):
        containment = {"A1_L": [True, False], "A1_R": [False, True]}
        self.assertEqual(["A1_L", "A1_R"], assign_regions(2, containment))

    def test_point_in_no_volume_is_unassigned(self):
        self.assertEqual([UNASSIGNED_REGION], assign_regions(1, {"A1_L": [False]}))

    def test_overlap_is_resolved_by_region_order(self):
        containment = {"SEZ_L": [True], "BRAIN_L": [True]}
        self.assertEqual(["BRAIN_L"], assign_regions(1, containment))

    def test_no_points_gives_empty_list(self):
        self.assertEqual([], assign_regions(0, {"A1_L": []}))

    def test_unknown_region_key_raises(self):
        with self.assertRaises(ValueError):
            assign_regions(1, {"NOT_A_REGION": [True]})


class NormalizeSideTest(TestCase):
    def test_spelling_variants_are_merged(self):
        for variant in ["Left", "left", "LEFT", "L", "l"]:
            self.assertEqual("left", normalize_side([variant, "other"]), variant)
        for variant in ["Right", "right", "RIGHT", "R", "r"]:
            self.assertEqual("right", normalize_side([variant]), variant)

    def test_no_side_annotation_gives_empty(self):
        self.assertEqual("", normalize_side(["Brain", "contralateral"]))

    def test_conflicting_sides_give_empty(self):
        self.assertEqual("", normalize_side(["Left", "right"]))


class AnnotationSelectionTest(TestCase):
    def test_papers_are_intersection_sorted(self):
        annotations = ["Winding, Pedigo et al. 2023", "TODO", "Zwart et al. 2016"]
        papers = {"Zwart et al. 2016", "Winding, Pedigo et al. 2023", "Other 2020"}
        self.assertEqual(
            ["Winding, Pedigo et al. 2023", "Zwart et al. 2016"],
            papers_for(annotations, papers),
        )

    def test_cell_types_keep_original_text_exactly(self):
        annotations = ["MBON-a1", "v'pda, class III", "DAN-c1 ", "Brain"]
        types = {"MBON-a1", "v'pda, class III", "DAN-c1 "}
        self.assertEqual(
            ["DAN-c1 ", "MBON-a1", "v'pda, class III"],
            cell_types_for(annotations, types),
        )

    def test_no_matches_gives_empty_list(self):
        self.assertEqual([], cell_types_for(["Brain"], {"KC"}))
        self.assertEqual([], papers_for([], {"KC"}))


class MirrorTwinTest(TestCase):
    def test_hemilateral_pair_is_symmetric(self):
        ann = {1: ["hemilateral_pair_1_2"], 2: ["hemilateral_pair_1_2"], 3: []}
        self.assertEqual({1: 2, 2: 1}, build_mirror_twins(ann))

    def test_pair_with_id_outside_the_set_is_ignored(self):
        ann = {1: ["hemilateral_pair_1_99"], 2: []}
        self.assertEqual({}, build_mirror_twins(ann))

    def test_paired_with_annotation_fills_unpaired_neurons(self):
        ann = {5: ["paired with #7"], 7: []}
        self.assertEqual({5: 7, 7: 5}, build_mirror_twins(ann))

    def test_hemilateral_pairs_take_precedence_over_paired_with(self):
        ann = {
            5: ["paired with #7"],
            7: ["hemilateral_pair_7_8"],
            8: ["hemilateral_pair_7_8"],
        }
        self.assertEqual({7: 8, 8: 7}, build_mirror_twins(ann))

    def test_self_reference_is_ignored(self):
        self.assertEqual({}, build_mirror_twins({4: ["paired with #4"]}))

    def test_result_is_always_symmetric(self):
        ann = {i: [f"paired with #{i + 1}"] for i in range(1, 6)}
        twins = build_mirror_twins(ann)
        for a, b in twins.items():
            self.assertEqual(a, twins[b])


class OrphanAggregateTest(TestCase):
    def test_ids_are_distinct_and_above_real_ids(self):
        ids = {
            orphan_aggregate_id(role, region)
            for role in ("pre", "post")
            for region in L1_REGIONS
        }
        self.assertEqual(2 * len(L1_REGIONS), len(ids))
        self.assertTrue(all(i >= ORPHAN_ID_BASE for i in ids))

    def test_ids_are_stable(self):
        self.assertEqual(
            orphan_aggregate_id("post", "A1_L"), orphan_aggregate_id("post", "A1_L")
        )

    def test_describe_is_inverse_of_id(self):
        for role in ("pre", "post"):
            for region in L1_REGIONS:
                agg = orphan_aggregate_id(role, region)
                self.assertEqual((role, region), describe_aggregate(agg))

    def test_describe_rejects_real_ids(self):
        with self.assertRaises(ValueError):
            describe_aggregate(12345)

    def test_invalid_role_or_region_raises(self):
        with self.assertRaises(ValueError):
            orphan_aggregate_id("both", "A1_L")
        with self.assertRaises(ValueError):
            orphan_aggregate_id("pre", "NOPE")

    def test_names_describe_role_and_region(self):
        self.assertEqual(
            "orphaned synaptic sites (postsynaptic), A1_L",
            orphan_aggregate_name("post", "A1_L"),
        )
        self.assertEqual(
            "orphaned synaptic sites (presynaptic), BRAIN_R",
            orphan_aggregate_name("pre", "BRAIN_R"),
        )


class ConnectionRowsTest(TestCase):
    REAL = {1, 2, 3}

    def rows(self, connectors, regions):
        return build_connection_rows(connectors, regions, self.REAL)

    def test_real_to_real_synapses_are_counted_per_region(self):
        connectors = [
            {"connector_id": 10, "pre": 1, "posts": [2]},
            {"connector_id": 11, "pre": 1, "posts": [2]},
            {"connector_id": 12, "pre": 1, "posts": [2]},
        ]
        regions = {10: "A1_L", 11: "A1_L", 12: "SEZ_L"}
        rows, stats, skipped = self.rows(connectors, regions)
        self.assertEqual(
            [[1, 2, "A1_L", 2, NT_UNKNOWN], [1, 2, "SEZ_L", 1, NT_UNKNOWN]],
            sorted(rows, key=lambda r: r[2]),
        )
        self.assertEqual({}, stats)
        self.assertEqual({"no_presynaptic_partner": 0, "both_orphan": 0}, skipped)

    def test_polyadic_connector_creates_one_row_per_post_partner(self):
        connectors = [{"connector_id": 10, "pre": 1, "posts": [2, 3]}]
        rows, _, _ = self.rows(connectors, {10: "A1_L"})
        self.assertEqual({(1, 2), (1, 3)}, {(r[0], r[1]) for r in rows})

    def test_same_post_partner_twice_counts_two_synapses(self):
        connectors = [{"connector_id": 10, "pre": 1, "posts": [2, 2]}]
        rows, _, _ = self.rows(connectors, {10: "A1_L"})
        self.assertEqual(1, len(rows))
        self.assertEqual(2, rows[0][3])

    def test_orphan_post_partner_collapses_into_regional_aggregate(self):
        connectors = [
            {"connector_id": 10, "pre": 1, "posts": [900, 901]},
            {"connector_id": 11, "pre": 1, "posts": [902]},
        ]
        regions = {10: "A1_L", 11: "A1_L"}
        rows, stats, _ = self.rows(connectors, regions)
        agg = orphan_aggregate_id("post", "A1_L")
        self.assertEqual([[1, agg, "A1_L", 3, NT_UNKNOWN]], rows)
        self.assertEqual({1: {"orphan_output": 3, "orphan_input": 0}}, stats)

    def test_orphan_pre_partner_collapses_into_regional_aggregate(self):
        connectors = [{"connector_id": 10, "pre": 900, "posts": [2, 3]}]
        rows, stats, _ = self.rows(connectors, {10: "SEZ_R"})
        agg = orphan_aggregate_id("pre", "SEZ_R")
        self.assertEqual(
            {(agg, 2, "SEZ_R", 1), (agg, 3, "SEZ_R", 1)},
            {tuple(r[:4]) for r in rows},
        )
        self.assertEqual(1, stats[2]["orphan_input"])
        self.assertEqual(1, stats[3]["orphan_input"])

    def test_connector_without_region_is_unassigned(self):
        rows, _, _ = self.rows([{"connector_id": 10, "pre": 1, "posts": [2]}], {})
        self.assertEqual(UNASSIGNED_REGION, rows[0][2])

    def test_connectors_without_presynaptic_partner_are_skipped_and_counted(self):
        connectors = [{"connector_id": 10, "pre": None, "posts": [2]}]
        rows, stats, skipped = self.rows(connectors, {10: "A1_L"})
        self.assertEqual([], rows)
        self.assertEqual(1, skipped["no_presynaptic_partner"])

    def test_orphan_to_orphan_connectors_are_skipped_and_counted(self):
        connectors = [{"connector_id": 10, "pre": 900, "posts": [901]}]
        rows, stats, skipped = self.rows(connectors, {10: "A1_L"})
        self.assertEqual([], rows)
        self.assertEqual({}, stats)
        self.assertEqual(1, skipped["both_orphan"])

    def test_aggregate_ids_in_rows_are_reported(self):
        connectors = [
            {"connector_id": 10, "pre": 1, "posts": [900]},
            {"connector_id": 11, "pre": 901, "posts": [2]},
        ]
        rows, _, _ = self.rows(connectors, {10: "A1_L", 11: "A2_R"})
        self.assertEqual(
            sorted(
                [
                    orphan_aggregate_id("post", "A1_L"),
                    orphan_aggregate_id("pre", "A2_R"),
                ]
            ),
            aggregate_ids_in(rows),
        )


class ExportTablesTest(TestCase):
    def setUp(self):
        self.summaries = [
            {
                "skeleton_id": 2,
                "name": "neuron, two",
                "node_count": 500,
                "cable_length_nm": 12345.6,
                "has_soma": True,
                "position_xyz": (10, 20, 30),
                "soma_region": "A1_R",
            },
            {
                "skeleton_id": 1,
                "name": "neuron one",
                "node_count": 20,
                "cable_length_nm": 99.0,
                "has_soma": False,
                "position_xyz": (1, 2, 3),
                "soma_region": None,
            },
        ]
        self.annotations = {
            1: ["Left", "Zwart et al. 2016", "3"],
            2: ["right", "MBON-a1", "Winding, Pedigo et al. 2023"],
        }
        agg = orphan_aggregate_id("post", "A1_L")
        self.rows = [
            [1, 2, "A1_L", 4, NT_UNKNOWN],
            [1, agg, "A1_L", 3, NT_UNKNOWN],
        ]
        self.stats = {1: {"orphan_output": 3, "orphan_input": 0}}
        self.tables = build_export_tables(
            summaries=self.summaries,
            annotations=self.annotations,
            paper_names={"Zwart et al. 2016", "Winding, Pedigo et al. 2023"},
            cell_type_names={"MBON-a1"},
            connection_rows=self.rows,
            orphan_stats=self.stats,
            twins={1: 2, 2: 1},
        )
        self.agg = agg

    def test_every_table_starts_with_its_schema_header(self):
        self.assertEqual(set(L1_EXPORT_SCHEMA), set(self.tables))
        for fname, cols in L1_EXPORT_SCHEMA.items():
            self.assertEqual(cols, self.tables[fname][0], fname)

    def test_rows_match_header_width(self):
        for fname, rows in self.tables.items():
            for r in rows:
                self.assertEqual(len(L1_EXPORT_SCHEMA[fname]), len(r), fname)

    def test_neurons_list_real_ids_sorted_then_used_aggregates(self):
        ids = [r[0] for r in self.tables["neurons.csv.gz"][1:]]
        self.assertEqual([1, 2, self.agg], ids)

    def test_neurotransmitter_is_unknown_for_everyone(self):
        nt_col = L1_EXPORT_SCHEMA["neurons.csv.gz"].index("nt_type")
        for r in self.tables["neurons.csv.gz"][1:]:
            self.assertEqual(NT_UNKNOWN, r[nt_col])

    def test_group_prefers_cell_type_then_soma_region(self):
        g = L1_EXPORT_SCHEMA["neurons.csv.gz"].index("group")
        by_id = {r[0]: r[g] for r in self.tables["neurons.csv.gz"][1:]}
        self.assertEqual("MBON-a1", by_id[2])
        self.assertEqual(UNASSIGNED_REGION, by_id[1])

    def test_side_is_normalized_and_aggregates_take_it_from_region(self):
        s = L1_EXPORT_SCHEMA["classification.csv.gz"].index("side")
        by_id = {r[0]: r[s] for r in self.tables["classification.csv.gz"][1:]}
        self.assertEqual("left", by_id[1])
        self.assertEqual("right", by_id[2])
        self.assertEqual("left", by_id[self.agg])

    def test_cell_types_are_one_row_per_type_verbatim(self):
        self.assertEqual([[2, "MBON-a1", ""]], self.tables["cell_types.csv.gz"][1:])

    def test_papers_are_one_row_per_paper(self):
        self.assertEqual(
            [[1, "Zwart et al. 2016"], [2, "Winding, Pedigo et al. 2023"]],
            self.tables["papers.csv.gz"][1:],
        )

    def test_raw_annotations_keep_numeric_labels(self):
        rows = self.tables["annotations.csv.gz"][1:]
        self.assertIn([1, "3"], rows)
        self.assertEqual(6, len(rows))

    def test_skeleton_rows_carry_measurements_twin_and_orphan_counts(self):
        cols = L1_EXPORT_SCHEMA["skeletons.csv.gz"]
        by_id = {r[0]: dict(zip(cols, r)) for r in self.tables["skeletons.csv.gz"][1:]}
        n2 = by_id[2]
        self.assertEqual("neuron, two", n2["skeleton_name"])
        self.assertEqual(500, n2["node_count"])
        self.assertEqual(1, n2["has_soma"])
        self.assertEqual(12346, n2["length_nm"])
        self.assertEqual("10 20 30", n2["position"])
        self.assertEqual(1, n2["mirror_twin_root_id"])
        self.assertEqual(0, n2["is_aggregate"])
        n1 = by_id[1]
        self.assertEqual(0, n1["has_soma"])
        self.assertEqual(3, n1["orphan_output_synapses"])
        self.assertEqual(0, n1["orphan_input_synapses"])

    def test_aggregate_skeleton_row_is_flagged_and_named(self):
        cols = L1_EXPORT_SCHEMA["skeletons.csv.gz"]
        by_id = {r[0]: dict(zip(cols, r)) for r in self.tables["skeletons.csv.gz"][1:]}
        agg = by_id[self.agg]
        self.assertEqual(1, agg["is_aggregate"])
        self.assertEqual(
            "orphaned synaptic sites (postsynaptic), A1_L", agg["skeleton_name"]
        )

    def test_connections_are_passed_through_with_header(self):
        self.assertEqual(self.rows, self.tables["connections.csv.gz"][1:])


class ImageEndpointGuardTest(TestCase):
    def test_tracing_endpoints_are_allowed(self):
        base = "https://l1em.catmaid.virtualflybrain.org/1"
        for path in [
            "skeletons/",
            "skeletons/?nodecount_gt=10",
            "annotations/",
            "annotations/query-targets",
            "volumes/",
            "volumes/12/",
            "connectors/",
            "skeletons/12/compact-detail",
        ]:
            self.assertFalse(is_image_endpoint(f"{base}/{path}"), path)

    def test_image_and_tile_endpoints_are_blocked(self):
        base = "https://l1em.catmaid.virtualflybrain.org"
        for path in [
            "1/stack/3/info",
            "1/stacks/",
            "tile-data/3/0/0/0.jpg",
            "1/tiles/3/1_0_0.png",
            "1/image/crop",
            "1/cutout/0/0/0",
        ]:
            self.assertTrue(is_image_endpoint(f"{base}/{path}"), path)


class ChunkedTest(TestCase):
    def test_splits_into_fixed_size_batches(self):
        self.assertEqual([[1, 2], [3, 4], [5]], list(chunked([1, 2, 3, 4, 5], 2)))

    def test_empty_input_gives_no_batches(self):
        self.assertEqual([], list(chunked([], 3)))

    def test_non_positive_size_raises(self):
        with self.assertRaises(ValueError):
            list(chunked([1], 0))
