import re
from collections import namedtuple
from contextvars import ContextVar

# The neuron set decides which cells the app works with (search, statistics, heatmaps, partner counts).
# Each request activates one, chosen from the URL, a cookie or the default.
NEURON_SET_ALL = "all"
NEURON_SET_SOMA = "soma"
NEURON_SET_WINDING = "winding"
DEFAULT_NEURON_SET = NEURON_SET_WINDING
PAPER_KEY_PREFIX = "paper-"

NEURON_SET_PARAMETER = "neuron_set"
NEURON_SET_COOKIE_MAX_AGE = 365 * 24 * 60 * 60

WINDING_PAPER_MARKER = "winding"

NeuronSet = namedtuple("NeuronSet", "key label ids")

_active_neuron_set = ContextVar("active_neuron_set", default=None)


def active_neuron_set():
    """The key of the neuron set of the current request, or None outside of a request."""
    return _active_neuron_set.get()


def activate_neuron_set(key):
    return _active_neuron_set.set(key)


def deactivate_neuron_set(token):
    _active_neuron_set.reset(token)


def paper_slug(name):
    return re.sub(r"[^a-z0-9]+", "-", str(name).lower()).strip("-")


def build_neuron_sets(neuron_data):
    """The sets a user can choose from, as an ordered dict of key -> NeuronSet: the Winding et al. 2023
    set (the default, if the data has it), all skeletons, skeletons with a soma, and one set per
    publication. Aggregates of orphaned synaptic sites belong to no set."""
    cells = {rid: nd for rid, nd in neuron_data.items() if not nd["is_aggregate"]}

    winding_paper = None
    by_paper = {}
    for rid, nd in cells.items():
        for paper in nd["papers"]:
            by_paper.setdefault(paper, set()).add(rid)
            if WINDING_PAPER_MARKER in paper.lower():
                winding_paper = winding_paper or paper

    sets = {}
    if winding_paper:
        sets[NEURON_SET_WINDING] = NeuronSet(
            NEURON_SET_WINDING, winding_paper, frozenset(by_paper[winding_paper])
        )
    sets[NEURON_SET_ALL] = NeuronSet(
        NEURON_SET_ALL, "All skeletons", frozenset(cells)
    )
    sets[NEURON_SET_SOMA] = NeuronSet(
        NEURON_SET_SOMA,
        "Skeletons with a soma",
        frozenset(rid for rid, nd in cells.items() if nd["has_soma"]),
    )
    for paper in sorted(by_paper, key=str.lower):
        if paper == winding_paper:
            continue
        key = PAPER_KEY_PREFIX + paper_slug(paper)
        if key in sets:  # two names with the same slug
            continue
        sets[key] = NeuronSet(key, paper, frozenset(by_paper[paper]))
    return sets


def resolve_neuron_set(requested, available_keys):
    """The requested key if it is available, else the default set, else all skeletons."""
    if requested in available_keys:
        return requested
    if DEFAULT_NEURON_SET in available_keys:
        return DEFAULT_NEURON_SET
    return NEURON_SET_ALL
