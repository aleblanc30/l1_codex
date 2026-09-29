import csv
import gc
import gzip
import os
import pickle
from pathlib import Path

from codex.data.catalog import get_data_schema
from codex.data.neuron_data_initializer import (
    initialize_neuron_data,
    NEURON_DATA_ATTRIBUTE_TYPES,
)
from codex.data.versions import DEFAULT_DATA_SNAPSHOT_VERSION, DATA_SNAPSHOT_VERSIONS
from codex.utils.networking import download

from codex import logger

DATA_ROOT_PATH = "static/data"
NEURON_DB_PICKLE_FILE_NAME = "neuron_db.pickle.gz"

# One raw data file per catalog table
DATA_FILE_NAMES = [f"{table}.csv.gz" for table in get_data_schema()]

# Raw data files shipped with the repository. They are used when a version's files are
# neither in the data folder nor available at the URL in DATA_URL_ENV_VAR.
BUNDLED_DATA_PATH = str(Path(__file__).resolve().parents[2] / "data" / "l1_export")

# Base URL of hosted raw data files (the file name is appended)
DATA_URL_ENV_VAR = "CODEX_DATA_URL"


def data_file_path_for_version(version, data_root_path=DATA_ROOT_PATH):
    return f"{data_root_path}/{version}"


def find_raw_file(
    filename,
    version,
    data_root_path=DATA_ROOT_PATH,
    bundled_path=BUNDLED_DATA_PATH,
    base_url=None,
):
    """Path of a raw data file: the data folder first, then the hosted copy, then the bundled one."""
    data_file_path = data_file_path_for_version(
        version=version, data_root_path=data_root_path
    )
    local_path = os.path.join(data_file_path, filename)
    if os.path.isfile(local_path):
        return local_path

    base_url = base_url or os.environ.get(DATA_URL_ENV_VAR)
    if base_url:
        url = f"{base_url.rstrip('/')}/{filename}"
        logger.info(f"Downloading raw data file {filename} for version {version}")
        if download(url, data_file_path) and os.path.isfile(local_path):
            return local_path
        logger.warning(f"Raw data file {filename} could not be downloaded from {url}")

    bundled_file = os.path.join(bundled_path, filename)
    return bundled_file if os.path.isfile(bundled_file) else None


def load_neuron_db(
    data_root_path=DATA_ROOT_PATH, version=None, bundled_path=BUNDLED_DATA_PATH
):
    if version is None:
        version = DEFAULT_DATA_SNAPSHOT_VERSION
    logger.info(f"Loading data for version {version}...")

    rows = {}
    for table in get_data_schema():
        filename = f"{table}.csv.gz"
        path = find_raw_file(filename, version, data_root_path, bundled_path)
        if path is None:
            raise FileNotFoundError(
                f"Raw data file {filename} for version {version} was not found in "
                f"{data_file_path_for_version(version, data_root_path)}, at ${DATA_URL_ENV_VAR} "
                f"or in {bundled_path}"
            )
        rows[table] = read_csv(path)

    logger.info(
        f"Loaded {len(rows['neurons']) - 1} neuron rows and "
        f"{len(rows['connections']) - 1} connection rows"
    )
    return initialize_neuron_data(
        neuron_file_rows=rows["neurons"],
        classification_rows=rows["classification"],
        cell_type_rows=rows["cell_types"],
        paper_rows=rows["papers"],
        annotation_rows=rows["annotations"],
        skeleton_rows=rows["skeletons"],
        connection_rows=rows["connections"],
    )


def unpickle_neuron_db(
    version, data_root_path=DATA_ROOT_PATH, bundled_path=BUNDLED_DATA_PATH
):
    try:
        fldr = data_file_path_for_version(
            version=version, data_root_path=data_root_path
        )
        pf = f"{fldr}/{NEURON_DB_PICKLE_FILE_NAME}"
        if not os.path.isfile(pf):
            logger.info(f"Building the data pickle for version {version}")
            load_and_pickle_neuron_db_versions(
                data_root_path=data_root_path,
                versions=[version],
                bundled_path=bundled_path,
            )
        with gzip.open(pf, "rb") as handle:
            gc.disable()
            db = pickle.load(handle)
            # For the default data version, we want to make sure the data schema of the sourcecode is consistent with
            # the pre-pickled data file.
            if version == DEFAULT_DATA_SNAPSHOT_VERSION:
                for nd in db.neuron_data.values():
                    if NEURON_DATA_ATTRIBUTE_TYPES != {
                        k: type(v) for k, v in nd.items()
                    }:
                        logger.error(
                            f"Failed to load data {version=}.\nPickled data file is inconsistent with source. "
                            f"If running a local server, delete cached pickle files in the data folder and try again."
                        )
                        exit(1)
            gc.enable()
            logger.info(f"Pickle loaded for version {version}")
            return db
    except Exception as e:
        logger.error(f"Failed to load DB for data version {version}: {e}")
        return None


def unpickle_all_neuron_db_versions(data_root_path=DATA_ROOT_PATH):
    return {
        v: unpickle_neuron_db(version=v, data_root_path=data_root_path)
        for v in DATA_SNAPSHOT_VERSIONS
    }


def load_and_pickle_neuron_db_versions(
    data_root_path=DATA_ROOT_PATH,
    versions=DATA_SNAPSHOT_VERSIONS,
    bundled_path=BUNDLED_DATA_PATH,
):
    for v in versions:
        print(f"Loading data for version {v}..")
        db = load_neuron_db(version=v, data_root_path=data_root_path, bundled_path=bundled_path)
        fldr = data_file_path_for_version(version=v, data_root_path=data_root_path)
        os.makedirs(fldr, exist_ok=True)
        pf = f"{fldr}/{NEURON_DB_PICKLE_FILE_NAME}"
        print(f" writing pickle to {pf}..")
        with gzip.open(pf, "wb") as handle:
            pickle.dump(db, handle, protocol=pickle.HIGHEST_PROTOCOL)
        print("Done.")


# generic CSV file reader with settings
def read_csv(filename, num_rows=None, column_idx=None):
    def col_reader(row):
        return row[column_idx]

    def row_reader(row):
        return row

    def read_from(rdr):
        if num_rows is None and column_idx is None:
            return [r for r in rdr]
        else:
            if num_rows is None:
                return [r[column_idx] for r in rdr]
            reader_func = col_reader if column_idx is not None else row_reader
            res = []
            for r in rdr:
                res.append(reader_func(r))
                if len(res) == num_rows:
                    break
            return res

    if filename.lower().endswith(".gz"):
        with gzip.open(filename, "rt") as f:
            reader = csv.reader(f, delimiter=",", quotechar='"')
            return read_from(reader)
    else:
        with open(filename) as fp:
            reader = csv.reader(fp, delimiter=",", quotechar='"')
            return read_from(reader)


def write_csv(filename, rows, compress=False):
    if compress:
        if not filename.lower().endswith(".gz"):
            filename = filename + ".gz"
        with gzip.open(filename, "wt") as f:
            csv.writer(f, delimiter=",").writerows(rows)
    else:
        with open(filename, "wt") as fp:
            csv.writer(fp, delimiter=",").writerows(rows)


if __name__ == "__main__":
    load_and_pickle_neuron_db_versions(versions=[DEFAULT_DATA_SNAPSHOT_VERSION])
