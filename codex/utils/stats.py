from collections import defaultdict, namedtuple

from codex.data.brain_regions import NEUROPIL_DESCRIPTIONS
from codex.data.neurotransmitters import NEURO_TRANSMITTER_NAMES
from codex.utils.formatting import nanos_to_formatted_micros, display


def group_counts(count_pairs):
    key = f"{len(count_pairs)} others"
    val = sum([p[1] for p in count_pairs])
    return key, val


def make_chart_from_counts(
    chart_type,
    key_title,
    val_title,
    counts_dict,
    colors_dict=None,  # keyed by count_dict keys
    descriptions_dict=None,  # keyed by count_dict keys, used in tooltips
    search_filter="",
):
    sorted_counts = (
        sorted(counts_dict.items(), key=lambda p: p[1], reverse=True)
        if chart_type == "bar"
        else sorted(counts_dict.items(), key=lambda p: p[0])
    )

    if chart_type == "bar" and len(sorted_counts) > 10:
        sorted_counts = sorted_counts[:10]

    height_px = (
        max(300, min(400, 150 + 4 * len(counts_dict))) if chart_type == "bar" else 400
    )

    def _color(key):
        return colors_dict.get(key) if colors_dict else None

    def _tooltip(key):
        return (
            f"<b>{key}</b><br>{descriptions_dict.get(key)}<br><b>{counts_dict[key]}</b>"
            if descriptions_dict
            else None
        )

    return {
        "type": chart_type,
        "searchable": bool(search_filter),
        "search_filter": search_filter,
        "height_px": height_px,
        "data": [
            [
                key_title,
                val_title,
                {"role": "style"},
                {"type": "string", "role": "tooltip", "p": {"html": "true"}},
            ]
        ]
        + [[k, c, _color(k), _tooltip(k)] for k, c in sorted_counts],
    }


def make_chart_from_list(
    chart_type,
    key_title,
    val_title,
    item_list,
    descriptions_dict=None,
    search_filter="",
):
    counts = defaultdict(int)
    for i in item_list:
        counts[i] += 1
    return make_chart_from_counts(
        chart_type=chart_type,
        key_title=key_title,
        val_title=val_title,
        counts_dict=counts,
        descriptions_dict=descriptions_dict,
        search_filter=search_filter,
    )


def _make_data_charts(data_list):
    StatGroupProps = namedtuple(
        "StatGroupProps", "title filter_key type descriptions", defaults=(None,)
    )
    stat_groups = {
        "nt_type": StatGroupProps(
            "Neurotransmitter Types", "nt_type", "bar", NEURO_TRANSMITTER_NAMES
        ),
        "input_neuropils": StatGroupProps(
            "Top Input Regions", "input_neuropil", "bar", NEUROPIL_DESCRIPTIONS
        ),
        "output_neuropils": StatGroupProps(
            "Top Output Regions", "output_neuropil", "bar", NEUROPIL_DESCRIPTIONS
        ),
    }
    stat_groups.update(
        {
            k: StatGroupProps(display(k), k, "donut")
            for k in ["side", "flow", "super_class"]
        }
    )
    stat_groups.update(
        {
            k: StatGroupProps(display(k), k, "bar")
            for k in [
                "class",
                "sub_class",
                "cell_type",
                "nerve",
                "hemilineage",
                "connectivity_tag",
            ]
        }
    )

    stat_lists = {k: [] for k in stat_groups.keys()}
    unknown_key = "Unknown"

    for d in data_list:
        for k, props in stat_groups.items():
            val = d[k]
            if isinstance(val, list):
                stat_lists[k].extend(val)
            elif (
                val or props.type == "donut"
            ):  # donut charts should sum up to 100%, so we include missing values
                stat_lists[k].append(val or unknown_key)

    result = {}

    for k, props in stat_groups.items():
        if stat_lists[k]:
            result[props.title] = make_chart_from_list(
                chart_type=props.type,
                key_title=props.title,
                val_title="Num Cells",
                item_list=stat_lists[k],
                search_filter=props.filter_key,
                descriptions_dict=props.descriptions,
            )

    return result


def _make_data_stats(neuron_data):
    classified_neurons = 0
    total_length = 0
    total_area = 0
    total_volume = 0
    for nd in neuron_data:
        if nd["class"]:
            classified_neurons += 1
        total_length += nd["length_nm"]
        total_area += nd["area_nm"]
        total_volume += nd["size_nm"]

    result = {
        "": {
            "Cells": len(neuron_data),
            "- Classified": classified_neurons,
            "- Combined length": (
                nanos_to_formatted_micros(total_length, 1) if neuron_data else "NA"
            ),
            "- Combined area": (
                nanos_to_formatted_micros(total_area, 2) if neuron_data else "NA"
            ),
            "- Combined volume": (
                nanos_to_formatted_micros(total_volume, 3) if neuron_data else "NA"
            ),
        }
    }
    return result


def format_for_display(dict_of_dicts):
    def _format_val(val):
        return display(val) if isinstance(val, int) else val

    def _format_dict(dct):
        return {k: _format_val(v) for k, v in dct.items()}

    return {k: _format_dict(d) for k, d in dict_of_dicts.items()}


def compile_data(neuron_data, search_query, case_sensitive, match_words, data_version):
    stats_caption = []
    if search_query:
        stats_caption.append(f"search query: '{search_query}'")
    if case_sensitive:
        stats_caption.append("case sensitive")
    if match_words:
        stats_caption.append("match words")
    stats_caption.append(f"data version: {data_version}")
    caption = "Stats for " + ", ".join(stats_caption)

    data_stats = _make_data_stats(neuron_data)
    data_stats = format_for_display(data_stats)

    data_charts = _make_data_charts(neuron_data)

    return caption, data_stats, data_charts


def jaccard_weighted(d1, d2):
    if not d1 or not d2:
        return 0
    combined_key_set = set(d1.keys()).union(d2.keys())
    min_sum = 0
    max_sum = 0
    for ck in combined_key_set:
        v1 = d1.get(ck, 0)
        v2 = d2.get(ck, 0)
        min_sum += min(v1, v2)
        max_sum += max(v1, v2)
    return min_sum / max_sum


def jaccard_binary(s1, s2):
    if not s1 and not s2:
        return 0
    if len(s1) <= len(s2):
        small_set, large_set = s1, s2
    else:
        small_set, large_set = s2, s1
    int_size = 0
    for e in small_set:
        if e in large_set:
            int_size += 1

    return int_size / (len(s1) + len(s2) - int_size)
