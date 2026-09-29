from pathlib import Path
from unittest import TestCase
from urllib.parse import parse_qs, urlsplit

from flask import Blueprint, Flask, abort

from codex.configuration import RedirectHomeError
from codex.error_handlers import register_error_handlers

ROOT = Path(__file__).resolve().parents[2]


def make_app(name):
    """A Flask app with the handlers and the stand-in `base` endpoints they redirect to."""
    flask_app = Flask(name)
    stand_in = Blueprint("base", name)

    @stand_in.route("/index")
    def index():
        return "home"

    @stand_in.route("/404")
    def page_not_found():
        return "not found"

    flask_app.register_blueprint(stand_in)
    register_error_handlers(flask_app)
    return flask_app


def make_client():
    flask_app = make_app("error-handlers-test")

    @flask_app.route("/abort/<int:code>")
    def abort_with(code):
        abort(code)

    @flask_app.route("/post_only", methods=["POST"])
    def post_only():
        return "posted"

    @flask_app.route("/crash")
    def crash():
        raise ValueError("secret internal detail <b>")

    @flask_app.route("/redirect_home")
    def redirect_home():
        raise RedirectHomeError("go home")

    @flask_app.route("/moved")
    def moved():
        return "moved"

    flask_app.testing = False
    flask_app.config["PROPAGATE_EXCEPTIONS"] = False
    return flask_app.test_client()


def error_page_params(response):
    location = urlsplit(response.headers["Location"])
    return location.path, {k: v[0] for k, v in parse_qs(location.query).items()}


class ErrorHandlersTest(TestCase):
    def setUp(self):
        self.client = make_client()

    def test_client_and_server_errors_redirect_to_the_error_page_with_their_status_code(self):
        for code in (400, 403, 405, 429, 500, 503):
            with self.subTest(code=code):
                response = self.client.get(f"/abort/{code}")
                self.assertEqual(302, response.status_code)
                path, params = error_page_params(response)
                self.assertEqual("/error", path)
                self.assertEqual(str(code), params["title"])
                self.assertTrue(params["message"])

    def test_wrong_method_is_reported_as_405(self):
        response = self.client.get("/post_only")
        path, params = error_page_params(response)
        self.assertEqual("/error", path)
        self.assertEqual("405", params["title"])

    def test_an_unexpected_exception_hides_its_details_from_the_user(self):
        response = self.client.get("/crash")
        self.assertEqual(302, response.status_code)
        path, params = error_page_params(response)
        self.assertEqual("/error", path)
        self.assertEqual("500", params["title"])
        self.assertNotIn("secret internal detail", params["message"])
        self.assertNotIn("ValueError", params["message"])

    def test_an_unexpected_exception_is_logged_with_its_traceback(self):
        with self.assertLogs("codex", level="ERROR") as logs:
            self.client.get("/crash")
        self.assertIn("secret internal detail", "\n".join(logs.output))

    def test_redirect_home_error_keeps_going_home(self):
        response = self.client.get("/redirect_home")
        self.assertEqual(302, response.status_code)
        self.assertEqual("/index", urlsplit(response.headers["Location"]).path)

    def test_not_found_goes_to_the_404_page(self):
        response = self.client.get("/abort/404")
        self.assertEqual(302, response.status_code)
        self.assertEqual("/404", urlsplit(response.headers["Location"]).path)

    def test_normal_pages_and_routing_redirects_are_untouched(self):
        self.assertEqual(200, self.client.get("/index").status_code)
        # a trailing slash on a route without one is a 404, but strict_slashes redirects must pass through
        flask_app = make_app("redirects")

        @flask_app.route("/dir/")
        def directory():
            return "dir"

        response = flask_app.test_client().get("/dir")
        self.assertEqual(308, response.status_code)
        self.assertTrue(response.headers["Location"].endswith("/dir/"))


class MainRegistersHandlersTest(TestCase):
    def test_main_uses_the_shared_registration_and_has_no_todo_left(self):
        source = (ROOT / "codex" / "main.py").read_text()
        self.assertIn("register_error_handlers(codex)", source)
        self.assertNotIn("TODO", source)


class MotifSearchPaginationSourceTest(TestCase):
    """The motif search page is a browser module, so only its source is checked here."""

    def setUp(self):
        self.source = (ROOT / "codex" / "static" / "js" / "motif_search.js").read_text()

    def test_no_todo_is_left(self):
        self.assertNotIn("TODO", self.source)

    def test_pagination_controls_are_rendered_only_for_more_than_one_page(self):
        self.assertIn("totalPages > 1", self.source)
        self.assertIn("<${PaginationControls}", self.source)
        self.assertLess(
            self.source.index("totalPages > 1"),
            self.source.index("<${PaginationControls}"),
        )

    def test_the_pagination_controls_receive_the_page_state(self):
        for prop in (
            "totalPages=${totalPages}",
            "currentPage=${page}",
            "onPageChange=${handlePageChange}",
            "maxVisiblePages=${maxVisiblePages}",
        ):
            self.assertIn(prop, self.source)
