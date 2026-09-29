import re
from collections import defaultdict
from unittest import TestCase
from codex.data.brain_regions import (
    COLORS,
    HEMISPHERES,
    REGIONS,
    REGIONS_JSON,
    REGION_CATEGORIES,
    lookup_neuropil_set,
    match_to_neuropil,
    neuropil_description,
    neuropil_hemisphere,
    without_side_suffix,
)
from codex.data.l1_export import L1_REGIONS

ABDOMINAL = {f"A{i}_{s}" for i in range(1, 9) for s in "LR"}
THORACIC = {f"T{i}_{s}" for i in (1, 2, 3) for s in "LR"}


class RegionsTest(TestCase):
    def test_regions_follow_the_export_region_list(self):
        self.assertEqual(L1_REGIONS, list(REGIONS.keys()))

    def test_lookup_neuropil(self):
        for k in REGIONS.keys():
            self.assertEqual(k, match_to_neuropil(k))
            self.assertEqual(k, match_to_neuropil(k.lower()))
        self.assertEqual("A1_L", match_to_neuropil("first abdominal segment/left"))
        self.assertEqual({"A1_L", "A1_R"}, lookup_neuropil_set("first abdominal"))

    def test_lookup_neuropil_set_by_side(self):
        pil_set = lookup_neuropil_set("left")
        self.assertEqual(13, len(pil_set))
        for p in pil_set:
            self.assertTrue(p.endswith("_L"))

        pil_set = lookup_neuropil_set("right")
        self.assertEqual(13, len(pil_set))
        for p in pil_set:
            self.assertTrue(p.endswith("_R"))

        self.assertEqual({"UNASGD"}, lookup_neuropil_set("Center"))

    def test_lookup_neuropil_set_by_abbreviation(self):
        self.assertEqual({"SEZ_L", "SEZ_R"}, lookup_neuropil_set("sez"))
        self.assertEqual({"BRAIN_L", "BRAIN_R"}, lookup_neuropil_set("brain"))
        self.assertEqual({"A1_L", "A1_R"}, lookup_neuropil_set("A1"))
        self.assertEqual(THORACIC, lookup_neuropil_set("T"))

    def test_lookup_neuropil_set_by_description(self):
        self.assertEqual(ABDOMINAL, lookup_neuropil_set("abdominal"))
        self.assertEqual(
            {"T1_L", "T2_L", "T3_L"}, lookup_neuropil_set("thoracic left")
        )
        self.assertEqual({"SEZ_L", "SEZ_R"}, lookup_neuropil_set("subesophageal"))

    def test_neuropil_description(self):
        descriptions = set([neuropil_description(k) for k in REGIONS.keys()])
        self.assertEqual(len(REGIONS), len(descriptions))
        self.assertTrue(all(descriptions))
        self.assertEqual("left first abdominal segment", neuropil_description("A1_L"))
        self.assertEqual("right brain hemisphere", neuropil_description("BRAIN_R"))
        self.assertEqual("unassigned", neuropil_description("UNASGD"))

    def test_neuropil_categories(self):
        dct = defaultdict(list)
        for key, value in REGION_CATEGORIES.items():
            for pil in value:
                dct[pil].append(key)

        for p in REGIONS.keys():
            self.assertEqual(1, len(dct[p]), p)
            self.assertGreater(len(dct[p][0]), 5)

    def test_regions_json_lists_every_region_once_by_hemisphere(self):
        self.assertEqual(set(HEMISPHERES), set(REGIONS_JSON))
        listed = [
            region["id"]
            for hemisphere in REGIONS_JSON.values()
            for category in hemisphere
            for region in category["regions"]
        ]
        self.assertEqual(sorted(REGIONS), sorted(listed))

    def test_every_region_has_a_hex_color(self):
        self.assertEqual(set(REGIONS), set(COLORS))
        for region, color in COLORS.items():
            self.assertTrue(re.fullmatch(r"#[0-9a-f]{6}", color), region)

    def test_segment_ids_match_the_catmaid_volume_ids(self):
        ids = [v[0] for k, v in REGIONS.items() if k != "UNASGD"]
        self.assertEqual(len(ids), len(set(ids)))
        self.assertEqual(-1, REGIONS["UNASGD"][0])
        self.assertEqual(61, REGIONS["BRAIN_L"][0])
        self.assertEqual(80, REGIONS["SEZ_R"][0])
        self.assertEqual(83, REGIONS["A1_L"][0])
        self.assertEqual(98, REGIONS["A8_R"][0])
        self.assertEqual(102, REGIONS["T3_R"][0])

    def test_neuropil_hemisphere(self):
        for k in REGIONS.keys():
            if k.endswith("_L"):
                self.assertEqual("Left", neuropil_hemisphere(k))
            elif k.endswith("_R"):
                self.assertEqual("Right", neuropil_hemisphere(k))
            else:
                self.assertEqual("Center", neuropil_hemisphere(k))

    def test_without_side_suffix(self):
        for k in REGIONS.keys():
            if k.endswith("_L"):
                self.assertEqual(k.replace("_L", ""), without_side_suffix(k))
            elif k.endswith("_R"):
                self.assertEqual(k.replace("_R", ""), without_side_suffix(k))
            else:
                self.assertEqual(k, without_side_suffix(k))
