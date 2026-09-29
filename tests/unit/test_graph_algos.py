from collections import Counter
from unittest import TestCase

from codex.utils.graph_algos import pathways, reachable_node_counts
from tests import get_testing_neuron_db


class TestGraphAlgos(TestCase):
    @classmethod
    def setUpClass(cls):
        cls.neuron_db = get_testing_neuron_db()

    def test_reachable_node_counts(self):
        num_cells = len(self.neuron_db.neuron_data)
        isets = self.neuron_db.input_sets()
        for n in sorted(self.neuron_db.neuron_data.keys())[1000:1001]:
            self.assertEqual(
                {
                    "1 hop": "18 (0%)",
                    "2 hops": "293 (5%)",
                    "3 hops": "2,494 (49%)",
                    "4 hops": "3,542 (69%)",
                    "5 hops": "3,776 (74%)",
                    "6 hops": "3,803 (75%)",
                    "7 hops": "3,804 (75%)",
                },
                reachable_node_counts({n}, isets, num_cells),
            )

    def test_pathways_small_graph(self):
        # 1 -> 2 -> 4 and 1 -> 3 -> 4 are shortest paths, 1 -> 5 -> 6 -> 4 is longer, 7 is a dead end
        osets = {1: {2, 3, 5}, 2: {4}, 3: {4}, 5: {6}, 6: {4}, 7: set()}
        isets = {2: {1}, 3: {1}, 5: {1}, 4: {2, 3, 6}, 6: {5}}
        self.assertEqual({1: 0, 2: 1, 3: 1, 4: 2}, dict(pathways(1, 4, isets, osets)))
        self.assertEqual({1: 0, 5: 1, 6: 2}, dict(pathways("1", "6", isets, osets)))
        self.assertIsNone(pathways(4, 1, isets, osets))
        self.assertIsNone(pathways(1, 7, isets, osets))
        self.assertIsNone(pathways(1, "not an id", isets, osets))

    def test_pathways(self):
        s = t = 0
        isets = self.neuron_db.input_sets()
        osets = self.neuron_db.output_sets()
        all_rids = sorted(self.neuron_db.neuron_data.keys())

        self.assertEqual(None, pathways(s, t, isets, osets))

        s = all_rids[100]
        t = all_rids[101]

        self.assertEqual(None, pathways(s, s, isets, osets))
        self.assertEqual(
            {s: 0, t: 2, 6264270: 1, 3661586: 1},
            dict(pathways(s, t, isets, osets)),
        )

        t = all_rids[102]
        path_nodes = dict(pathways(s, t, isets, osets))
        self.assertEqual(37, len(path_nodes))
        self.assertEqual({0: 1, 1: 10, 2: 19, 3: 6, 4: 1}, Counter(path_nodes.values()))
        self.assertEqual(0, path_nodes[s])
        self.assertEqual(4, path_nodes[t])
        # every node has a partner one layer before it and one layer after it, along the pathway
        for n, layer in path_nodes.items():
            if layer > 0:
                self.assertTrue(
                    any(path_nodes.get(i) == layer - 1 for i in isets.get(n, ())), n
                )
            if layer < 4:
                self.assertTrue(
                    any(path_nodes.get(o) == layer + 1 for o in osets.get(n, ())), n
                )

        s = all_rids[101]
        path_nodes = dict(pathways(s, t, isets, osets))
        self.assertEqual(
            {
                s: 0,
                t: 4,
                18981220: 1,
                183502: 1,
                3054101: 2,
                16575803: 2,
                19120853: 2,
                3613276: 3,
                9903957: 3,
            },
            path_nodes,
        )
