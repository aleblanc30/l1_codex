"""Flask test client for the two Codex blueprints, backed by the testing neuron database."""

import os
import sys
import types


def _ensure_nglui():
    """Use a stub when the real nglui (needed only to build viewer links) can't be imported."""
    try:
        from nglui import statebuilder  # noqa: F401
    except ImportError:
        module = types.ModuleType("nglui")
        module.statebuilder = types.ModuleType("nglui.statebuilder")
        sys.modules["nglui"] = module
        sys.modules["nglui.statebuilder"] = module.statebuilder


def make_test_client():
    os.environ.setdefault("FLASK_SECRET_KEY", "test-secret")
    _ensure_nglui()

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
