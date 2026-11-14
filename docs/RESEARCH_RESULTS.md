# Initial Public Reference Experiment Results

**Execution date:** 14 November 2026  
**Repository PR head:** `0126015caf228322a073b89478b8bb2d8876891a`  
**Workflow:** [Research Evaluation run #43544920142](https://github.com/emtharva1047/DataSentry/actions/runs/43544920142)  
**Full JSON artifact:** [uci-wine-reference-experiment](https://github.com/emtharva1047/DataSentry/actions/runs/43544920142/artifacts/14093572094)  
**Artifact SHA-256:** `aaf3cafca990ffe109b9abb6e43aa3c9a6bfe109f8062b7cc2ec5d6eab49dcda`  
**Artifact expiry:** 14 December 2026

This is the first measured reference run, not a final general-purpose benchmark. All values below come from the uploaded JSON artifact. Each reported mean and standard deviation uses three seeds (42, 123, 2026); standard deviation is the sample standard deviation (ddof=1).

## Dataset and provenance

- **Dataset:** Wine Recognition, UCI Machine Learning Repository dataset 109.
- **Source:** [UCI dataset record](https://archive.ics.uci.edu/dataset/109/wine); [scikit-learn loader documentation](https://scikit-learn.org/stable/modules/generated/sklearn.datasets.load_wine.html).
- **Loader:** `sklearn.datasets.load_wine(as_frame=True)`; the bundled copy is used, so the experiment does not fetch data at runtime.
- **Original data:** 178 rows, 13 numeric features, three classes (59, 71, 48).
- **Derived feature:** `alcohol_band`, created from `alcohol` using fixed cut points 12.0 and 13.0 with labels low/medium/high. This is not an original UCI feature; it was added only to make categorical inconsistency measurable.
- **Detector frame:** the 13 original numeric features plus `alcohol_band`; the target is excluded.
- **Clean-reference preflight:** zero missing cells, zero exact duplicate rows, zero detected categorical inconsistency cells, and zero invalid numeric cells.
- **Canonical full-frame SHA-256:** `83f6c9765be98acbdfe6003d45049c96bfed86057f279b75280618491706758d`.
- **Detector-frame SHA-256 (target excluded):** `44f38eddfcac4516356d48300c9b05a1f37b24605c2cb20b9a1f7b047a10eca6`.
- **Versions:** Python 3.12, pandas 2.3.3, NumPy 2.5.4, scikit-learn 1.9.1.

The UCI dataset is licensed CC BY 4.0. Attribution: Aeberhard, S. & Forina, M. (1992), *Wine*, UCI Machine Learning Repository, DOI [10.24432/C5PC7J](https://doi.org/10.24432/C5PC7J).

## Detector benchmark protocol

- Corruption rates: 1%, 5%, 10%.
- Seeds: 42, 123, 2026.
- Isolation Forest: 100 estimators, contamination 0.05.
- IQR multiplier: 1.5.
- Modified robust Z threshold: 3.5.
- Five defect categories; seven applicable detector/rate combinations per rate (the numerical-anomaly defect is evaluated by IQR, robust Z, and Isolation Forest).
- **21 detector/rate experiments completed; 63 detector-seed runs; no skipped runs.**
- Missingness, categorical inconsistency, and invalid values are scored at cell level. Duplicates and numerical anomalies are scored at row level.
- Corruption generation and metric calculation are excluded from detector runtime. The measured interval includes full detector execution, including Isolation Forest fit/predict. Numerical detector eligibility is preflighted outside the timed interval, then the detector is rerun inside the measurement.
- Memory is Python `tracemalloc` peak allocation delta; native NumPy/scikit-learn allocations may be undercounted.

### Exact rule detectors

| Defect | Detector | Rate | Precision | Recall | F1 mean ± sample SD | Runtime (ms) | Python peak bytes |
|---|---|---:|---:|---:|---:|---:|---:|
| Missingness | Missingness rule | 1% | 1.000 | 1.000 | 1.000 ± 0.000 | 0.168 | 8,196 |
| Missingness | Missingness rule | 5% | 1.000 | 1.000 | 1.000 ± 0.000 | 0.157 | 8,196 |
| Missingness | Missingness rule | 10% | 1.000 | 1.000 | 1.000 ± 0.000 | 0.163 | 8,196 |
| Duplicates | Exact duplicate rule | 1% | 1.000 | 1.000 | 1.000 ± 0.000 | 1.872 | 50,691 |
| Duplicates | Exact duplicate rule | 5% | 1.000 | 1.000 | 1.000 ± 0.000 | 1.856 | 51,620 |
| Duplicates | Exact duplicate rule | 10% | 1.000 | 1.000 | 1.000 ± 0.000 | 1.847 | 52,955 |
| Invalid values | Numeric parseability rule | 1% | 1.000 | 1.000 | 1.000 ± 0.000 | 6.954 | 26,034 |
| Invalid values | Numeric parseability rule | 5% | 1.000 | 1.000 | 1.000 ± 0.000 | 8.048 | 26,034 |
| Invalid values | Numeric parseability rule | 10% | 1.000 | 1.000 | 1.000 ± 0.000 | 9.366 | 26,034 |

These perfect scores are expected for controlled defects whose injected labels match the corresponding deterministic rule definition. They are not evidence of perfect performance on arbitrary real-world defects.

### Categorical and numerical detectors

| Defect | Detector | Rate | Precision | Recall | F1 mean ± sample SD | Runtime (ms) | Python peak bytes |
|---|---|---:|---:|---:|---:|---:|---:|
| Categorical inconsistency | Categorical consistency rule | 1% | 0.017 | 1.000 | 0.034 ± 0.009 | 0.362 | 9,507 |
| Categorical inconsistency | Categorical consistency rule | 5% | 0.051 | 1.000 | 0.096 ± 0.000 | 0.406 | 9,613 |
| Categorical inconsistency | Categorical consistency rule | 10% | 0.101 | 1.000 | 0.184 ± 0.000 | 0.401 | 9,637 |
| Numerical anomalies | IQR | 1% | 0.633 | 1.000 | 0.775 ± 0.015 | 3.842 | 21,948 |
| Numerical anomalies | IQR | 5% | 0.944 | 1.000 | 0.971 ± 0.006 | 5.284 | 41,807 |
| Numerical anomalies | IQR | 10% | 0.990 | 1.000 | 0.995 ± 0.004 | 7.197 | 68,623 |
| Numerical anomalies | Robust Z-score | 1% | 0.639 | 1.000 | 0.780 ± 0.013 | 2.945 | 22,503 |
| Numerical anomalies | Robust Z-score | 5% | 0.955 | 1.000 | 0.977 ± 0.005 | 4.286 | 39,316 |
| Numerical anomalies | Robust Z-score | 10% | 0.988 | 1.000 | 0.994 ± 0.002 | 6.058 | 65,656 |
| Numerical anomalies | Isolation Forest | 1% | 0.963 | 0.377 | 0.542 ± 0.036 | 739.097 | 471,170 |
| Numerical anomalies | Isolation Forest | 5% | 1.000 | 0.106 | 0.192 ± 0.003 | 742.161 | 517,135 |
| Numerical anomalies | Isolation Forest | 10% | 1.000 | 0.067 | 0.126 ± 0.005 | 741.196 | 559,106 |

### Detector interpretation

1. **Categorical rule over-flagging:** recall is 1.0, but precision is very low. The current rule flags all members of a casefold-equivalent category group when a variant exists, not only the injected variant cells. This is a concrete false-positive problem to address.
2. **IQR and robust Z:** both achieve recall 1.0 on these deliberately extreme injected values; precision rises as the injection rate increases. This is an easy synthetic anomaly setting and does not establish performance on subtle or naturally occurring anomalies.
3. **Isolation Forest:** precision remains high while recall falls from 0.377 to 0.067. The detector uses fixed contamination 0.05, while the row-level prevalence of injected anomalies rises with the cell corruption rate. Contamination calibration and row-prevalence reporting need further study.
4. **Runtime:** Isolation Forest takes approximately 0.74 seconds on this small frame, compared with milliseconds for IQR and robust Z. The memory column is only a Python allocation proxy, not total process RSS.

## Downstream classification experiment

The clean reference is split first using stratified 75/25 holdouts for seeds 42, 123, and 2026 (133 training rows and 45 test rows per seed). Only the derived `alcohol_band` feature is used, deliberately excluding its source `alcohol` column and other predictors so the classifier cannot bypass the corrupted categorical representation.

For each seed and each corruption rate, the same untouched test partition is used for:

- clean training;
- training-only categorical case/whitespace corruption;
- training-only corruption followed by DataSentry's production trim-whitespace and lowercase operations.

All preprocessing is fitted within a separate pipeline on the corresponding training partition only. The target and test partition are never corrupted or cleaned. The clean test fingerprints are retained in the artifact.

| Training corruption rate | Clean macro F1 | Corrupted macro F1 | Cleaned-corrupted macro F1 | Paired cleaned − corrupted macro F1 |
|---|---:|---:|---:|---:|
| 5% | 0.524946 ± 0.024922 | 0.524946 ± 0.024922 | 0.524946 ± 0.024922 | 0.000000 ± 0.000000 |
| 10% | 0.524946 ± 0.024922 | 0.524946 ± 0.024922 | 0.524946 ± 0.024922 | 0.000000 ± 0.000000 |
| 20% | 0.524946 ± 0.024922 | 0.524946 ± 0.024922 | 0.524946 ± 0.024922 | 0.000000 ± 0.000000 |

Accuracy is 0.681481 ± 0.033945 and balanced accuracy is 0.622222 ± 0.030316 in all three conditions and at all three rates. The cleaned-corrupted metrics exactly match the clean condition, as expected because the production operations reverse the injected case/whitespace changes. The corrupted condition also has no measured metric change at these rates.

**Interpretation:** this is a null result for a small one-feature ablation and this logistic-regression baseline. It shows no measurable downstream sensitivity to this particular corruption on this dataset; it does not show that categorical inconsistency is harmless generally, nor that cleaning improves model performance. A larger mixed-type dataset and additional feature sets are needed.

## Limitations and next experiments

- One small, well-behaved public dataset; results are dataset-specific.
- One derived categorical feature is used to exercise categorical detection; it is not an original UCI attribute.
- Exact rule detectors are evaluated against synthetic labels generated from closely matching definitions, so their perfect scores are optimistic.
- Numerical anomalies are deliberately extreme; subtler anomaly distributions are not tested.
- Downstream evaluation covers classification and categorical inconsistency only. Regression, missingness, invalid-value, duplicate, and numerical-anomaly training-only comparisons remain outstanding.
- The categorical consistency rule needs more precise cell-level evidence to reduce false positives.
- Isolation Forest contamination should be varied or calibrated against row-level anomaly prevalence.
- Python `tracemalloc` does not capture all native memory allocations.

The next research increment should use a larger mixed-type public dataset, add downstream regression and other training-only corruption conditions, and compare multiple feature sets before drawing broader conclusions.
