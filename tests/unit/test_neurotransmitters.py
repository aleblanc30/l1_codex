from unittest import TestCase
from codex.data.neurotransmitters import (
    NEURO_TRANSMITTER_NAMES,
    NT_UNKNOWN,
    lookup_nt_type,
    lookup_nt_type_name,
)
from codex.data.structured_search_filters import STRUCTURED_SEARCH_ATTRIBUTES


class NtTest(TestCase):
    def test_lookup_nt_type(self):
        for nt in NEURO_TRANSMITTER_NAMES.keys():
            self.assertEqual(nt, lookup_nt_type(nt.lower()))
            self.assertEqual(nt, lookup_nt_type(nt.lower()))
        self.assertEqual("bogus", lookup_nt_type("bogus"))
        self.assertEqual("DA", lookup_nt_type("DOPA"))
        self.assertEqual("DA", lookup_nt_type("Dopamine"))
        self.assertEqual("DA", lookup_nt_type("dopamine"))

    def test_unknown_is_not_a_known_transmitter(self):
        self.assertEqual("UNKNOWN", NT_UNKNOWN)
        self.assertNotIn(NT_UNKNOWN, NEURO_TRANSMITTER_NAMES)

    def test_lookup_normalizes_unknown(self):
        for txt in ["UNKNOWN", "unknown", "Unknown"]:
            self.assertEqual(NT_UNKNOWN, lookup_nt_type(txt))

    def test_unknown_has_a_readable_name(self):
        self.assertEqual("unknown NT type", lookup_nt_type_name(NT_UNKNOWN))
        self.assertEqual("unknown NT type", lookup_nt_type_name("unknown"))

    def test_search_by_neurotransmitter_accepts_unknown(self):
        (attribute,) = [a for a in STRUCTURED_SEARCH_ATTRIBUTES if a.name == "nt_type"]
        self.assertIn(NT_UNKNOWN, attribute.value_range)
        self.assertEqual(NT_UNKNOWN, attribute.value_convertor("unknown"))
