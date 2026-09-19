# MovieMuse Bench

The evaluation registry for MM-046 loads the existing task configurations at
`fixtures/bench/tasks.yaml` through `movie_muse.testkit.api.BenchRegistry`.

Families stay separate:

- objective ground truth
- blinded human preference
- observed workflow utility

Do not collapse families into one MovieMuseScore. Synthetic audience text is a
hypothesis, not a human or bootstrap population sample.

Local and fine-tuned routes (`local_stub`, `finetune_script_adapter` /
`ft-script-v1`) must meet the declared quality and safety baselines before an
evaluation run is stored.
