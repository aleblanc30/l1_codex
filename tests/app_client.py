"""Flask test client for the two Codex blueprints, backed by the testing neuron database."""

import os


def make_test_client():
    os.environ.setdefault("FLASK_SECRET_KEY", "test-secret")

    from flask import Flask

    import codex.data.neuron_data_factory as factory_module
    from tests import get_testing_neuron_data_factory

    from codex.blueprints.app import app as app_blueprint
    from codex.blueprints.base import base as base_blueprint

    factory_module._instance = get_testing_neuron_data_factory()
    flask_app = Flask("codex-test")
    flask_app.secret_key = os.environ["FLASK_SECRET_KEY"]
    flask_app.register_blueprint(base_blueprint)
    flask_app.register_blueprint(app_blueprint)
    return flask_app.test_client()
