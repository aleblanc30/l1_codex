from functools import lru_cache

from codex.data.l1_export import L1_REGIONS, UNASSIGNED_REGION
from codex.utils.parsing import tokenize

from codex import logger

LEFT = "Left"
RIGHT = "Right"
CENTER = "Center"
HEMISPHERES = [LEFT, RIGHT, CENTER]

# CATMAID volume ids of the segment meshes
_VOLUME_IDS = {
    "BRAIN_L": 61,
    "BRAIN_R": 62,
    "SEZ_L": 79,
    "SEZ_R": 80,
    "T1_L": 81,
    "T1_R": 82,
    "T2_L": 99,
    "T2_R": 100,
    "T3_L": 101,
    "T3_R": 102,
}
_VOLUME_IDS.update(
    {f"A{i}_{s}": 83 + 2 * (i - 1) + k for i in range(1, 9) for k, s in enumerate("LR")}
)

_ORDINALS = ["first", "second", "third", "fourth", "fifth", "sixth", "seventh", "eighth"]
_DESCRIPTIONS = {
    "BRAIN": "brain hemisphere",
    "SEZ": "subesophageal zone",
    UNASSIGNED_REGION: "unassigned",
}
_DESCRIPTIONS.update({f"T{i}": f"{_ORDINALS[i - 1]} thoracic segment" for i in (1, 2, 3)})
_DESCRIPTIONS.update({f"A{i}": f"{_ORDINALS[i - 1]} abdominal segment" for i in range(1, 9)})


def _without_suffix(region):
    return region[:-2] if region.endswith(("_L", "_R")) else region


REGIONS = {
    # region abbreviation: [CATMAID volume id (-1 if none), description]
    region: [_VOLUME_IDS.get(region, -1), _DESCRIPTIONS[_without_suffix(region)]]
    for region in L1_REGIONS
}

REGION_CATEGORIES = {
    "brain hemispheres": ["BRAIN_R", "BRAIN_L"],
    "subesophageal zone": ["SEZ_R", "SEZ_L"],
    "thoracic segments": [f"T{i}_{s}" for i in (1, 2, 3) for s in "RL"],
    "abdominal segments": [f"A{i}_{s}" for i in range(1, 9) for s in "RL"],
    "other regions": [UNASSIGNED_REGION],
}

_COLORS_BY_REGION = {
    "BRAIN": "#4c78dd",
    "SEZ": "#7a4fe0",
    "T1": "#0b8f88",
    "T2": "#12a8a0",
    "T3": "#2ec4bb",
    "A1": "#d9480f",
    "A2": "#e8590c",
    "A3": "#f76707",
    "A4": "#fd7e14",
    "A5": "#ff922b",
    "A6": "#ffa94d",
    "A7": "#ffc078",
    "A8": "#ffd43b",
    UNASSIGNED_REGION: "#ff0000",
}
COLORS = {r: _COLORS_BY_REGION[_without_suffix(r)] for r in L1_REGIONS}


@lru_cache
def neuropil_hemisphere(pil):
    pil = pil.upper()
    if pil.endswith("_L"):
        return LEFT
    elif pil.endswith("_R"):
        return RIGHT
    else:
        return CENTER


def without_side_suffix(pil):
    pil = pil.upper()
    return pil[:-2] if pil.endswith("_L") or pil.endswith("_R") else pil


def neuropil_description(txt):
    pil = match_to_neuropil(txt)
    if pil not in REGIONS:
        return pil or "Unknown brain region"
    val = REGIONS[pil]
    hs = neuropil_hemisphere(pil)
    return val[1] if hs == CENTER else f"{hs.lower()} {val[1]}"


# find a matching neuropil from free-form text. if no matches, return unchanged
def match_to_neuropil(txt):
    nset = lookup_neuropil_set(txt)
    if len(nset) == 1:
        return nset.pop()
    else:
        if txt not in HEMISPHERES:
            logger.error(f"Could not match a single neuropil to {txt}: got {nset}")
        return txt


# find a set of matching neuropils from free-form text
def lookup_neuropil_set(txt):
    if not txt:
        return None

    txt_uc = txt.upper()
    txt_lc = txt.lower()

    if txt_uc in REGIONS:
        return {txt_uc}

    prefix_regions = set([k for k in REGIONS.keys() if k.startswith(txt_uc)])
    if prefix_regions:
        return prefix_regions

    for hs in HEMISPHERES:
        if hs.lower() == txt_lc:
            return set(
                [rgn for rgn in REGIONS.keys() if neuropil_hemisphere(rgn) == hs]
            )

    txt_lc_tokens = set(tokenize(txt_lc))
    token_wise_matched_regions = set()
    for r, v in REGIONS.items():
        rgn_tokens = set(tokenize(v[1].lower()))
        rgn_tokens.add(neuropil_hemisphere(r).lower())
        if txt_lc_tokens.issubset(rgn_tokens):
            token_wise_matched_regions.add(r)
    if token_wise_matched_regions:
        return token_wise_matched_regions

    return set()


NEUROPIL_DESCRIPTIONS = {k: neuropil_description(k) for k in REGIONS.keys()}


def hemisphere_categories(hemisphere):
    categories = []

    for category in REGION_CATEGORIES.items():
        regions = []

        for region_id in category[1]:
            if neuropil_hemisphere(region_id) == hemisphere:
                segment_id = REGIONS[region_id][0]
                description = REGIONS[region_id][1]
                regions.append(
                    {
                        "segment_id": segment_id,
                        "id": region_id,
                        "description": description,
                    }
                )

        if len(regions) > 0:
            categories.append({"name": category[0], "regions": regions})

    return categories


REGIONS_JSON = {h: hemisphere_categories(h) for h in HEMISPHERES}
