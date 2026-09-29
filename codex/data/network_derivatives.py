from collections import defaultdict

HEATMAP_GROUP_BY_ATTRIBUTES = [
    "side",
    "group",
    "flow",
    "nt_type",
    "super_class",
    "class",
    "sub_class",
]
NETWORK_GROUP_BY_ATTRIBUTES = [
    "side",
    "group",
    "flow",
    "nt_type",
    "super_class",
    "class",
    "sub_class",
]


def derive_connection_data(neuron_attributes, neuron_connection_rows):
    """Sets the partner counts, synapse counts and regions of every neuron from the connection rows
    ([pre, post, neuropil, syn_count, nt_type]), and returns the synapse, connection and reciprocal
    connection counts grouped by the heatmap attributes.

    Used for the whole dataset and for the subsets shown for a neuron set, so that the counts of a
    subset only reflect the connections inside it."""
    input_neuropils = defaultdict(set)
    output_neuropils = defaultdict(set)
    input_cells = defaultdict(set)
    output_cells = defaultdict(set)
    input_synapses = defaultdict(int)
    output_synapses = defaultdict(int)
    for from_node, to_node, neuropil, syn_count, _ in neuron_connection_rows:
        input_cells[to_node].add(from_node)
        output_cells[from_node].add(to_node)
        input_neuropils[to_node].add(neuropil)
        output_neuropils[from_node].add(neuropil)
        input_synapses[to_node] += syn_count
        output_synapses[from_node] += syn_count

    for rid, nd in neuron_attributes.items():
        nd["input_neuropils"] = sorted(input_neuropils[rid])
        nd["output_neuropils"] = sorted(output_neuropils[rid])
        nd["input_synapses"] = input_synapses[rid]
        nd["output_synapses"] = output_synapses[rid]
        nd["input_cells"] = len(input_cells[rid])
        nd["output_cells"] = len(output_cells[rid])

    grouped_synapse_counts = {
        attr: defaultdict(int) for attr in HEATMAP_GROUP_BY_ATTRIBUTES
    }
    grouped_connection_counts = {
        attr: defaultdict(int) for attr in HEATMAP_GROUP_BY_ATTRIBUTES
    }
    grouped_reciprocal_connection_counts = {
        attr: defaultdict(int) for attr in HEATMAP_GROUP_BY_ATTRIBUTES
    }
    connected_pairs = set()
    # update synapse counts and collect connected pairs (de-duped across regions)
    for r in neuron_connection_rows:
        from_neuron = neuron_attributes[r[0]]
        to_neuron = neuron_attributes[r[1]]
        connected_pairs.add((r[0], r[1]))
        for attr in HEATMAP_GROUP_BY_ATTRIBUTES:
            grouped_synapse_counts[attr][(from_neuron[attr], to_neuron[attr])] += r[3]
    # update connection counts
    for p in connected_pairs:
        from_neuron = neuron_attributes[p[0]]
        to_neuron = neuron_attributes[p[1]]
        for attr in HEATMAP_GROUP_BY_ATTRIBUTES:
            grouped_connection_counts[attr][(from_neuron[attr], to_neuron[attr])] += 1
    # update reciprocal connection counts, leaving out aggregates of orphaned sites
    reciprocal_connections = set(
        [
            p
            for p in connected_pairs
            if (p[1], p[0]) in connected_pairs
            and not neuron_attributes[p[0]]["is_aggregate"]
            and not neuron_attributes[p[1]]["is_aggregate"]
        ]
    )
    for p in reciprocal_connections:
        from_neuron = neuron_attributes[p[0]]
        to_neuron = neuron_attributes[p[1]]
        for attr in HEATMAP_GROUP_BY_ATTRIBUTES:
            from_group = from_neuron[attr]
            to_group = to_neuron[attr]
            grouped_reciprocal_connection_counts[attr][(from_group, to_group)] += 1
            grouped_reciprocal_connection_counts[attr][(to_group, from_group)] += 1

    return (
        grouped_synapse_counts,
        grouped_connection_counts,
        grouped_reciprocal_connection_counts,
        len(reciprocal_connections),
        len(connected_pairs),
    )
