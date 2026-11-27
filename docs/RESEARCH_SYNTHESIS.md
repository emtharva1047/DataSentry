# DataSentry Research Synthesis

**Synthesis date:** 27 November 2026  
**Repository baseline:** `main` at `13f284e43c700fe6981fc1de337d20033f5e557d`  
**Detailed measured results:** [RESEARCH_RESULTS.md](RESEARCH_RESULTS.md)  
**Protocol:** [RESEARCH_PLAN.md](RESEARCH_PLAN.md)

## Executive summary

The prototype has a reproducible research record spanning five seeded synthetic defect families, defect-specific detector evaluation, downstream classification and regression, and clean-baseline rolling-origin evaluation. Matching deterministic rules and univariate detectors on deliberately extreme values performed well in these controlled settings. Isolation Forest was materially more sensitive to its contamination threshold and to the row-level anomaly prevalence induced by cell-level corruption.

The downstream experiments do **not** support a general claim that cleaning improves model quality. Duplicate removal and case normalization restored the clean training representation in their controlled conditions; invalid-value cleaning matched the model pipeline's training-fitted median imputation; missing-value cleaning had mixed results; and IQR clipping improved the corrupted condition but did not recover the clean baseline and also clipped non-injected observations.

These are controlled, reference-specific experiments—not estimates of real-world defect prevalence, universal detector accuracy, or guaranteed production cleaning benefit.

## Evidence inventory

Counts below describe separate experiments and must not be added into one total: some workflows rerun earlier conditions as controls, and quality-version-2 categorical results supersede historical quality-version-1 categorical results.

| Evidence slice | Reference / design | Completed coverage |
|---|---|---|
| Initial detector benchmark | UCI Wine, 178 rows | 21 detector/rate combinations; 63 detector-seed runs |
| Mixed-type detector benchmark | UCI Bike Sharing, 17,379 rows | 21 detector/rate combinations; 63 detector-seed runs |
| Quality-v2 combined categorical re-benchmark | Wine and Bike Sharing | 18 reference/rate/seed runs; no skips |
| Pure case-only categorical benchmark | Wine and Bike Sharing | 18 reference/rate/seed runs; no skips |
| Isolation Forest sensitivity | Bike Sharing; contamination 0.01/0.05/0.10 | 27 IF seed runs plus 54 IQR/robust-Z control runs |
| Downstream classification | Wine; 5%, 10%, 20% training corruption | Three seeds and clean/corrupted/cleaned conditions |
| Downstream regression | Bike Sharing; five defect families, 1%/5%/10% | 45 rate/seed trials and 135 Ridge fits |
| Clean-baseline stability | Bike Sharing; expanding 70%/80%/90% training prefixes | Three non-overlapping future windows |

The two public references are UCI Wine Recognition (178 rows, 13 original numeric features plus one derived categorical feature for category-rule evaluation) and UCI Bike Sharing hourly (17,379 rows, eight semantically mapped categorical predictors and five numeric predictors). The Bike Sharing target `cnt` is not a feature; direct target components `casual` and `registered` are excluded from regression predictors.

## Detector findings

### Exact and categorical rules

| Defect / detector | Measured controlled-reference result | Interpretation |
|---|---|---|
| Missingness rule | Precision = recall = F1 = 1.0 on both references at tested rates | Expected when injected missing cells are scored by the matching rule |
| Exact duplicate rule | Precision = recall = F1 = 1.0 on both references at tested rates | Expected for exact inserted copies and an exact duplicate detector |
| Numeric parseability rule | Precision = recall = F1 = 1.0 on both references at tested rates | Expected for deliberately non-numeric sentinels in declared numeric-like columns |
| Categorical consistency, quality v2 | Precision = recall = F1 = 1.0 for combined whitespace-plus-case and isolated case-only generators on both references at 1%, 5%, and 10% | Controlled support for the modal-spelling heuristic, not universal category-drift detection |

The categorical quality-v2 rule always flags surrounding whitespace. For casefold-equivalent values, it flags only non-dominant spellings when there is a unique most-frequent trimmed spelling; tied groups remain ambiguous. The benchmark calls the same production helper to avoid detector/benchmark drift. The pure case-only generator changes letter case without adding whitespace.

Perfect rule scores are optimistic because generator and detector definitions are closely aligned. A legitimate minority spelling can still be flagged, tied groups are unresolved, and a wrong spelling that becomes dominant can evade the heuristic. Explicit schema/domain contracts remain preferable when business semantics are known.

### Numerical anomaly detectors

F1 mean ± sample SD (ddof=1) across seeds 42, 123, and 2026:

| Reference / detector | 1% cell corruption | 5% cell corruption | 10% cell corruption |
|---|---:|---:|---:|
| Wine — IQR | 0.775 ± 0.015 | 0.971 ± 0.006 | 0.995 ± 0.004 |
| Wine — modified robust Z | 0.780 ± 0.013 | 0.977 ± 0.005 | 0.994 ± 0.002 |
| Wine — Isolation Forest, contamination 0.05 | 0.542 ± 0.036 | 0.192 ± 0.003 | 0.126 ± 0.005 |
| Bike Sharing — IQR | 0.932601 ± 0.000745 | 0.989284 ± 0.000531 | 0.997517 ± 0.000045 |
| Bike Sharing — modified robust Z | 0.991432 ± 0.000371 | 0.998389 ± 0.000145 | 0.999390 ± 0.000107 |
| Bike Sharing — Isolation Forest, contamination 0.05 | 0.988159 ± 0.002227 | 0.362621 ± 0.002259 | 0.218159 ± 0.000385 |

IQR and modified robust-Z achieved recall 1.0 in the deliberately high-extreme-value benchmark; precision rose with injection rate. This does not test subtle or naturally occurring multivariate anomalies.

The Bike Sharing sensitivity sweep shows why configured **cell** corruption rate cannot be treated as Isolation Forest **row** contamination rate. Measured affected-row prevalence was 4.8833%, 22.5789%, and 40.8405% at 1%, 5%, and 10% cell corruption across five numeric columns. Among the three tested settings, contamination 0.05 gave F1 0.988159 at 1%; contamination 0.10 gave the best tested F1 at 5% (0.613847, recall 0.442847) and 10% (0.393406, recall 0.244870). No universal or automatic contamination choice is justified.

Runtime observations place tested Isolation Forest runs at roughly 0.74–0.91 seconds, while rule and univariate statistical detectors were generally faster. Memory figures use Python `tracemalloc` peak-allocation deltas; they are not process RSS and omit some native NumPy/scikit-learn allocations. Cross-reference runtime is not a controlled dataset-size scaling experiment.

## Downstream model findings

### UCI Wine classification

The one-feature `alcohol_band` ablation produced macro-F1 **0.524946 ± 0.024922** for clean, corrupted, and production-cleaned training at each tested rate (5%, 10%, 20%). Accuracy and balanced accuracy were also unchanged. This is a null result for one small derived-feature experiment; it does not show that categorical inconsistency is harmless in general.

### UCI Bike Sharing regression

The five-family runner evaluates missingness, exact duplicate rows, invalid numeric tokens, numerical anomalies, and pure case-only categorical inconsistency at 1%, 5%, and 10% over seeds 42, 123, and 2026. The chronological split uses 13,034 training rows and 4,345 future test rows. Corruption is training-only; preprocessing is fitted on training data; the future test partition is fingerprinted and left untouched.

| Training defect | Production cleaning result | Evidence-based interpretation |
|---|---|---|
| Missingness | Median/mode cleaning was worse than the corrupted pipeline at 1% and 5% on the reported holdout; at 10%, MAE improved slightly while RMSE and R² worsened | No consistent downstream benefit from the production imputation policy |
| Exact duplicates | Removing injected complete feature/target duplicates restored original training pairs and reproduced clean-baseline metrics exactly | Validates this inserted-copy condition; repeated events are not universally invalid |
| Invalid numeric tokens | Production numeric-median cleaning and the model pipeline's training-fitted coercion/imputation produced identical metrics | Preprocessing parity, not improvement over the corrupted pipeline |
| Numerical anomalies | IQR clipping improved MAE, RMSE, and R² relative to corrupted training at all three rates, but did not restore clean-baseline metrics | Conditional gain for this extreme-value mechanism; the cleaner clipped 48–87 additional non-injected training cells per seed |
| Pure case-only categorical inconsistency | Production lowercase cleaning restored the clean baseline exactly; corrupted-condition shifts were small and not consistently directional | Validates the fixed transform for documented case-insensitive semantic labels, not arbitrary categorical domains |

For numerical anomalies, paired cleaned-minus-corrupted mean changes were:

| Rate | ΔMAE | ΔRMSE | ΔR² |
|---:|---:|---:|---:|
| 1% | -3.823573 | -2.375620 | +0.013432 |
| 5% | -2.421385 | -1.559145 | +0.008845 |
| 10% | -1.587886 | -1.047642 | +0.005955 |

Negative MAE/RMSE and positive R² indicate improvement relative to corrupted training. The clean baseline remained better than the clipped condition. Extra cells outside the fitted IQR fences were not injected defects and may be legitimate extremes; this supports keeping IQR clipping high-risk, previewed, and explicitly applied rather than automatic.

The three corruption seeds vary injection locations on the same chronological holdout. They are not independent datasets or independent temporal test splits. Per-seed metrics and paired deltas remain in the detailed results and workflow artifacts.

### Clean-baseline temporal-window dispersion

An expanding-window experiment evaluates all 5,214 rows in the final 30% of the Bike Sharing chronology exactly once, using three non-overlapping 1,738-row future windows. Preprocessing is fitted independently on each training prefix.

| Metric | Mean across windows | Sample SD across windows |
|---|---:|---:|
| MAE ↓ | 102.337591 | 14.717943 |
| RMSE ↓ | 134.584052 | 16.832018 |
| R² ↑ | 0.610930 | 0.007623 |

This is **temporal-window dispersion**, not random-seed uncertainty and not a confidence interval. Training prefixes expand and overlap by design; future test windows do not overlap. The final window was easier on MAE/RMSE than the two preceding windows, indicating temporal heterogeneity for this reference and fixed Ridge configuration.

## Cross-study conclusions

1. The prototype detects its declared synthetic defects reproducibly, but the construction is deliberately aligned with several detectors.
2. Univariate numerical detectors were effective on deliberately extreme values; this does not generalize to subtle or domain-valid extremes.
3. Isolation Forest threshold choice matters because cell corruption and row anomaly prevalence differ.
4. Cleaning is not uniformly beneficial: effects range from exact restoration and pipeline parity to mixed/no improvement and a conditional gain below the clean baseline.
5. Outlier status is not invalidity. IQR clipping affected additional non-injected cells, so anomaly flags and cleaning require human review.
6. Temporal variation is visible; a single fixed holdout would not expose the observed dispersion across future windows.

## Threats to validity and explicit scope cuts

- **Reference coverage:** only two public references were used. Wine has 178 rows; Bike Sharing has 17,379. Neither establishes performance across arbitrary business schemas.
- **Synthetic realism:** injected defects are controlled and often obvious. Results do not estimate real-world prevalence or performance on naturally occurring, ambiguous, adversarial, or correlated defects.
- **Detector-definition coupling:** exact-rule and categorical scores are partly expected because generator and detector share defect semantics. No independent external annotation study was performed.
- **Model coverage:** downstream classification uses one derived categorical feature and one baseline. Downstream regression uses one fixed Ridge alpha and one primary chronological 75/25 holdout. There is no hyperparameter search or broad model comparison.
- **Seed interpretation:** seeds vary synthetic corruption locations. They do not create independent source datasets or independent test periods. Rolling-origin SD is across only three temporal windows and is descriptive.
- **Research question 2 (hybrid versus individual):** individual detectors and weighted DQS are implemented, but there is no controlled ablation comparing a fully specified hybrid detector against each individual method. This question remains open.
- **Research question 4 (dataset size versus runtime):** the two references differ in size and schema, but this is not a controlled scaling study. Dataset size, feature count, type mix, and detector work differ together; no causal size/runtime relationship is claimed.
- **Memory:** `tracemalloc` is a Python allocation proxy, not total resident memory.
- **UI scope:** interactive schema-contract authoring remains deferred; explicit schema/domain validation is available through the API. Cloud-scale processing, role-based access, non-CSV formats, and advanced PDF export remain out of scope.

## Reproducibility and provenance

Implementation entry points:

- Synthetic corruption and exact labels: `backend/app/services/dataset_research.py`.
- Defect-specific detector benchmark: `backend/app/services/dataset_benchmark.py`.
- Detector CLI: `backend/scripts/run_detector_benchmark.py`.
- UCI Wine detector/classification runner: `backend/scripts/run_public_reference_experiments.py`.
- Bike Sharing downstream regression runner: `backend/scripts/run_bike_sharing_regression_experiment.py`.
- Bike Sharing clean-baseline stability runner: `backend/scripts/run_bike_sharing_baseline_stability.py`.
- Isolated application demo: `backend/scripts/run_end_to_end_demo.py`.

Documented workflows include [UCI Wine research evaluation](https://github.com/emtharva1047/DataSentry/actions/runs/43544920142), [Bike Sharing detector benchmark](https://github.com/emtharva1047/DataSentry/actions/runs/44221377880), [Isolation Forest sensitivity](https://github.com/emtharva1047/DataSentry/actions/runs/44442153834), [pure case-only categorical benchmark](https://github.com/emtharva1047/DataSentry/actions/runs/44658968650), [Bike Sharing case-only downstream regression](https://github.com/emtharva1047/DataSentry/actions/runs/45310571907), and [rolling-origin baseline stability](https://github.com/emtharva1047/DataSentry/actions/runs/45531043258). Exact artifact IDs, hashes, software versions, per-seed metrics, confusion counts, and retention notes remain in [RESEARCH_RESULTS.md](RESEARCH_RESULTS.md); workflow artifacts are temporary and are not committed as datasets.

The UCI Bike Sharing source archive SHA-256 is `b70182d0d0508e9abbb79306ce5c0cec34869000f8220175ac83d11dbe845401`; `hour.csv` SHA-256 is `e03de4ee4ef4dc376ac6e04bf829673c6269e8eba5c60fa121640fa2f829504f`. The semantic regression-frame fingerprint is recorded in the detailed result file. Reported Bike Sharing workflow software is Python 3.12.16, pandas 2.3.3, NumPy 2.5.5, and scikit-learn 1.9.1. The Wine experiment uses the bundled scikit-learn dataset loader and records its frame hashes and package versions in the detailed result file.

## Completion decision

The planned detector comparisons, three-seed synthetic evaluation, five-family training-only downstream regression, Wine classification experiment, and clean-baseline temporal-window evaluation have been executed and documented. **M9's planned prototype experiments and consolidated interpretation are complete with the scope cuts above.** Research questions 2 and 4 are explicitly unresolved rather than presented as completed findings.

M10 remains open for the final known-limitations/deployment audit, clean-environment verification of the demo and installation instructions, final main-branch integration checks, and the delivery report. The project must not be described as a production-ready platform or a generally validated data-quality benchmark.
