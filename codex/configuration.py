import os

MIN_SYN_THRESHOLD = 5
MIN_NBLAST_SCORE_SIMILARITY = 4
MAX_NEURONS_FOR_DOWNLOAD = 100
MAX_NODES_FOR_PATHWAY_ANALYSIS = 10

# Neuron set views (see codex.data.view_cache) are dropped, least recently used first, when the cells they
# hold together exceed this budget. Each 1,000 cells take roughly 30 MB. 0 means no limit.
NEURON_SET_VIEW_CELL_BUDGET = int(os.environ.get("CODEX_VIEW_CELL_BUDGET", 5000))

APP_ENVIRONMENT = str(os.environ.get("APP_ENVIRONMENT", "DEV"))


class RedirectHomeError(ValueError):
    def __init__(self, msg):
        super().__init__(msg)
