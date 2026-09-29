# L1 larval EM export

Exported from the public L1 CATMAID project (project 1 on
`https://l1em.catmaid.virtualflybrain.org`) with `scripts/export_l1.py`. See `manifest.json`
for the export date and row counts. The schema is `L1_EXPORT_SCHEMA` in
`codex/data/l1_export.py`.

- 5,013 skeletons, all kept. Filter by node count, soma, paper or annotation downstream.
- Cell types are the `MB nomenclature` annotations, verbatim. Publications are the
  sub-annotations of `papers`. `annotations.csv.gz` holds every raw annotation, numeric ones included.
- Neurotransmitter is `UNKNOWN` for every neuron, pending a literature search.
- Regions are the CATMAID segment volumes (brain hemispheres, SEZ, T1-T3, A1-A8), assigned
  by point-in-mesh lookup of each synapse. Points outside every mesh are `UNASGD`.
- Synaptic sites whose partner is a single-node placeholder skeleton (not part of the 5,013)
  are collapsed into 54 aggregate nodes with ids from 900,000,000, named
  `orphaned synaptic sites (presynaptic|postsynaptic), <region>` and flagged
  `is_aggregate` in `skeletons.csv.gz`. Per-neuron counts of synapses to such sites are in
  `orphan_output_synapses` and `orphan_input_synapses`.
- `syn_count` counts (connector, postsynaptic site) links.
- Mirror twins come from `hemilateral_pair_*` and `paired with #*` annotations and cover a
  minority of neurons. `side` comes from left/right annotations and is empty for most.
