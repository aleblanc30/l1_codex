# Codex - Connectome Data Explorer for FlyWire

![Tests Passing](https://img.shields.io/badge/tests-passing-brightgreen)
![Coverage](https://img.shields.io/badge/coverage-67%25-yellowgreen)

## Description

[Codex](https://codex.flywire.ai) is a web application for exploring and analyzing neurons and
annotations from the
[FlyWire Whole Brain Connectome](https://flywire.ai).

## Setup

Python 3.9 or later is required.

We recommend using an environment manager such as [Poetry](https://python-poetry.org/):

```sh
poetry install
```

### Download and initialize the FlyWire connectome data (initially or upon version updates)
```bash
poetry run ./scripts/make_data.sh
```

### Export the L1 larval dataset from CATMAID (optional, maintainers only)

The exporter reads the public L1 CATMAID project through
[pymaid](https://github.com/navis-org/pymaid) and writes Codex data files. It requests
skeletons, annotations, connectors and region volumes only, never EM image data, and it
throttles and caches its requests. Run it once per data release and host the output.

```sh
poetry install --with export
poetry run python scripts/export_l1.py --out-dir static/data/l1_export
```

Use `--limit 50` for a trial run of the pipeline. Set `CATMAID_API_TOKEN` for servers that
require a token.

## Run service locally

```bash
poetry run ./scripts/run_local.sh
```

To run in [Flask debug mode](https://flask.palletsprojects.com/en/2.2.x/debugging/#the-built-in-debugger)

```sh
poetry run ./scripts/run_local_dev.sh
```

Navigate to [localhost:5000](http://localhost:5000)

## Deployment

Codex is a Flask application, so it needs a host that runs Python. GitHub Pages only serves static
files, and is used here only for the neuroglancer data (`data/l1_skeletons` and `data/l1_meshes`), which
the 3D viewer links read from `raw.githubusercontent.com`.

The app needs about 200 MB of memory and starts in under a second. The repository contains a
`Dockerfile` that runs it with gunicorn, and a `render.yaml` for [Render](https://render.com), whose free
web services sleep when idle and wake on the next request:

1. In Render, choose New, then Blueprint, and select this repository and the `main` branch.
2. Render builds the image and generates `FLASK_SECRET_KEY`. Nothing else has to be set.

Any other host that runs Docker images works the same way: set `FLASK_SECRET_KEY` to a random secret and
give the container the port to listen on in `PORT`. Optional settings:

- `CODEX_DATA_REF`: branch or tag that the viewer links read the skeleton and mesh files from (default `main`)
- `CODEX_DATA_HOST_URL`: another host for those files
- `CODEX_NEUROGLANCER_URL`: another neuroglancer deployment (default: the public demo instance)
- `CODEX_DATA_URL`: base URL of hosted raw data files, if they should not come from the repository

## Testing before posting a PR or merging (please fork - do not create branches in the main repo)

### Manual UI testing (Required)

Run service locally and click around in all pages

### Unit tests & code coverage (Required)

```sh
poetry run ./scripts/run_unit_tests.sh
```
If test status or coverage percentage change, update the static badges above

## Linting / code formatting

```sh
poetry run ./scripts/lint.sh
```
