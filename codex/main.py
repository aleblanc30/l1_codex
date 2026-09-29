import os
import secrets

from flask import Flask, request

from codex.blueprints.app import app
from codex.blueprints.base import base
from codex.data.neuron_data_factory import NeuronDataFactory
from codex.error_handlers import register_error_handlers
from codex import logger
import logging

# Set logger level
logger.setLevel(logging.DEBUG)

# Create console handler and set its level to DEBUG
ch = logging.StreamHandler()
ch.setLevel(logging.DEBUG)

# Add the console handler to the logger
logger.addHandler(ch)

logger.debug("App initialization started")
codex = Flask(__name__)


@app.before_request
def before_request():
    logger.info(f"APP: Processing request to {request.url}")


register_error_handlers(codex)

# The app does not use sessions, so the key is optional. Without one, a random key is generated for this
# process (with several worker processes each would have its own, which matters only if sessions are used).
secret_key = os.environ.get("FLASK_SECRET_KEY")
if not secret_key:
    logger.warning("FLASK_SECRET_KEY is not set, using a random key for this process")
    secret_key = secrets.token_hex(32)
codex.secret_key = secret_key
codex.config["PERMANENT_SESSION_LIFETIME"] = 12 * 31 * 24 * 60 * 60  # 12 months
codex.register_blueprint(
    base
)  # Common endpoints, mostly static pages, assets and other resources
codex.register_blueprint(
    app
)  # Web application (search/stats/cell details, other tools)

print(
    f"App initialization complete. Loaded data versions {NeuronDataFactory.instance().loaded_versions()}"
)

if __name__ == "__main__":
    codex.run(debug=True, host="0.0.0.0", port=int(os.environ.get("PORT", 8080)))
