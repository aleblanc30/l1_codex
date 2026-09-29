_CODEX_DATA_SCHEMA = {
    # one row per id
    "neurons": [
        "root_id",
        "group",
        "nt_type",
        "nt_type_score",
        "da_avg",
        "ser_avg",
        "gaba_avg",
        "glut_avg",
        "ach_avg",
        "oct_avg",
    ],
    # one row per id
    "classification": [
        "root_id",
        "flow",
        "super_class",
        "class",
        "sub_class",
        "hemilineage",
        "side",
        "nerve",
    ],
    # one row per (id, cell type)
    "cell_types": ["root_id", "primary_type", "additional_type(s)"],
    # one row per (id, publication)
    "papers": ["root_id", "paper"],
    # one row per (id, raw source annotation)
    "annotations": ["root_id", "annotation"],
    # one row per id
    "skeletons": [
        "root_id",
        "skeleton_name",
        "node_count",
        "has_soma",
        "length_nm",
        "position",
        "mirror_twin_root_id",
        "is_aggregate",
        "orphan_output_synapses",
        "orphan_input_synapses",
    ],
    # one row per (pre_root_id,post_root_id,neuropil) tuple
    "connections": [
        "pre_root_id",
        "post_root_id",
        "neuropil",
        "syn_count",
        "nt_type",
    ],
}


def get_data_schema():
    return {table: list(columns) for table, columns in _CODEX_DATA_SCHEMA.items()}


def get_neurons_file_columns():
    return list(_CODEX_DATA_SCHEMA["neurons"])


def get_classification_file_columns():
    return list(_CODEX_DATA_SCHEMA["classification"])


def get_cell_types_file_columns():
    return list(_CODEX_DATA_SCHEMA["cell_types"])


def get_papers_file_columns():
    return list(_CODEX_DATA_SCHEMA["papers"])


def get_annotations_file_columns():
    return list(_CODEX_DATA_SCHEMA["annotations"])


def get_skeletons_file_columns():
    return list(_CODEX_DATA_SCHEMA["skeletons"])


def get_connections_file_columns():
    return list(_CODEX_DATA_SCHEMA["connections"])
