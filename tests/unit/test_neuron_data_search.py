from copy import deepcopy
from unittest import TestCase

from codex.data.neuron_data_initializer import initialize_neuron_data
from tests.l1_fixture import AGGREGATE_ID, initialize_kwargs, l1_rows


class FreeTextSearchTest(TestCase):
    """Free-text search over the small fixture: 1001 MBON-a1, 1002 chos_v'ch_a1, 1003 A3_L fragment."""

    @classmethod
    def setUpClass(cls):
        cls.db = initialize_neuron_data(**initialize_kwargs())

    def search(self, query, **kwargs):
        return set(self.db.search(query, **kwargs))

    def test_whole_word_in_the_skeleton_name(self):
        self.assertEqual({1002}, self.search("a1r"))

    def test_prefix_of_a_word_in_the_skeleton_name(self):
        self.assertEqual({1002}, self.search("v'ch"))

    def test_substring_of_the_skeleton_name_ranks_the_full_match_first(self):
        # documents matching only some words of the query follow the full match
        self.assertEqual([1002, 1001], self.db.search("ch a1"))

    def test_skeleton_name_is_matched_whole_ignoring_case(self):
        self.assertEqual({1002}, self.search("V'CH A1R"))

    def test_word_of_a_cell_type_finds_all_its_members(self):
        self.assertEqual({1001}, self.search("MBON"))

    def test_cell_type_with_an_apostrophe(self):
        self.assertEqual({1002}, self.search("chos_v'ch_a1"))

    def test_cell_type_containing_a_comma(self):
        self.assertEqual({1002}, self.search("Second, type"))

    def test_paper_name_finds_the_cells_it_reconstructed(self):
        self.assertEqual({1001, 1002}, self.search("Winding"))
        self.assertEqual({1002}, self.search("Zwart"))

    def test_group_and_name_still_match(self):
        self.assertEqual({1003}, self.search("A3_L"))
        self.assertEqual({1003}, self.search("A3_L.1"))

    def test_raw_annotations_are_not_part_of_free_text_search(self):
        rows = deepcopy(l1_rows())
        rows["annotations"].append(["1003", "zzzunique annotation"])
        db = initialize_neuron_data(**initialize_kwargs(rows))
        self.assertEqual([], db.search("zzzunique"))
        self.assertEqual([1003], db.search("A3_L"))

    def test_whole_word_option_rejects_partial_words(self):
        self.assertEqual(set(), self.search("v'c", word_match=True))
        self.assertEqual({1002}, self.search("a1r", word_match=True))

    def test_a_number_that_is_a_cell_id_finds_that_cell_only(self):
        rows = deepcopy(l1_rows())
        rows["skeletons"][3][1] = "MBE1001 fragment"  # cell 1003, whose name contains the id 1001
        db = initialize_neuron_data(**initialize_kwargs(rows))
        self.assertEqual([1001], db.search("1001"))
        self.assertEqual([1001], db.search(" 1001 "))

    def test_a_number_that_is_not_a_cell_id_is_searched_as_text(self):
        rows = deepcopy(l1_rows())
        rows["skeletons"][3][1] = "MBE1004 fragment"  # 1004 is not a cell id
        db = initialize_neuron_data(**initialize_kwargs(rows))
        self.assertEqual([1003], db.search("1004"))
        self.assertEqual([1003], db.search("MBE100"))

    def test_star_lists_every_cell(self):
        self.assertEqual({1001, 1002, 1003, AGGREGATE_ID}, self.search("*"))
