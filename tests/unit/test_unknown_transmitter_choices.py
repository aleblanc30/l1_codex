import logging
from unittest import TestCase

from codex.data.neurotransmitters import (
    NEURO_TRANSMITTER_CHOICES,
    NEURO_TRANSMITTER_NAMES,
    NT_UNKNOWN,
)
from codex.service.motif_search import MotifSearchQuery
from tests import get_testing_neuron_data_factory
from tests.app_client import make_test_client


class ChoicesTest(TestCase):
    def test_choices_are_the_known_transmitters_then_unknown(self):
        self.assertEqual(
            list(NEURO_TRANSMITTER_NAMES) + [NT_UNKNOWN], list(NEURO_TRANSMITTER_CHOICES)
        )

    def test_known_names_are_unchanged(self):
        for key, name in NEURO_TRANSMITTER_NAMES.items():
            self.assertEqual(name, NEURO_TRANSMITTER_CHOICES[key])

    def test_the_unknown_choice_is_described(self):
        self.assertIn("not yet", NEURO_TRANSMITTER_CHOICES[NT_UNKNOWN])

    def test_the_known_transmitters_alone_are_not_extended(self):
        self.assertNotIn(NT_UNKNOWN, NEURO_TRANSMITTER_NAMES)


class MotifSearchTest(TestCase):
    def query(self):
        msq = MotifSearchQuery(get_testing_neuron_data_factory())
        msq.add_node("a", "")
        msq.add_node("b", "")
        return msq

    def test_an_edge_can_require_an_unknown_transmitter(self):
        msq = self.query()
        msq.add_edge("a", "b", regions=None, nt_type=NT_UNKNOWN, min_synapse_count=0)
        self.assertEqual(NT_UNKNOWN, msq.edges[("a", "b")].nt_type)

    def test_other_transmitters_are_still_rejected(self):
        msq = self.query()
        with self.assertRaises(ValueError):
            msq.add_edge("a", "b", regions=None, nt_type="FOO", min_synapse_count=0)

    def test_the_form_accepts_unknown(self):
        msq = MotifSearchQuery.from_form_query(
            {
                "queryA": "*",
                "queryB": "*",
                "enabledAB": "on",
                "regionAB": "Any",
                "ntTypeAB": NT_UNKNOWN,
            },
            get_testing_neuron_data_factory(),
        )
        self.assertEqual(NT_UNKNOWN, msq.edges[("A", "B")].nt_type)

    def test_the_form_still_rejects_other_values(self):
        with self.assertRaises(ValueError):
            MotifSearchQuery.from_form_query(
                {"queryA": "*", "queryB": "*", "enabledAB": "on", "regionAB": "Any", "ntTypeAB": "FOO"},
                get_testing_neuron_data_factory(),
            )

    def test_a_match_can_carry_an_unknown_transmitter(self):
        edge = MotifSearchQuery._make_edge_match_dict("A", "B", "A1_L", 3, NT_UNKNOWN)
        self.assertEqual(NT_UNKNOWN, edge["nt_type"])

    def test_a_match_rejects_an_invented_transmitter(self):
        with self.assertRaises(AssertionError):
            MotifSearchQuery._make_edge_match_dict("A", "B", "A1_L", 3, "FOO")


class MotifPageTest(TestCase):
    @classmethod
    def setUpClass(cls):
        logging.disable(logging.CRITICAL)

    @classmethod
    def tearDownClass(cls):
        logging.disable(logging.NOTSET)

    def test_the_page_offers_unknown(self):
        page = make_test_client().get("/app/motifs/").get_data(as_text=True)
        self.assertIn('value="UNKNOWN"', page)
        self.assertIn('value="GABA"', page)

    def test_a_search_with_an_unknown_transmitter_edge_finds_pairs(self):
        query = (
            "/app/motifs/?queryA=*&queryB=*&enabledAB=on&regionAB=Any"
            "&minSynapseCountAB=20&ntTypeAB=UNKNOWN&neuron_set=all"
        )
        response = make_test_client().get(query)
        self.assertEqual(200, response.status_code)
