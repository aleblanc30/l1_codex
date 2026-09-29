import html
import json
import re
from html.parser import HTMLParser
from unittest import TestCase

from codex.blueprints.base import jinja_env
from codex.data.neuron_data_initializer import initialize_neuron_data
from codex.utils.formatting import highlight_annotations
from tests.l1_fixture import initialize_kwargs

HOSTILE = "O'Brien \"<b>x</b>\" & <script>alert(1)</script>"


def _visible_text(fragment):
    """The text a browser would show for a fragment that only uses span tags."""
    return html.unescape(re.sub(r"</?span[^>]*>", "", fragment))


class HighlightEscapingTest(TestCase):
    def test_markup_in_a_term_is_escaped_without_a_match(self):
        out = highlight_annotations(["zzz"], ["a<b>c & d"])["a<b>c & d"]
        self.assertNotIn("<b>", out)
        self.assertEqual("a<b>c & d", _visible_text(out))

    def test_markup_around_a_match_is_escaped(self):
        term = "<script>MBON</script> & co"
        out = highlight_annotations(["MBON"], [term])[term]
        self.assertNotIn("<script>", out)
        self.assertIn('<span class="highlight-', out)
        self.assertEqual(term, _visible_text(out))

    def test_markup_inside_a_matched_word_is_escaped(self):
        term = "x<i>MBON"
        out = highlight_annotations(["mbon"], [term])[term]
        self.assertNotIn("<i>", out)
        self.assertEqual(term, _visible_text(out))

    def test_quotes_and_ampersands_survive_the_round_trip(self):
        out = highlight_annotations(["o'brien"], [HOSTILE])[HOSTILE]
        self.assertNotIn("<script>", out)
        self.assertEqual(HOSTILE, _visible_text(out))

    def test_plain_terms_are_unchanged(self):
        out = highlight_annotations(["mbon"], ["MBON-a1"])["MBON-a1"]
        self.assertEqual("MBON-a1", _visible_text(out))
        self.assertIn('<span class="highlight-', out)


class _OnclickCollector(HTMLParser):
    def __init__(self):
        super().__init__()
        self.onclicks = []

    def handle_starttag(self, tag, attrs):
        for name, value in attrs:
            if name == "onclick":
                self.onclicks.append(value)


def _filter_arguments(rendered_html):
    collector = _OnclickCollector()
    collector.feed(rendered_html)
    args = []
    for onclick in collector.onclicks:
        match = re.fullmatch(r"apply_filter\((.*)\);", onclick)
        assert match, f"onclick is not a plain apply_filter call: {onclick}"
        args.append(json.loads(match.group(1)))
    return args


class FilterButtonEscapingTest(TestCase):
    def test_single_value_filter_buttons_pass_the_value_as_a_string(self):
        rendered = jinja_env.get_template("attribute_with_spot_filter.html").render(
            attr_val=HOSTILE,
            attr_key="cell_type",
            caption="",
            tooltip="",
            highlighted_terms={},
            multi_val_attrs=["cell_type"],
        )
        self.assertEqual(
            [f"cell_type != {HOSTILE}", f"cell_type == {HOSTILE}"],
            _filter_arguments(rendered),
        )
        self.assertNotIn("<script>", rendered)

    def test_multi_value_filter_buttons_pass_each_value_as_a_string(self):
        rendered = jinja_env.get_template("attribute_with_multiple_values.html").render(
            attr_val=[HOSTILE],
            attr_key="papers",
            caption="",
            tooltip="",
            highlighted_terms={},
            non_uniform_values={HOSTILE},
        )
        self.assertEqual(
            [f"papers != {HOSTILE}", f"papers == {HOSTILE}"],
            _filter_arguments(rendered),
        )
        self.assertNotIn("<script>", rendered)


class QueryErrorEscapingTest(TestCase):
    """Error messages are rendered as HTML, and they quote what the user typed."""

    @classmethod
    def setUpClass(cls):
        cls.db = initialize_neuron_data(**initialize_kwargs())

    def message_for(self, query):
        with self.assertRaises(ValueError) as caught:
            self.db.search(query)
        return str(caught.exception)

    def test_unknown_attribute_name_is_escaped(self):
        msg = self.message_for("<img src=x onerror=alert(1)> == left")
        self.assertNotIn("<img", msg)
        self.assertIn("&lt;img", msg)

    def test_invalid_value_is_escaped(self):
        msg = self.message_for("node_count >= <img src=x onerror=alert(1)>")
        self.assertNotIn("<img", msg)
        self.assertIn("&lt;img", msg)

    def test_term_with_too_many_operators_is_escaped(self):
        msg = self.message_for("a == b != <img src=x>")
        self.assertNotIn("<img", msg)
        self.assertIn("&lt;img", msg)

    def test_the_hints_of_the_message_keep_their_markup(self):
        msg = self.message_for("node_count >= many")
        self.assertIn("<b>advanced search</b>", msg)


class ErrorPageTest(TestCase):
    def test_error_url_round_trips_messages_with_reserved_characters(self):
        from urllib.parse import parse_qs, urlsplit

        from codex.blueprints.base import error_page_url

        message = "a&b=c#d %20 &lt;x&gt; 'q' \"q\""
        url = error_page_url(message=message, title="T&T", back_button=0)
        query = parse_qs(urlsplit(url).query)
        self.assertEqual("/error", urlsplit(url).path)
        self.assertEqual([message], query["message"])
        self.assertEqual(["T&T"], query["title"])
        self.assertEqual(["0"], query["back_button"])

    def test_sanitizer_keeps_the_markup_the_app_uses_in_messages(self):
        from codex.utils.formatting import sanitize_message_html

        msg = "'x' is not valid for <b>side</b>.<ul><li>a</li><li>b</li></ul><br><i>hint</i>"
        self.assertEqual(msg, sanitize_message_html(msg))

    def test_sanitizer_neutralizes_other_tags(self):
        from codex.utils.formatting import sanitize_message_html

        for hostile in [
            "<script>alert(1)</script>",
            "<img src=x onerror=alert(1)>",
            '<a href="javascript:alert(1)">x</a>',
            "<b onmouseover=alert(1)>x</b>",
            "<svg/onload=alert(1)>",
        ]:
            out = sanitize_message_html(f"before {hostile} after")
            self.assertEqual("before", out.split(" ")[0])
            self.assertNotRegex(out, r"<(?!/?(?:b|br|i|small|ul|li)\s*/?>)", hostile)

    def test_sanitizer_leaves_entities_alone(self):
        from codex.utils.formatting import sanitize_message_html

        self.assertEqual("&lt;img&gt; &amp; co", sanitize_message_html("&lt;img&gt; &amp; co"))

    def test_sanitizer_accepts_non_strings(self):
        from codex.utils.formatting import sanitize_message_html

        self.assertEqual("5", sanitize_message_html(5))
