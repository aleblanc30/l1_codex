from collections import defaultdict

from codex.data.auto_naming import assign_names_from_annotations
from codex.data.brain_regions import REGIONS
from codex.data.catalog import (
    get_annotations_file_columns,
    get_cell_types_file_columns,
    get_classification_file_columns,
    get_connections_file_columns,
    get_neurons_file_columns,
    get_papers_file_columns,
    get_skeletons_file_columns,
)
from codex.data.network_derivatives import (  # noqa: F401 (re-exported)
    HEATMAP_GROUP_BY_ATTRIBUTES,
    NETWORK_GROUP_BY_ATTRIBUTES,
    derive_connection_data,
)
from codex.data.neuron_data import NeuronDB
from codex.data.neurotransmitters import NEURO_TRANSMITTER_NAMES, NT_UNKNOWN
from codex.utils.formatting import clean_display_name, make_web_safe
from codex import logger

NEURON_DATA_ATTRIBUTE_TYPES = {
    # cell type if there is one, else the region of the cell's anchor point
    "group": str,
    # group + running id (to make unique)
    "name": str,
    # CATMAID skeleton id. Aggregates of orphaned synaptic sites use ids from ORPHAN_ID_BASE.
    "root_id": int,
    # the name of the skeleton in the CATMAID project
    "skeleton_name": str,
    # optional mirror/twin cell (LR matching)
    "mirror_twin_root_id": int,
    # shape-based similarity, cell id -> 1-digit score (none in the L1 data)
    "similar_cell_scores": dict,
    # neurotransmitter type info with prediction confidence scores
    "nt_type": str,
    "nt_type_score": float,
    "ach_avg": float,
    "gaba_avg": float,
    "glut_avg": float,
    "ser_avg": float,
    "oct_avg": float,
    "da_avg": float,
    # hierarchical annotations & classification
    "flow": str,
    "super_class": str,
    "class": str,
    "sub_class": str,
    "cell_type": list,
    "hemilineage": str,
    "nerve": str,
    "side": str,
    # publications that reconstructed the cell, and every raw annotation from the source project
    "papers": list,
    "annotations": list,
    # I/O counts + regions and network properties
    "input_cells": int,
    "input_synapses": int,
    "input_neuropils": list,
    "output_cells": int,
    "output_synapses": int,
    "output_neuropils": list,
    "connectivity_tag": list,
    # Anchor point (soma if there is one, else the root node) in nanometers, "x y z"
    "position": list,
    # Skeleton measurements
    "length_nm": int,
    "area_nm": int,
    "size_nm": int,
    "node_count": int,
    "has_soma": int,
    # Synaptic sites whose partner was never attributed to a cell, collapsed into one
    # aggregate cell per role and region (is_aggregate), and per-cell counts of synapses with them
    "is_aggregate": int,
    "orphan_output_synapses": int,
    "orphan_input_synapses": int,
    # Synapse totals in the whole dataset, whatever neuron set is shown
    "total_input_synapses": int,
    "total_output_synapses": int,
}

# Names come from the source project and are shown as they are apart from whitespace
VERBATIM_ATTRIBUTES = {"group", "skeleton_name"}

def _check_header(rows, expected_columns, table):
    if not rows or list(rows[0]) != expected_columns:
        raise ValueError(
            f"Unexpected columns in the {table} data: {rows[0] if rows else 'no header'}"
        )
    return {c: i for i, c in enumerate(rows[0])}


def _get_value(row, col_index, attr_name):
    raw = row[col_index[attr_name]]
    if attr_name in VERBATIM_ATTRIBUTES:
        attr_val = clean_display_name(raw)
    else:
        attr_val = make_web_safe(raw)
    attr_type = NEURON_DATA_ATTRIBUTE_TYPES[attr_name]
    if not attr_val:
        return attr_type()
    elif attr_type == list:
        return attr_val.split(",")
    else:
        return attr_type(attr_val)


def initialize_neuron_data(
    neuron_file_rows,
    classification_rows,
    cell_type_rows,
    paper_rows,
    annotation_rows,
    skeleton_rows,
    connection_rows,
):
    neuron_attributes = {}
    neuron_connection_rows = []

    def neuron_for(root_id, table):
        if root_id not in neuron_attributes:
            raise ValueError(f"Unknown root id {root_id} in the {table} data")
        return neuron_attributes[root_id]

    logger.debug("App initialization processing neuron data..")
    neurons_column_index = _check_header(
        neuron_file_rows, get_neurons_file_columns(), "neurons"
    )
    for r in neuron_file_rows[1:]:
        root_id = _get_value(r, neurons_column_index, "root_id")
        if root_id in neuron_attributes:
            raise ValueError(f"Duplicate root id {root_id} in the neurons data")
        neuron_attributes[root_id] = {
            attr_name: (
                _get_value(r, neurons_column_index, attr_name)
                if attr_name in neurons_column_index
                else attr_type()
            )
            for attr_name, attr_type in NEURON_DATA_ATTRIBUTE_TYPES.items()
        }

    def load_per_neuron_columns(rows, columns, table):
        column_index = _check_header(rows, columns, table)
        for r in rows[1:]:
            root_id = _get_value(r, column_index, "root_id")
            neuron_for(root_id, table).update(
                {
                    attr_name: _get_value(r, column_index, attr_name)
                    for attr_name in columns[1:]
                }
            )

    logger.debug("App initialization processing classification and skeleton data..")
    load_per_neuron_columns(
        classification_rows, get_classification_file_columns(), "classification"
    )
    load_per_neuron_columns(skeleton_rows, get_skeletons_file_columns(), "skeletons")

    def load_values_per_neuron(rows, columns, table, value_column, attr_name):
        column_index = _check_header(rows, columns, table)
        for r in rows[1:]:
            root_id = int(r[column_index["root_id"]])
            value = r[column_index[value_column]]
            if value:
                neuron_for(root_id, table)[attr_name].append(value)

    logger.debug("App initialization processing cell types, papers and annotations..")
    load_values_per_neuron(
        cell_type_rows,
        get_cell_types_file_columns(),
        "cell types",
        "primary_type",
        "cell_type",
    )
    load_values_per_neuron(
        paper_rows, get_papers_file_columns(), "papers", "paper", "papers"
    )
    load_values_per_neuron(
        annotation_rows,
        get_annotations_file_columns(),
        "annotations",
        "annotation",
        "annotations",
    )

    logger.debug("App initialization loading connections..")
    _check_header(connection_rows, get_connections_file_columns(), "connections")
    for r in connection_rows[1:]:
        from_node, to_node, neuropil, syn_count, nt_type = (
            int(r[0]),
            int(r[1]),
            r[2].upper(),
            int(r[3]),
            r[4].upper(),
        )
        if from_node not in neuron_attributes or to_node not in neuron_attributes:
            raise ValueError(f"Connection between unknown cells: {r}")
        if nt_type not in NEURO_TRANSMITTER_NAMES and nt_type != NT_UNKNOWN:
            raise ValueError(f"Unknown neurotransmitter type in connection: {r}")
        if neuropil not in REGIONS:
            raise ValueError(f"Unknown region in connection: {r}")
        neuron_connection_rows.append(
            [from_node, to_node, neuropil, syn_count, nt_type]
        )

    logger.debug("App initialization augmenting and calculating grouped counts..")
    (
        grouped_synapse_counts,
        grouped_connection_counts,
        grouped_reciprocal_connection_counts,
        num_reciprocal_connections,
        num_connected_pairs,
    ) = derive_connection_data(neuron_attributes, neuron_connection_rows)
    # Synapse totals of the whole dataset. Shares of orphaned synapses are relative to these, so they do
    # not change when a neuron set restricts the connections.
    for nd in neuron_attributes.values():
        nd["total_input_synapses"] = nd["input_synapses"]
        nd["total_output_synapses"] = nd["output_synapses"]
    logger.debug(
        f"App initialization found {num_reciprocal_connections} reciprocal connections out of {num_connected_pairs}.."
    )

    assign_names_from_annotations(neuron_attributes)
    for nd in neuron_attributes.values():
        if nd["is_aggregate"]:
            nd["name"] = nd["skeleton_name"]

    return NeuronDB(
        neuron_attributes=neuron_attributes,
        neuron_connection_rows=neuron_connection_rows,
        grouped_synapse_counts=grouped_synapse_counts,
        grouped_connection_counts=grouped_connection_counts,
        grouped_reciprocal_connection_counts=grouped_reciprocal_connection_counts,
    )
