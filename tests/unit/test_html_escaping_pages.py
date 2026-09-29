import json
import logging
import re
from copy import deepcopy
from unittest import TestCase

from codex.data.neuron_data_initializer import initialize_neuron_data
from codex.service.cell_details import cached_cell_details
from codex.service.heatmaps import heatmap_data
from codex.service.network import compile_network_html
from codex.utils import stats as stats_utils
from tests.app_client import make_test_client
from tests.l1_fixture import initialize_kwargs, l1_rows

TAG = "<pwn-tag>"
ESCAPED = "&lt;pwn-tag&gt;"


def hostile_db():
    """The fixture with markup in a group, a cell type and a skeleton name."""
    rows = deepcopy(l1_rows())
    for r in rows["neurons"][1:]:
        if r[0] == "1001":
            r[1] = f"grp{TAG}"  # group
    for r in rows["cell_types"][1:]:
        if r[0] == "1001":
            r[1] = f"type{TAG}"
    for r in rows["skeletons"][1:]:
        if r[0] == "1001":
            r[1] = f"skel{TAG}"
    return initialize_neuron_data(**initialize_kwargs(rows))


def strings_in(value):
    if isinstance(value, dict):
        for k, v in value.items():
            yield from strings_in(k)
            yield from strings_in(v)
    elif isinstance(value, (list, tuple)):
        for v in value:
            yield from strings_in(v)
    elif isinstance(value, str):
        yield value


def popup_titles(network_html):
    """The titles of the nodes, which the page inserts as HTML when a node is hovered."""
    nodes = json.loads(re.search(r"const nodeslist = (\[.*?\]);", network_html).group(1))
    return [n["title"] for n in nodes]


class PageEscapingTest(TestCase):
    @classmethod
    def setUpClass(cls):
        logging.disable(logging.CRITICAL)
        cls.db = hostile_db()
        cls.app = make_test_client().application

    @classmethod
    def tearDownClass(cls):
        logging.disable(logging.NOTSET)

    def test_the_fixture_really_holds_markup(self):
        self.assertIn(TAG, self.db.get_neuron_data(1001)["name"])
        self.assertIn(TAG, self.db.get_neuron_data(1001)["cell_type"][0])

    def test_cell_page_values_are_escaped(self):
        with self.app.test_request_context():
            details = cached_cell_details(
                cell_names_or_id="1001",
                root_id=1001,
                neuron_db=self.db,
                data_version="",
                reachability_stats=0,
            )
        shown = " ".join(
            strings_in([details["cell_attributes"], details["cell_annotations"]])
        )
        self.assertNotIn(TAG, shown)
        self.assertIn(ESCAPED, shown)

    def test_cell_page_keeps_its_own_markup(self):
        with self.app.test_request_context():
            details = cached_cell_details(
                cell_names_or_id="1001",
                root_id=1001,
                neuron_db=self.db,
                data_version="",
                reachability_stats=0,
            )
        shown = " ".join(strings_in(details["cell_attributes"]))
        self.assertIn("<small>", shown)
        self.assertIn("<a href=", shown)

    def test_heatmap_headers_are_escaped(self):
        data = heatmap_data(self.db, "Group", "Synapses")
        shown = " ".join(strings_in(data["table"])).lower()  # group names are title-cased
        self.assertNotIn(TAG, shown)
        self.assertIn(ESCAPED, shown)

    def test_chart_tooltips_are_escaped(self):
        chart = stats_utils.make_chart_from_counts(
            chart_type="bar",
            key_title="Cell type",
            val_title="Cells",
            counts_dict={f"type{TAG}": 3},
            descriptions_dict={f"type{TAG}": "described"},
        )
        tooltip = chart["data"][1][3]  # shown as HTML, unlike the row label
        self.assertNotIn(TAG, tooltip)
        self.assertIn(ESCAPED, tooltip)

    def test_network_node_popups_are_escaped(self):
        with self.app.test_request_context():
            html = compile_network_html(
                center_ids=[1001],
                contable=[[1001, 1002, "A1_L", 3, ""]],
                neuron_db=self.db,
                show_regions=0,
                connections_cap=0,
                hide_weights=0,
                log_request=False,
            )
        titles = " ".join(popup_titles(html))
        self.assertNotIn(TAG, titles)
        self.assertIn(ESCAPED, titles)

    def test_network_popups_keep_their_link(self):
        with self.app.test_request_context():
            html = compile_network_html(
                center_ids=[1001],
                contable=[[1001, 1002, "A1_L", 3, ""]],
                neuron_db=self.db,
                show_regions=0,
                connections_cap=0,
                hide_weights=0,
                log_request=False,
            )
        self.assertIn('<a href="/app/cell_details?root_id=1001"', " ".join(popup_titles(html)))

    def test_network_group_popups_are_escaped(self):
        with self.app.test_request_context():
            html = compile_network_html(
                center_ids=[1001],
                contable=[[1001, 1002, "A1_L", 3, ""]],
                neuron_db=self.db,
                show_regions=0,
                connections_cap=0,
                hide_weights=0,
                log_request=False,
                group_by_attribute_name="group",
            )
        titles = " ".join(popup_titles(html)).lower()  # group names are title-cased
        self.assertIn("grp", titles)
        self.assertNotIn(TAG, titles)
        self.assertIn(ESCAPED, titles)
