import os
import shutil
import tempfile
from unittest import TestCase
from unittest.mock import patch

from codex.data.catalog import get_data_schema
from codex.data.local_data_loader import (
    BUNDLED_DATA_PATH,
    DATA_FILE_NAMES,
    DATA_URL_ENV_VAR,
    NEURON_DB_PICKLE_FILE_NAME,
    data_file_path_for_version,
    find_raw_file,
    load_and_pickle_neuron_db_versions,
    load_neuron_db,
    read_csv,
    unpickle_neuron_db,
    write_csv,
)
from codex.data.versions import (
    DATA_SNAPSHOT_VERSIONS,
    DEFAULT_DATA_SNAPSHOT_VERSION,
    TESTING_DATA_SNAPSHOT_VERSION,
)
from tests.l1_fixture import AGGREGATE_ID, l1_rows

VERSION = "test-version"


def write_fixture(directory, tables=None):
    os.makedirs(directory, exist_ok=True)
    for table, rows in (tables or l1_rows()).items():
        write_csv(os.path.join(directory, f"{table}.csv.gz"), rows, compress=True)


class TempDirTestCase(TestCase):
    def setUp(self):
        self.root = tempfile.mkdtemp()
        self.bundled = os.path.join(self.root, "bundled")
        self.data_root = os.path.join(self.root, "data")
        self.addCleanup(shutil.rmtree, self.root, ignore_errors=True)

    @property
    def local_dir(self):
        return data_file_path_for_version(VERSION, self.data_root)


class VersionsTest(TestCase):
    def test_default_and_testing_versions_are_listed(self):
        self.assertIn(DEFAULT_DATA_SNAPSHOT_VERSION, DATA_SNAPSHOT_VERSIONS)
        self.assertIn(TESTING_DATA_SNAPSHOT_VERSION, DATA_SNAPSHOT_VERSIONS)

    def test_data_files_are_the_catalog_tables(self):
        self.assertEqual(
            {f"{table}.csv.gz" for table in get_data_schema()},
            set(DATA_FILE_NAMES),
        )

    def test_repository_ships_a_copy_of_every_data_file(self):
        for name in DATA_FILE_NAMES:
            self.assertTrue(os.path.isfile(os.path.join(BUNDLED_DATA_PATH, name)), name)


class FindRawFileTest(TempDirTestCase):
    def find(self, **kwargs):
        return find_raw_file(
            "neurons.csv.gz",
            VERSION,
            data_root_path=self.data_root,
            bundled_path=self.bundled,
            **kwargs,
        )

    def test_local_copy_wins(self):
        write_fixture(self.local_dir)
        write_fixture(self.bundled)
        self.assertEqual(os.path.join(self.local_dir, "neurons.csv.gz"), self.find())

    def test_falls_back_to_the_bundled_copy(self):
        write_fixture(self.bundled)
        self.assertEqual(os.path.join(self.bundled, "neurons.csv.gz"), self.find())

    def test_returns_none_when_nothing_is_available(self):
        self.assertIsNone(self.find())

    def test_downloads_from_the_configured_url(self):
        def fake_download(url, dest_folder):
            self.assertEqual("https://example.org/l1/neurons.csv.gz", url)
            write_fixture(dest_folder)
            return True

        with patch(
            "codex.data.local_data_loader.download", side_effect=fake_download
        ) as mocked:
            path = self.find(base_url="https://example.org/l1")
        self.assertEqual(1, mocked.call_count)
        self.assertEqual(os.path.join(self.local_dir, "neurons.csv.gz"), path)

    def test_url_comes_from_the_environment_when_not_given(self):
        write_fixture(self.bundled)
        with patch.dict(os.environ, {DATA_URL_ENV_VAR: "https://example.org/l1/"}):
            with patch(
                "codex.data.local_data_loader.download", return_value=False
            ) as mocked:
                path = self.find()
        self.assertEqual(
            "https://example.org/l1/neurons.csv.gz", mocked.call_args[0][0]
        )
        # a failed download falls back to the bundled copy
        self.assertEqual(os.path.join(self.bundled, "neurons.csv.gz"), path)

    def test_no_download_is_attempted_without_a_url(self):
        with patch.dict(os.environ, clear=False) as env:
            env.pop(DATA_URL_ENV_VAR, None)
            with patch("codex.data.local_data_loader.download") as mocked:
                self.find()
        mocked.assert_not_called()


class LoadNeuronDbTest(TempDirTestCase):
    def load(self):
        return load_neuron_db(
            data_root_path=self.data_root, version=VERSION, bundled_path=self.bundled
        )

    def test_loads_from_local_files(self):
        write_fixture(self.local_dir)
        db = self.load()
        self.assertEqual({1001, 1002, 1003, AGGREGATE_ID}, set(db.neuron_data))

    def test_loads_from_the_bundled_files(self):
        write_fixture(self.bundled)
        self.assertEqual(4, len(self.load().neuron_data))

    def test_missing_file_is_reported_by_name(self):
        tables = l1_rows()
        del tables["papers"]
        write_fixture(self.bundled, tables)
        with self.assertRaises(FileNotFoundError) as ctx:
            self.load()
        self.assertIn("papers.csv.gz", str(ctx.exception))

    def test_bundled_export_loads_with_a_consistent_schema(self):
        db = load_neuron_db(data_root_path=self.data_root, version=VERSION)
        self.assertGreater(len(db.neuron_data), 5000)
        self.assertTrue(any(nd["is_aggregate"] for nd in db.neuron_data.values()))


class PickleTest(TempDirTestCase):
    def test_round_trip(self):
        write_fixture(self.local_dir)
        load_and_pickle_neuron_db_versions(
            data_root_path=self.data_root, versions=[VERSION], bundled_path=self.bundled
        )
        self.assertTrue(
            os.path.isfile(os.path.join(self.local_dir, NEURON_DB_PICKLE_FILE_NAME))
        )
        db = unpickle_neuron_db(VERSION, data_root_path=self.data_root)
        self.assertEqual({1001, 1002, 1003, AGGREGATE_ID}, set(db.neuron_data))

    def test_missing_pickle_is_built_from_the_raw_files(self):
        write_fixture(self.bundled)
        db = unpickle_neuron_db(
            VERSION, data_root_path=self.data_root, bundled_path=self.bundled
        )
        self.assertEqual(4, len(db.neuron_data))
        self.assertTrue(
            os.path.isfile(os.path.join(self.local_dir, NEURON_DB_PICKLE_FILE_NAME))
        )

    def test_unloadable_data_gives_none(self):
        self.assertIsNone(
            unpickle_neuron_db(
                VERSION, data_root_path=self.data_root, bundled_path=self.bundled
            )
        )


class CsvHelpersTest(TempDirTestCase):
    def test_compressed_round_trip_keeps_commas_and_quotes(self):
        rows = [["a", "b"], ["x, y", "v'ada \"q\""]]
        path = os.path.join(self.root, "t.csv.gz")
        write_csv(path, rows, compress=True)
        self.assertEqual(rows, read_csv(path))
