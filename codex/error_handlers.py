from flask import redirect, url_for
from werkzeug.exceptions import HTTPException, InternalServerError

from codex import logger
from codex.configuration import RedirectHomeError

UNEXPECTED_ERROR_MESSAGE = "An unexpected error occurred. Please try again later."


def error_page_redirect(title, message):
    # imported here because the base blueprint imports much of the application
    from codex.blueprints.base import render_error

    return render_error(message, str(title))


def register_error_handlers(flask_app):
    """Sends every failed request to the error page, or home for RedirectHomeError."""

    @flask_app.errorhandler(RedirectHomeError)
    def handle_redirect_home_error(e):
        logger.error(f"Redirecting home due to exception: {e}")
        return redirect(url_for("base.index"))

    @flask_app.errorhandler(404)
    def page_not_found(e):
        logger.error(f"404: {e}")
        return redirect(url_for("base.page_not_found"))

    @flask_app.errorhandler(HTTPException)
    def handle_http_exception(e):
        logger.error(f"{e.code}: {e}")
        return error_page_redirect(e.code, e.description or e.name)

    @flask_app.errorhandler(Exception)
    def handle_unexpected_exception(e):
        # the details go to the log only, so internals are not shown to the user
        logger.error(f"Unexpected error: {e!r}", exc_info=e)
        return error_page_redirect(InternalServerError.code, UNEXPECTED_ERROR_MESSAGE)
