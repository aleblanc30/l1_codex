from unittest import TestCase

from codex.data.versions import (
    DEFAULT_DATA_SNAPSHOT_VERSION,
)
from codex.utils import stats
from tests import get_testing_neuron_db


class Test(TestCase):
    def test_format_for_display(self):
        self.assertEqual(
            {"d1": {"a": "6,555"}, "d2": {"b": None, "c": 0.55}},
            stats.format_for_display({"d1": {"a": 6555}, "d2": {"b": None, "c": 0.55}}),
        )

    def test_compile_data(self):
        # empty data
        caption, data_stats, data_charts = stats.compile_data(
            neuron_data={},
            search_query="test_query_1",
            case_sensitive=0,
            match_words=1,
            data_version=DEFAULT_DATA_SNAPSHOT_VERSION,
        )
        self.assertEqual(
            f"Stats for search query: 'test_query_1', match words, data version: {DEFAULT_DATA_SNAPSHOT_VERSION}",
            caption,
        )
        self.assertEqual(
            {
                "": {
                    "- Combined area": "NA",
                    "- Combined length": "NA",
                    "- Combined volume": "NA",
                    "- Classified": "0",
                    "Cells": "0",
                }
            },
            data_stats,
        )
        self.assertEqual({}, data_charts)

        # actual data
        neuron_db = get_testing_neuron_db()
        caption, data_stats, data_charts = stats.compile_data(
            neuron_data=list(neuron_db.neuron_data.values()),
            search_query="test_query_2",
            case_sensitive=1,
            match_words=0,
            data_version=DEFAULT_DATA_SNAPSHOT_VERSION,
        )
        self.assertEqual(
            f"Stats for search query: 'test_query_2', case sensitive, data version: {DEFAULT_DATA_SNAPSHOT_VERSION}",
            caption,
        )
        self.assertEqual(
            {""},
            set(data_stats.keys()),
        )
        self.assertEqual(
            {
                "Cells": "5,067",
                "- Classified": "0",
                "- Combined length": "1,300,210 &#181;m",
                "- Combined area": "0 &#181;m<sup>2</sup>",
                "- Combined volume": "0 &#181;m<sup>3</sup>",
            },
            data_stats[""],
        )
        self.assertEqual(
            [
                "Cell Type",
                "Flow",
                "Neurotransmitter Types",
                "Side",
                "Super Class",
                "Top Input Regions",
                "Top Output Regions",
            ],
            sorted(data_charts.keys()),
        )
        self.assertEqual(
            [5, 5, 5, 5, 5, 5, 5],
            [len(data_charts[k]) for k in sorted(data_charts.keys())],
        )
