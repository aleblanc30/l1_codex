import os
import re

# for IDE test
from codex.configuration import APP_ENVIRONMENT
from codex.data.local_data_loader import DATA_ROOT_PATH
from codex.data.neuron_data_factory import NeuronDataFactory
from codex.data.versions import TESTING_DATA_SNAPSHOT_VERSION

TEST_DATA_ROOT_PATH = re.sub(r"tests.*", DATA_ROOT_PATH, os.getcwd())
# for pytest
if not TEST_DATA_ROOT_PATH.endswith(DATA_ROOT_PATH):
    TEST_DATA_ROOT_PATH += f"/{DATA_ROOT_PATH}"

_TEST_NEURON_DATA_FACTORY = None


# The factory (and so the database) is built on first use, so tests that don't need it don't pay for it
def get_testing_neuron_data_factory():
    global _TEST_NEURON_DATA_FACTORY
    if _TEST_NEURON_DATA_FACTORY is None:
        _TEST_NEURON_DATA_FACTORY = NeuronDataFactory(
            data_root_path=TEST_DATA_ROOT_PATH, preload_latest=False
        )
    return _TEST_NEURON_DATA_FACTORY


def get_testing_neuron_db(version=TESTING_DATA_SNAPSHOT_VERSION):
    return get_testing_neuron_data_factory().get(version=version)


assert APP_ENVIRONMENT == "DEV"


# Helper for inspecting cell lists in dev server
def log_dev_url_for_root_ids(caption, root_ids, prod=False):
    burl = "https://codex.flywire.ai" if prod else "http://localhost:5000"
    print(
        f"{caption}: {burl}/app/search?filter_string="
        f"{'%2C+'.join([str(rid) for rid in root_ids])}&page_size=100"
    )
