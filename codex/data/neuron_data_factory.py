from codex.configuration import RedirectHomeError
from codex.data.local_data_loader import unpickle_neuron_db, DATA_ROOT_PATH
from codex.data.neuron_sets import DEFAULT_NEURON_SET, active_neuron_set
from codex.data.versions import DEFAULT_DATA_SNAPSHOT_VERSION, DATA_SNAPSHOT_VERSIONS
from codex import logger

# Singleton
_instance = None


class NeuronDataFactory(object):
    def __init__(self, data_root_path=DATA_ROOT_PATH, preload_latest=True):
        logger.debug(f"Initializing NeuronDataFactory with {data_root_path=}...")
        # enforce singleton for app (allow for tests)
        if data_root_path == DATA_ROOT_PATH:
            global _instance
            assert _instance is None
            _instance = self

        self._data_root_path = data_root_path
        self._version_to_data = {}
        if preload_latest:
            logger.debug("App Initialization: preloading latest version")
            self.get_unrestricted().view(DEFAULT_NEURON_SET)

    def get(self, version=None):
        """The database for the data version, restricted to the neuron set of the current request. Outside
        of a request (scripts, tests) no set is active and this is the whole dataset."""
        db = self.get_unrestricted(version)
        return db.view(active_neuron_set()) if active_neuron_set() else db

    def get_containing(self, root_id, version=None):
        """Like get, but a cell outside the current neuron set is looked up in the whole dataset, so the
        page of a single cell can always be shown."""
        db = self.get(version)
        if db.is_in_dataset(root_id):
            return db
        return self.get_unrestricted(version)

    def get_unrestricted(self, version=None):
        if not version:
            version = DEFAULT_DATA_SNAPSHOT_VERSION
        elif version not in DATA_SNAPSHOT_VERSIONS:
            raise RedirectHomeError(f"Data version {version} could not be loaded.")

        if version not in self._version_to_data:
            self._version_to_data[version] = unpickle_neuron_db(
                version, data_root_path=self._data_root_path
            )
        return self._version_to_data[version]

    def loaded_versions(self):
        return list(self._version_to_data.keys())

    @classmethod
    def instance(cls):
        global _instance
        if _instance is None:
            _instance = NeuronDataFactory()
        return _instance
