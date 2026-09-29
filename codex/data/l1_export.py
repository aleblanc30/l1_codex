"""Pure (network-free) logic for exporting the L1 larval EM dataset to Codex files.

The CATMAID/pymaid side lives in scripts/export_l1.py. Everything here works on plain
Python data so it can be tested without a server.
"""

import re
from collections import defaultdict

NT_UNKNOWN = "UNKNOWN"
UNASSIGNED_REGION = "UNASGD"

# Regions are the CATMAID segment volumes (brain hemispheres, SEZ, thoracic and abdominal segments).
# The order defines the priority when a point falls inside more than one volume.
L1_REGIONS = (
    ["BRAIN_L", "BRAIN_R", "SEZ_L", "SEZ_R"]
    + [f"T{i}_{s}" for i in (1, 2, 3) for s in ("L", "R")]
    + [f"A{i}_{s}" for i in range(1, 9) for s in ("L", "R")]
    + [UNASSIGNED_REGION]
)

# Skeletons standing in for unattributed synaptic sites are collapsed into one aggregate per
# role and region. Their ids sit far above any CATMAID skeleton id.
ORPHAN_ID_BASE = 900_000_000
_ROLES = ("pre", "post")
_ROLE_LABELS = {"pre": "presynaptic", "post": "postsynaptic"}

L1_EXPORT_SCHEMA = {
    "neurons.csv.gz": [
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
    "classification.csv.gz": [
        "root_id",
        "flow",
        "super_class",
        "class",
        "sub_class",
        "hemilineage",
        "side",
        "nerve",
    ],
    # one row per (root_id, cell type)
    "cell_types.csv.gz": ["root_id", "primary_type", "additional_type(s)"],
    # one row per (root_id, publication)
    "papers.csv.gz": ["root_id", "paper"],
    # one row per (root_id, raw CATMAID annotation)
    "annotations.csv.gz": ["root_id", "annotation"],
    "skeletons.csv.gz": [
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
    # one row per (pre_root_id, post_root_id, neuropil) tuple
    "connections.csv.gz": [
        "pre_root_id",
        "post_root_id",
        "neuropil",
        "syn_count",
        "nt_type",
    ],
}

_IMAGE_ENDPOINT_TOKENS = ("tile", "stack", "image", "/img", "iiif", "cutout")
_HEMILATERAL_PAIR = re.compile(r"hemilateral_pair_(\d+)_(\d+)")
_PAIRED_WITH = re.compile(r"paired with #(\d+)")
_SEGMENT_VOLUME = re.compile(r"(?P<segment>[AT]\d|SEZ)_(?P<side>left|right)")
_BRAIN_VOLUME = re.compile(r"Brain Hemisphere (?P<side>left|right)")


def region_code(volume_name):
    if volume_name == "cns":
        return None
    match = _BRAIN_VOLUME.fullmatch(volume_name)
    if match:
        return f"BRAIN_{match.group('side')[0].upper()}"
    match = _SEGMENT_VOLUME.fullmatch(volume_name)
    if match:
        return f"{match.group('segment')}_{match.group('side')[0].upper()}"
    raise ValueError(f"Unrecognized CATMAID volume name: {volume_name}")


def assign_regions(num_points, containment):
    """Region code per point. containment maps region code -> list of bools per point."""
    for region in containment:
        if region not in L1_REGIONS:
            raise ValueError(f"Unknown region: {region}")
    ordered = [r for r in L1_REGIONS if r in containment]
    return [
        next((r for r in ordered if containment[r][i]), UNASSIGNED_REGION)
        for i in range(num_points)
    ]


def normalize_side(annotations):
    sides = set()
    for annotation in annotations:
        lowered = annotation.lower()
        if lowered in ("left", "l"):
            sides.add("left")
        elif lowered in ("right", "r"):
            sides.add("right")
    return sides.pop() if len(sides) == 1 else ""


def papers_for(annotations, paper_names):
    return sorted(set(annotations) & set(paper_names))


def cell_types_for(annotations, cell_type_names):
    return sorted(set(annotations) & set(cell_type_names))


def build_mirror_twins(annotations_by_skeleton):
    """Symmetric {skeleton: twin} map from pairing annotations.

    hemilateral_pair_<a>_<b> annotations are applied first, then 'paired with #<id>'
    fills neurons that are still unpaired. Ids outside the dataset are ignored.
    """
    known = set(annotations_by_skeleton)
    hemilateral, paired_with = set(), set()
    for skeleton, annotations in annotations_by_skeleton.items():
        for annotation in annotations:
            match = _HEMILATERAL_PAIR.fullmatch(annotation)
            if match:
                a, b = int(match.group(1)), int(match.group(2))
                hemilateral.add((min(a, b), max(a, b)))
            match = _PAIRED_WITH.fullmatch(annotation)
            if match:
                other = int(match.group(1))
                paired_with.add((min(skeleton, other), max(skeleton, other)))
    twins = {}
    for a, b in sorted(hemilateral) + sorted(paired_with):
        if a == b or a not in known or b not in known:
            continue
        if a in twins or b in twins:
            continue
        twins[a], twins[b] = b, a
    return twins


def orphan_aggregate_id(role, region):
    if role not in _ROLES:
        raise ValueError(f"Invalid role: {role}")
    if region not in L1_REGIONS:
        raise ValueError(f"Invalid region: {region}")
    return ORPHAN_ID_BASE + L1_REGIONS.index(region) * 2 + _ROLES.index(role)


def describe_aggregate(aggregate_id):
    offset = aggregate_id - ORPHAN_ID_BASE
    if offset < 0 or offset >= 2 * len(L1_REGIONS):
        raise ValueError(f"Not an aggregate id: {aggregate_id}")
    return _ROLES[offset % 2], L1_REGIONS[offset // 2]


def orphan_aggregate_name(role, region):
    return f"orphaned synaptic sites ({_ROLE_LABELS[role]}), {region}"


def aggregate_ids_in(connection_rows):
    ids = set()
    for pre, post, *_ in connection_rows:
        for node in (pre, post):
            if node >= ORPHAN_ID_BASE:
                ids.add(node)
    return sorted(ids)


def build_connection_rows(connectors, connector_regions, real_ids):
    """Aggregate connector details into Codex connection rows.

    connectors: dicts with connector_id, pre (skeleton id or None) and posts (list of
    skeleton ids, repeated when a neuron has several postsynaptic sites on the connector).
    Skeletons outside real_ids are unattributed synaptic sites. They are collapsed into
    per-role, per-region aggregates.
    Returns (rows, orphan_stats, skipped) where orphan_stats maps a real neuron to its
    counts of synapses shared with orphaned sites.
    """
    counts = defaultdict(int)
    stats = {}
    skipped = {"no_presynaptic_partner": 0, "both_orphan": 0}

    def neuron_stats(skeleton):
        return stats.setdefault(skeleton, {"orphan_output": 0, "orphan_input": 0})

    for connector in connectors:
        region = connector_regions.get(connector["connector_id"], UNASSIGNED_REGION)
        pre = connector["pre"]
        for post in connector["posts"]:
            if pre is None:
                skipped["no_presynaptic_partner"] += 1
                continue
            pre_is_real, post_is_real = pre in real_ids, post in real_ids
            if not pre_is_real and not post_is_real:
                skipped["both_orphan"] += 1
                continue
            if not post_is_real:
                neuron_stats(pre)["orphan_output"] += 1
            if not pre_is_real:
                neuron_stats(post)["orphan_input"] += 1
            pre_node = pre if pre_is_real else orphan_aggregate_id("pre", region)
            post_node = post if post_is_real else orphan_aggregate_id("post", region)
            counts[(pre_node, post_node, region)] += 1

    rows = [
        [pre, post, region, count, NT_UNKNOWN]
        for (pre, post, region), count in sorted(counts.items())
    ]
    return rows, stats, skipped


def _side_from_region(region):
    if region.endswith("_L"):
        return "left"
    if region.endswith("_R"):
        return "right"
    return ""


def build_export_tables(
    summaries,
    annotations,
    paper_names,
    cell_type_names,
    connection_rows,
    orphan_stats,
    twins,
):
    """Rows (header first) for every file in L1_EXPORT_SCHEMA, keyed by file name."""
    tables = {name: [list(cols)] for name, cols in L1_EXPORT_SCHEMA.items()}
    unknown_scores = [NT_UNKNOWN, "", "", "", "", "", "", ""]

    for summary in sorted(summaries, key=lambda s: s["skeleton_id"]):
        skeleton = summary["skeleton_id"]
        skeleton_annotations = annotations.get(skeleton, [])
        cell_types = cell_types_for(skeleton_annotations, cell_type_names)
        group = (
            cell_types[0]
            if cell_types
            else (summary["position_region"] or UNASSIGNED_REGION)
        )
        stats = orphan_stats.get(skeleton, {})

        tables["neurons.csv.gz"].append([skeleton, group] + unknown_scores)
        tables["classification.csv.gz"].append(
            [skeleton, "", "", "", "", "", normalize_side(skeleton_annotations), ""]
        )
        for cell_type in cell_types:
            tables["cell_types.csv.gz"].append([skeleton, cell_type, ""])
        for paper in papers_for(skeleton_annotations, paper_names):
            tables["papers.csv.gz"].append([skeleton, paper])
        for annotation in skeleton_annotations:
            tables["annotations.csv.gz"].append([skeleton, annotation])
        tables["skeletons.csv.gz"].append(
            [
                skeleton,
                summary["name"],
                summary["node_count"],
                int(bool(summary["has_soma"])),
                int(round(summary["cable_length_nm"])),
                " ".join(str(int(round(c))) for c in summary["position_xyz"]),
                twins.get(skeleton, ""),
                0,
                stats.get("orphan_output", 0),
                stats.get("orphan_input", 0),
            ]
        )

    for aggregate in aggregate_ids_in(connection_rows):
        role, region = describe_aggregate(aggregate)
        name = orphan_aggregate_name(role, region)
        tables["neurons.csv.gz"].append([aggregate, name] + unknown_scores)
        tables["classification.csv.gz"].append(
            [aggregate, "", "", "", "", "", _side_from_region(region), ""]
        )
        tables["skeletons.csv.gz"].append(
            [aggregate, name, "", 0, "", "", "", 1, "", ""]
        )

    tables["connections.csv.gz"].extend(connection_rows)
    return tables


def is_image_endpoint(url):
    """True for URLs that could serve EM image data, which the exporter never requests."""
    lowered = str(url).lower()
    return any(token in lowered for token in _IMAGE_ENDPOINT_TOKENS)


def chunked(items, size):
    if size <= 0:
        raise ValueError("Chunk size must be positive")
    batch = []
    for item in items:
        batch.append(item)
        if len(batch) == size:
            yield batch
            batch = []
    if batch:
        yield batch
