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
- Visualization stays in neuroglancer, as in the FlyWire version, with sources for the L1 volume in place of the FlyWire ones. CATMAID is not used as a viewer. Thumbnails and mesh views are hidden until they can be rendered offline.
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
- [ ] Export skeletons in a neuroglancer-readable format (needs the node data that the current export discards after summarizing)
- [ ] Curated neurotransmitter table from the literature
- [ ] Curated neuropil innervation table from the papers

### Phase 2: core data changes

- [x] Replace the FlyWire schema in `codex/data/catalog.py` with the L1 schema (`L1_EXPORT_SCHEMA` now derives from it)
- [x] Replace the FAFB region list, categories and colors in `brain_regions.py` with the 27 L1 regions (`REGIONS` derives from `L1_REGIONS`, segment ids are the CATMAID volume ids)
- [x] Accept `UNKNOWN` neurotransmitters in the initializer, connection encoding, `NeuronDB.connections` and the search filter, and hide the prediction line on the cell page
- [x] Remove the voxel conversion and use nanometre positions
- [x] Update `neuron_data_initializer.py` to read the new files, drop supervoxel ids and mark aggregates
- [x] Point the loader at the raw files (data folder, then `CODEX_DATA_URL`, then the bundled `data/l1_export`), build a missing pickle from them, and set the release label `l1-2026-09`
- [x] Names: `group` and `skeleton_name` are kept verbatim apart from whitespace trimming, and cell types, papers and raw annotations are kept exactly as exported

### Phase 3: filtering

- [ ] Attributes for node count, soma, papers, annotations, aggregate flag and orphan shares
- [ ] Numeric operators (`>=`, `<=`) in the structured search
- [ ] Advanced search controls for the new attributes
- [ ] Global neuron-set filter with the Winding 2023 default and per-request aggregates
- [ ] Skip aggregates in pathway search, motif search and reciprocal counts
- [ ] Show the orphan share as a completeness indicator, with a note that degree counts understate connectivity
- [x] Free-text search matches words, word prefixes and substrings of skeleton names, cell types and paper names (`v'ada`, `MBON` and `Eichler` now find their cells), and a number that is a cell id finds that cell only
- [ ] Make the raw annotations searchable through a structured attribute (they are deliberately left out of free-text search: 358,000 rows, many of them working notes)
- [ ] Keep the aggregate nodes out of search results by default (a search for `A3_L` currently lists them first)
- [ ] Audit every place where names, cell types and annotations are put into HTML strings or inline JavaScript, and escape them (they contain quotes, `&`, `<` and `>`, and the loader no longer replaces quotes)
- [ ] Add the `group` attribute to the heatmap and network group-by lists, since flow, class and sub-class are empty
- [x] Hide the FlyWire community features: the leaderboard and labeling-log routes are no longer served, and the community labels column and modal, the `label` search attribute, the label sort options, the label statistics, the CSV label column and the labeling wording are gone (`tests/unit/test_community_features_hidden.py`)
- [ ] Remove the code the hidden features left behind: the label methods of `NeuronDB`, the `label` and `marker` attributes, the `is_oss`-guarded annotation form and the label-cleaning module
- [ ] Decide what to do with the motif search and statistics code that lists only the six known transmitters

### Phase 4: neuroglancer viewer

- [x] Find where the L1 EM image can be read by neuroglancer. The stack info (metadata only) lists five mirrors of 512 x 512 JPEG tiles in CATMAID's tile format (source type 4): Virtual Fly Brain, two at the MRC LMB, Janelia and Magdeburg. The listing of neuroglancer's data sources and its README show no CATMAID source (precomputed, N5, Zarr, Boss, DVID, Render, NIfTI and Deep Zoom only), so none of these mirrors can be added as an image layer. The volume is 28,128 x 31,840 x 4,841 voxels at 3.8 x 3.8 x 50 nm (about 4.3 TB uncompressed), with the z origin offset by 6,050 nm and 90 broken slices
- [ ] Decide the EM image question: no image layer at first (3D view of skeletons and meshes only), a converted copy hosted by us (about 4.3 TB uncompressed, which also conflicts with the no-download rule), or an existing public precomputed copy if one is known
- [ ] Export the skeletons in neuroglancer's precomputed skeleton format (simplified to keep the size manageable) and the CNS and segment volumes as meshes, and choose a static host that sends CORS headers
- [ ] Choose the neuroglancer deployment that the links point to (FlyWire's version posted large states to its own state server, which L1 does not have, so states must stay small by referencing hosted sources)
- [ ] Decide how skeletons reach neuroglancer: precomputed skeletons written offline (for example with navis) and hosted with the data, or inline line annotations as a fallback for small selections
- [ ] Decide whether the segment volumes are also shown as meshes
- [ ] Rewrite the URL builders in `codex/utils/nglui.py` for L1 (nanometre positions, 3.8 x 3.8 x 50 nm voxels) and replace the FlyWire links on cell pages
- [ ] Hide skeleton thumbnails and neuropil mesh views

### Phase 5: tests and CI

- [ ] Synthetic L1-style fixture under `tests/`
- [ ] Rewrite the 34 unit tests that still assert FlyWire facts: `test_neuron_data.py` (26), `test_heatmaps.py` (2), `test_graph_algos.py` (2), `test_motif_search.py` (2), `test_connectivity.py`, `test_stats_utils.py` and `test_structured_search_filters.py` (1 each). `test_graph_algos.py` alone hard-codes 54 ids, and `test_annotations_web_safe` contradicts the verbatim-names decision
- [ ] Mocked-pymaid test of the export script
- [x] CI data step: `python -m codex.data.local_data_loader` now builds the database from the bundled export without any download

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
- Unit tests for the L1 work: `python3 -m pytest tests/unit/test_l1_export.py tests/unit/test_local_data_loader.py tests/unit/test_neuron_data_initializer.py tests/unit/test_brain_regions.py tests/unit/test_catalog.py`. The full suite is at 156 passing and 34 failing, all of the failures being FlyWire-specific assertions (Phase 5).
- The first start builds `static/data/l1-2026-09/neuron_db.pickle.gz` from the bundled export in about 5 seconds. Delete the pickle after any schema change.
- Packages needed to run the whole suite locally: Flask and user-agents. `nglui` did not build in the cloud environment, so `tests/app_client.py` stubs it when the real package cannot be imported. The client also serves as a smoke test of the pages against the L1 data.
- The pathways page takes `source_cell_id` and `target_cell_id`, and returns an error without them.
- The exporter has been run end to end only against the public server, with the throttle at its defaults.
