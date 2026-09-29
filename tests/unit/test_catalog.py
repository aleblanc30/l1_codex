from collections import defaultdict
from unittest import TestCase

from codex.data import catalog
from codex.data.catalog import _CODEX_DATA_SCHEMA, get_data_schema
from codex.data.l1_export import L1_EXPORT_SCHEMA
from codex.data.neuron_data_initializer import NEURON_DATA_ATTRIBUTE_TYPES


class CatalogTest(TestCase):
    def test_column_intersections(self):
        col_counts = defaultdict(int)
        for cols in _CODEX_DATA_SCHEMA.values():
            for c in cols:
                col_counts[c] += 1
        for k, v in col_counts.items():
            if k == "root_id":  # all files but the connections file are keyed by root_id
                self.assertEqual(len(_CODEX_DATA_SCHEMA) - 1, v)
            elif k == "nt_type":
                self.assertEqual(2, v)
            else:
                self.assertEqual(1, v, k)

    def test_every_table_has_a_column_getter(self):
        getters = {
            "neurons": catalog.get_neurons_file_columns,
            "classification": catalog.get_classification_file_columns,
            "cell_types": catalog.get_cell_types_file_columns,
            "papers": catalog.get_papers_file_columns,
            "annotations": catalog.get_annotations_file_columns,
            "skeletons": catalog.get_skeletons_file_columns,
            "connections": catalog.get_connections_file_columns,
        }
        self.assertEqual(set(_CODEX_DATA_SCHEMA), set(getters))
        for table, getter in getters.items():
            self.assertEqual(_CODEX_DATA_SCHEMA[table], getter())

    def test_getters_return_copies(self):
        catalog.get_neurons_file_columns().append("bogus")
        get_data_schema()["neurons"].append("bogus")
        self.assertNotIn("bogus", _CODEX_DATA_SCHEMA["neurons"])

    def test_export_schema_is_derived_from_the_catalog(self):
        self.assertEqual(
            {f"{table}.csv.gz": cols for table, cols in _CODEX_DATA_SCHEMA.items()},
            L1_EXPORT_SCHEMA,
        )

    def test_columns_loaded_as_attributes_have_a_declared_type(self):
        for table in ["neurons", "classification", "skeletons"]:
            for col in _CODEX_DATA_SCHEMA[table]:
                if col != "root_id":
                    self.assertIn(col, NEURON_DATA_ATTRIBUTE_TYPES, (table, col))
