"""Small synthetic dataset in the L1 export schema, as csv.reader would yield it (all strings)."""

from codex.data import catalog
from codex.data.l1_export import NT_UNKNOWN, orphan_aggregate_id

AGGREGATE_ID = orphan_aggregate_id("post", "BRAIN_L")
AGGREGATE_NAME = "orphaned synaptic sites (postsynaptic), BRAIN_L"


def _table(columns, *rows):
    """Header plus rows, where each row is a dict of column -> value (missing means empty)."""
    return [list(columns)] + [[str(row.get(c, "")) for c in columns] for row in rows]


def l1_rows():
    neurons = _table(
        catalog.get_neurons_file_columns(),
        {"root_id": 1001, "group": "MBON-a1", "nt_type": NT_UNKNOWN},
        {"root_id": 1002, "group": "chos_v'ch_a1", "nt_type": NT_UNKNOWN},
        {"root_id": 1003, "group": "A3_L", "nt_type": NT_UNKNOWN},
        {"root_id": AGGREGATE_ID, "group": AGGREGATE_NAME, "nt_type": NT_UNKNOWN},
    )
    classification = _table(
        catalog.get_classification_file_columns(),
        {"root_id": 1001, "side": "left"},
        {"root_id": 1002, "side": "right"},
        {"root_id": 1003},
        {"root_id": AGGREGATE_ID, "side": "left"},
    )
    cell_types = _table(
        catalog.get_cell_types_file_columns(),
        {"root_id": 1001, "primary_type": "MBON-a1"},
        {"root_id": 1002, "primary_type": "chos_v'ch_a1"},
        {"root_id": 1002, "primary_type": "Second, type"},
    )
    papers = _table(
        catalog.get_papers_file_columns(),
        {"root_id": 1001, "paper": "Winding, Pedigo et al. 2023"},
        {"root_id": 1002, "paper": "Winding, Pedigo et al. 2023"},
        {"root_id": 1002, "paper": "Zwart et al. 2016"},
    )
    annotations = _table(
        catalog.get_annotations_file_columns(),
        {"root_id": 1001, "annotation": "Left"},
        {"root_id": 1001, "annotation": "3"},
        {"root_id": 1002, "annotation": "Brain&SEZ <x>"},
        {"root_id": 1002, "annotation": "a, b"},
    )
    skeletons = _table(
        catalog.get_skeletons_file_columns(),
        {
            "root_id": 1001,
            "skeleton_name": "MBON a1 left",
            "node_count": 500,
            "has_soma": 1,
            "length_nm": 12345,
            "position": "10 20 30",
            "mirror_twin_root_id": 1002,
            "is_aggregate": 0,
            "orphan_output_synapses": 2,
            "orphan_input_synapses": 0,
        },
        {
            "root_id": 1002,
            "skeleton_name": "v'ch a1r  ",
            "node_count": 40,
            "has_soma": 0,
            "length_nm": 99,
            "position": "1 2 3",
            "mirror_twin_root_id": 1001,
            "is_aggregate": 0,
        },
        {
            "root_id": 1003,
            "skeleton_name": "frag",
            "node_count": 5,
            "has_soma": 0,
            "is_aggregate": 0,
        },
        {"root_id": AGGREGATE_ID, "skeleton_name": AGGREGATE_NAME, "is_aggregate": 1},
    )
    connections = _table(
        catalog.get_connections_file_columns(),
        _connection(1001, 1002, "A1_L", 3),
        _connection(1002, 1001, "A1_R", 2),
        _connection(1001, AGGREGATE_ID, "BRAIN_L", 5),
        _connection(1003, 1001, "A3_L", 1),
    )
    return {
        "neurons": neurons,
        "classification": classification,
        "cell_types": cell_types,
        "papers": papers,
        "annotations": annotations,
        "skeletons": skeletons,
        "connections": connections,
    }


def _connection(pre, post, neuropil, count, nt_type=NT_UNKNOWN):
    return {
        "pre_root_id": pre,
        "post_root_id": post,
        "neuropil": neuropil,
        "syn_count": count,
        "nt_type": nt_type,
    }


def initialize_kwargs(rows=None):
    """Keyword arguments for initialize_neuron_data built from the fixture (or from rows)."""
    rows = rows or l1_rows()
    return {
        "neuron_file_rows": rows["neurons"],
        "classification_rows": rows["classification"],
        "cell_type_rows": rows["cell_types"],
        "paper_rows": rows["papers"],
        "annotation_rows": rows["annotations"],
        "skeleton_rows": rows["skeletons"],
        "connection_rows": rows["connections"],
    }
