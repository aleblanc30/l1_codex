import logging
import re
from unittest import TestCase

from codex.utils.formatting import display
from tests.app_client import make_test_client

WINDING_COUNT = 3066
ALL_COUNT = 5013
IDS_URL = "/app/root_ids_from_search_results?filter_string=*&page_size=100000"


def without_selector(page):
    return re.sub(r"<select id=\"neuron_set_select\".*?</select>", "", page, flags=re.S)


def result_count(response):
    assert response.status_code == 200, response.status_code
    body = response.get_data(as_text=True)
    return len(body.split(",")) if body else 0


class NeuronSetRequestTest(TestCase):
    @classmethod
    def setUpClass(cls):
        logging.disable(logging.CRITICAL)

    @classmethod
    def tearDownClass(cls):
        logging.disable(logging.NOTSET)

    def setUp(self):
        self.client = make_test_client()

    def test_default_is_the_winding_set(self):
        self.assertEqual(WINDING_COUNT, result_count(self.client.get(IDS_URL)))

    def test_query_parameter_selects_a_set(self):
        self.assertEqual(
            ALL_COUNT, result_count(self.client.get(IDS_URL + "&neuron_set=all"))
        )

    def test_cookie_selects_a_set(self):
        self.client.set_cookie("neuron_set", "all")
        self.assertEqual(ALL_COUNT, result_count(self.client.get(IDS_URL)))

    def test_query_parameter_wins_over_the_cookie(self):
        self.client.set_cookie("neuron_set", "all")
        self.assertEqual(
            WINDING_COUNT,
            result_count(self.client.get(IDS_URL + "&neuron_set=winding")),
        )

    def test_unknown_values_fall_back_to_the_default(self):
        self.assertEqual(
            WINDING_COUNT, result_count(self.client.get(IDS_URL + "&neuron_set=zzz"))
        )
        self.client.set_cookie("neuron_set", "zzz")
        self.assertEqual(WINDING_COUNT, result_count(self.client.get(IDS_URL)))

    def test_soma_set(self):
        count = result_count(self.client.get(IDS_URL + "&neuron_set=soma"))
        self.assertTrue(0 < count < ALL_COUNT)

    def test_one_request_does_not_change_the_next(self):
        self.client.get(IDS_URL + "&neuron_set=all")
        self.assertEqual(WINDING_COUNT, result_count(self.client.get(IDS_URL)))

    def test_stats_follow_the_set(self):
        winding = self.client.get("/app/stats?filter_string=*").get_data(as_text=True)
        everything = self.client.get("/app/stats?filter_string=*&neuron_set=all")
        # the selector lists the size of every set
        winding = without_selector(winding)
        everything = without_selector(everything.get_data(as_text=True))
        self.assertIn(display(WINDING_COUNT), winding)
        self.assertIn(display(ALL_COUNT), everything)
        self.assertNotIn(display(ALL_COUNT), winding)

    def test_a_cell_outside_the_set_still_has_its_page(self):
        outside = self.client.get(IDS_URL + "&neuron_set=all").get_data(as_text=True)
        inside = set(self.client.get(IDS_URL).get_data(as_text=True).split(","))
        rid = next(r for r in outside.split(",") if r not in inside)
        response = self.client.get(f"/app/cell_details?root_id={rid}")
        self.assertEqual(200, response.status_code)
        self.assertIn(rid, response.get_data(as_text=True))

    def test_pages_offer_the_choice_of_set(self):
        page = self.client.get("/app/search?filter_string=*").get_data(as_text=True)
        self.assertIn('id="neuron_set_select"', page)
        self.assertIn('value="all"', page)
        self.assertIn('value="winding" selected', page)

    def test_selector_shows_the_current_set(self):
        page = self.client.get("/app/search?filter_string=*&neuron_set=all")
        self.assertIn('value="all" selected', page.get_data(as_text=True))


class OutsideTheSetTest(TestCase):
    @classmethod
    def setUpClass(cls):
        logging.disable(logging.CRITICAL)

    @classmethod
    def tearDownClass(cls):
        logging.disable(logging.NOTSET)

    def test_pathways_to_a_cell_outside_the_set_explain_the_choice(self):
        client = make_test_client()
        response = client.get("/app/pathways?source_cell_id=29&target_cell_id=11995")
        self.assertEqual(302, response.status_code)
        self.assertIn("selected+set+of+neurons", response.headers["Location"])

    def test_pathways_work_when_the_set_holds_both_cells(self):
        client = make_test_client()
        response = client.get(
            "/app/pathways?source_cell_id=29&target_cell_id=11995&neuron_set=all"
        )
        self.assertEqual(200, response.status_code)


class SetNeuronSetRouteTest(TestCase):
    @classmethod
    def setUpClass(cls):
        logging.disable(logging.CRITICAL)

    @classmethod
    def tearDownClass(cls):
        logging.disable(logging.NOTSET)

    def setUp(self):
        self.client = make_test_client()

    def test_sets_the_cookie_and_returns_to_the_page(self):
        response = self.client.get(
            "/neuron_set?value=all&next=/app/search%3Ffilter_string%3DKC"
        )
        self.assertEqual(302, response.status_code)
        self.assertEqual("/app/search?filter_string=KC", response.headers["Location"])
        cookie = response.headers["Set-Cookie"]
        self.assertIn("neuron_set=all", cookie)
        self.assertIn("SameSite=Lax", cookie)
        self.assertIn("Max-Age=", cookie)
        self.assertEqual(ALL_COUNT, result_count(self.client.get(IDS_URL)))

    def test_unknown_value_is_not_stored(self):
        response = self.client.get("/neuron_set?value=zzz&next=/")
        self.assertNotIn("neuron_set=zzz", response.headers.get("Set-Cookie", ""))

    def test_next_must_be_a_path_of_this_site(self):
        for unsafe in [
            "//evil.example/x",
            "https://evil.example/x",
            "/\\evil.example",
            "javascript:alert(1)",
            "",
        ]:
            response = self.client.get("/neuron_set", query_string={"value": "all", "next": unsafe})
            self.assertEqual(302, response.status_code, unsafe)
            self.assertEqual("/", response.headers["Location"], unsafe)

