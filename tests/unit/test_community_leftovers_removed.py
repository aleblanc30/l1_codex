import importlib
import inspect
from unittest import TestCase

from codex.blueprints.base import jinja_env
from codex.data import sorting
from codex.data.neuron_data import NEURON_SEARCH_TEXT_ATTRIBUTES, NeuronDB
from codex.data.neuron_data_initializer import (
    NEURON_DATA_ATTRIBUTE_TYPES,
    initialize_neuron_data,
)
from codex.data.structured_search_filters import SEARCH_ATTRIBUTE_NAMES
from codex.utils import graph_vis
from tests.l1_fixture import initialize_kwargs


class LabelCodeRemovedTest(TestCase):
    @classmethod
    def setUpClass(cls):
        cls.db = initialize_neuron_data(**initialize_kwargs())

    def test_label_and_marker_are_no_cell_attributes(self):
        for name in ("label", "marker"):
            self.assertNotIn(name, NEURON_DATA_ATTRIBUTE_TYPES)
            for nd in self.db.neuron_data.values():
                self.assertNotIn(name, nd)

    def test_they_are_no_search_attributes(self):
        for name in ("label", "marker"):
            self.assertNotIn(name, SEARCH_ATTRIBUTE_NAMES)
        self.assertNotIn("label", NEURON_SEARCH_TEXT_ATTRIBUTES)

    def test_the_label_methods_are_gone(self):
        for name in (
            "get_label_data",
            "label_data_for_ids",
            "cell_ids_with_label_data",
            "labels_ingestion_timestamp",
            "num_labels",
            "get_links",
        ):
            self.assertFalse(hasattr(NeuronDB, name), name)

    def test_the_database_holds_no_label_data(self):
        self.assertFalse(hasattr(self.db, "label_data"))
        self.assertFalse(hasattr(self.db, "meta_data"))
        parameters = inspect.signature(NeuronDB.__init__).parameters
        self.assertNotIn("label_data", parameters)
        self.assertNotIn("labels_file_timestamp", parameters)

    def test_the_label_cleaning_module_is_gone(self):
        with self.assertRaises(ImportError):
            importlib.import_module("codex.utils.label_cleaning")

    def test_the_explore_page_has_no_label_category(self):
        captions = " ".join(c["caption"] for c in self.db.categories(top_values=10))
        self.assertNotIn("Community", captions)

    def test_typed_cells_are_counted_by_cell_type(self):
        self.assertEqual(2, self.db.num_typed_cells())
        self.assertFalse(hasattr(NeuronDB, "num_typed_or_identified_cells"))

    def test_sorting_needs_no_label_counts(self):
        self.assertNotIn(
            "label_count_getter",
            inspect.signature(sorting.sort_search_results).parameters,
        )
        self.assertFalse(hasattr(sorting, "ITEM_COUNT"))

    def test_a_structured_query_keeps_the_search_order(self):
        self.assertIsNone(sorting.infer_sort_by("side == left"))

    def test_network_nodes_take_no_label_getter(self):
        self.assertNotIn(
            "label_getter", inspect.signature(graph_vis.make_graph_html).parameters
        )


class OpenSourceSwitchRemovedTest(TestCase):
    def test_the_flag_is_gone(self):
        self.assertNotIn("is_oss", jinja_env.globals)

    def test_no_template_depends_on_it(self):
        for name in jinja_env.list_templates():
            source = jinja_env.loader.get_source(jinja_env, name)[0]
            self.assertNotIn("is_oss", source, name)
