"""Random cells for the "Try with sample cells" buttons of the network and pathways pages.

The samples come from the database of the current neuron set, so they always exist in the data being
shown, and they are built to be connected so that the page has something to draw."""

from random import Random

from codex.configuration import MIN_SYN_THRESHOLD
from codex.utils.graph_algos import reachable_nodes

MIN_PARTNERS_OF_A_SEED = 3
MAX_PATHWAY_ATTEMPTS = 25
# Pathways of two or three steps are the interesting ones to look at
PREFERRED_DISTANCES = (2, 3)
SEARCH_DEPTH = 4


def sample_network_cells(neuron_db, rng=None, size=6, min_synapse_count=MIN_SYN_THRESHOLD):
    """A well-connected cell followed by some of its strongest partners, upstream and downstream.
    Empty if no cell has enough partners (with at least min_synapse_count synapses, or 1 if
    the threshold leaves nothing)."""
    rng = rng or Random()
    for threshold in dict.fromkeys([min_synapse_count, 1]):
        ins, outs = neuron_db.input_output_partners_with_synapse_counts(
            min_syn_count=threshold
        )

        def strengths(rid):
            combined = {}
            for partners in (ins.get(rid, {}), outs.get(rid, {})):
                for partner, count in partners.items():
                    combined[partner] = max(combined.get(partner, 0), count)
            return combined

        seeds = sorted(
            rid
            for rid in neuron_db.neuron_data
            if rid not in neuron_db.aggregate_ids
            and len(strengths(rid)) >= MIN_PARTNERS_OF_A_SEED
        )
        if not seeds:
            continue
        # cells with a cell type make a better demonstration than anonymous ones
        seeds = [r for r in seeds if neuron_db.neuron_data[r]["cell_type"]] or seeds
        seed = rng.choice(seeds)
        partners = sorted(strengths(seed).items(), key=lambda p: (-p[1], p[0]))
        # choose among the strongest ones, so that samples differ from click to click
        pool = [rid for rid, _ in partners[: 2 * (size - 1)]]
        return [seed] + rng.sample(pool, min(size - 1, len(pool)))
    return []


def sample_pathway_cells(neuron_db, rng=None, num_sources=3, num_targets=5):
    """Source cells and target cells for a table of pathway lengths, such that the targets can be
    reached from the sources. Targets are two or three steps away when such cells exist, otherwise
    further or nearer ones. Returns two empty lists if the database has no connections."""
    rng = rng or Random()
    outs = neuron_db.output_sets()
    candidates = sorted(
        rid
        for rid, partners in outs.items()
        if rid not in neuron_db.aggregate_ids and len(partners) >= MIN_PARTNERS_OF_A_SEED
    )
    if not candidates:
        candidates = sorted(
            rid
            for rid, partners in outs.items()
            if rid not in neuron_db.aggregate_ids and partners
        )
    fallback = ([], [])
    for _ in range(MAX_PATHWAY_ATTEMPTS):
        if not candidates:
            break
        sources = rng.sample(candidates, min(num_sources, len(candidates)))
        reached = reachable_nodes(sources, outs, max_depth=SEARCH_DEPTH)
        by_distance = {}
        for rid, distance in reached.items():
            if rid not in sources and rid not in neuron_db.aggregate_ids:
                by_distance.setdefault(distance, []).append(rid)
        preferred = sorted(
            rid for d in PREFERRED_DISTANCES for rid in by_distance.get(d, [])
        )
        if preferred:
            return sorted(sources), sorted(rng.sample(preferred, min(num_targets, len(preferred))))
        nearer = sorted(by_distance.get(1, []))
        if nearer and not fallback[1]:
            fallback = (
                sorted(sources),
                sorted(rng.sample(nearer, min(num_targets, len(nearer)))),
            )
    return fallback
