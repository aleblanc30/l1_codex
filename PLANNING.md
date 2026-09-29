# Planning: adapting Codex to the L1 larval dataset

Tick items off as they are completed. Keep the decisions and facts sections current, since the survey scripts that produced them were run in a temporary workspace and are not in the repository.

## Goal and scope

Codex becomes an explorer for the L1 larval Drosophila EM dataset (public CATMAID project 1 on `https://l1em.catmaid.virtualflybrain.org`), replacing FlyWire. There is a single dataset and no dataset switching. The app never queries CATMAID at runtime. A maintainer runs an offline exporter once per data release, hosts the output separately, and the app loads the hosted files. No part of the tooling may request EM image data.

## Settled decisions

- All 5,013 skeletons are exported, fragments included, and filtering happens in the GUI.
- The filter is global: it applies to search, heatmaps and partner counts, and aggregates are recomputed per request. The default view is the Winding, Pedigo et al. 2023 set (3,066 neurons), with the full set one filter change away.
- Cell types are the `MB nomenclature` sub-annotations, kept verbatim as a list. Original skeleton names are kept as a separate attribute. Numeric annotations stay only in the raw annotation list.
- Publications are the 26 sub-annotations of `papers`, stored as a multi-valued attribute.
- Neurotransmitter is `UNKNOWN` for every neuron until a literature search fills a curated table.
- Regions are the 26 CATMAID segment volumes (brain hemispheres, SEZ, T1 to T3, A1 to A8, left and right), assigned per synapse by point-in-mesh lookup, with `UNASGD` outside every mesh. Neuropil-level innervation comes later from a curated table built from the papers.
- Synaptic sites whose partner is a single-node placeholder skeleton are collapsed into one aggregate node per role and region (54 in total, ids from 900,000,000), flagged as aggregates and excluded from pathway search, motif search and reciprocal counts. Each real neuron carries counts of its synapses to such sites.
- Mirror twins come from `hemilateral_pair_<id>_<id>` and `paired with #<id>` annotations.
- CATMAID links replace the neuroglancer links. Thumbnails and mesh views are hidden for now.
- Tests are written before the implementation.

## Facts from the survey

- The project lists 5,013 skeletons. Node counts: 4,926 above 10, 4,179 above 500, 3,617 above 1,000, 329 above 5,000. 4,375 skeletons carry a `soma` tag.
- 14,584 annotations exist, mostly single-user working notes. 26 publications cover every neuron, and the Winding 2023 set has 3,066 neurons.
- `MB nomenclature` has 856 sub-annotations covering 1,203 neurons. Numeric annotation names are carried by real skeletons but their meaning is unknown, and they are not skeleton ids.
- The 27 volumes are coarse anatomical segments (200 to 900 vertices each). There are no neuropil meshes.
- Placeholder skeletons (ids above 22.3 million, named `Placeholder Neuron N`) have one node and one connector each. About 93% are postsynaptic and 24 of 25 probed lie inside the CNS mesh. The Winding et al. paper reports that 75% of annotated brain synaptic sites were linked to a neuron and that the rest were mostly small dendritic fragments.
- The full export holds 977,369 synapse links in 162,492 connection rows. For the Winding set, 44% of output links go to orphaned sites and 14% of input links come from them. For the other neurons the figures are 71% and 48%.

## Checklist

### Phase 0: survey of the L1 project

- [x] Skeleton counts, annotations, node tags and volumes
- [x] Annotation hierarchy for papers and MB nomenclature
- [x] Synapse assignment test against the segment volumes
- [x] Sizing of the connector and partner fetch
- [x] Nature of the placeholder skeletons

### Phase 1: exporter

- [x] Tests for the pure module (`tests/unit/test_l1_export.py`, 54 passing)
- [x] Pure module `codex/data/l1_export.py`
- [x] Throttled, cached pymaid script `scripts/export_l1.py` with an image-endpoint guard
- [x] Trial export of 50 neurons
- [x] Full export committed under `data/l1_export/`
- [ ] Decide where to host the export permanently, and upload it (a copy was delivered for Drive)
- [ ] Fill `side` from soma position relative to the midline (only 1,506 of 5,013 neurons have it from annotations)
- [ ] Review the 12,782 links skipped for lacking a presynaptic partner
- [ ] Look at the 450 neurons whose anchor point is outside every mesh
- [ ] Decide whether mirror twin coverage (1,198 neurons) needs more sources
- [ ] Reconcile the orphan share with the 25% figure in Winding et al. 2023
- [ ] Curated neurotransmitter table from the literature
- [ ] Curated neuropil innervation table from the papers

### Phase 2: core data changes

- [ ] Replace the FlyWire schema in `codex/data/catalog.py` with the L1 schema, including the skeleton, paper and annotation files
- [ ] Replace the FAFB region list, categories and colors in `brain_regions.py` with the 27 L1 regions
- [ ] Accept `UNKNOWN` neurotransmitters in the initializer and lookups, and check the cell page text
- [ ] Remove the voxel conversion and use nanometre positions
- [ ] Update `neuron_data_initializer.py` to read the new files, drop supervoxel ids and mark aggregates
- [ ] Point the loader at the hosted files and set an L1 release label in `versions.py`
- [ ] Decide how names with quotes, whitespace and commas are stored (`make_web_safe` rewrites quotes, and list columns split on commas)

### Phase 3: filtering

- [ ] Attributes for node count, soma, papers, annotations, aggregate flag and orphan shares
- [ ] Numeric operators (`>=`, `<=`) in the structured search
- [ ] Advanced search controls for the new attributes
- [ ] Global neuron-set filter with the Winding 2023 default and per-request aggregates
- [ ] Skip aggregates in pathway search, motif search and reciprocal counts
- [ ] Show the orphan share as a completeness indicator, with a note that degree counts understate connectivity

### Phase 4: viewer links

- [ ] CATMAID URL builders replacing `codex/utils/nglui.py`, after confirming the URL parameters for several skeletons
- [ ] Hide skeleton thumbnails and neuropil mesh views

### Phase 5: tests and CI

- [ ] Synthetic L1-style fixture under `tests/`
- [ ] Rewrite the tests that depend on FlyWire ids and counts (`test_graph_algos.py` alone hard-codes 54 ids)
- [ ] Mocked-pymaid test of the export script
- [ ] Change the CI data step to use the fixture

### Deferred

- [ ] Page text, About and FAQ pages, branding
- [ ] NBLAST similarity computed offline with navis
- [ ] Rendered skeleton thumbnails

## Open questions

- Where the exported files are hosted.
- Whether features that start empty (similar cells, connectivity tags, community labels) are hidden or left visible.
- How to name and describe the orphan aggregates in the interface.

## Working notes

- Setup for the exporter: `poetry install --with export`.
- Trial export: `poetry run python scripts/export_l1.py --limit 50 --out-dir <dir> --cache-dir <dir>`.
- Full export: the same command without `--limit`. It took roughly 15 to 20 minutes and resumes from the cache directory if interrupted.
- Unit tests: `python3 -m pytest tests/unit/test_l1_export.py`.
- The exporter has been run end to end only against the public server, with the throttle at its defaults.
