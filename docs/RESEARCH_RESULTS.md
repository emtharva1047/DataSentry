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
- The Wine-specific downstream evaluation covers classification and categorical inconsistency only. UCI Bike Sharing downstream regression under training-only missingness is reported separately below; regression experiments for invalid values, duplicates, categorical inconsistency, and numerical anomalies remain outstanding.
- The categorical consistency rule needs more precise cell-level evidence to reduce false positives.
- Isolation Forest contamination should be varied or calibrated against row-level anomaly prevalence.
- Python `tracemalloc` does not capture all native memory allocations.

The next research increment should use a larger mixed-type public dataset, add downstream regression and other training-only corruption conditions, and compare multiple feature sets before drawing broader conclusions.


## UCI Bike Sharing downstream regression experiment

**Execution date:** 17 November 2026. The public-reference workflow completed successfully; the artifact was downloaded and its JSON payload inspected before recording the results below.

- Dataset: UCI Bike Sharing hourly, dataset 275, DOI 10.24432/C5W894, CC BY 4.0.
- Target: cnt; casual and registered excluded because they sum directly to cnt.
- Features: eight semantic categorical fields, four original continuous fields, and derived day_index.
- Split: chronological 75/25 holdout; final 25% is an untouched future test partition.
- Corruption: training-feature missingness at 1%, 5%, and 10%; target and test rows remain unchanged.
- Conditions: clean training, corrupted training, and production median/mode-cleaned training.
- Model: Ridge regression, alpha 1.0; preprocessing fitted separately on each training condition only.
- Seeds: 42, 123, and 2026 vary corruption selection while retaining the same temporal split.
- Metrics: MAE, RMSE, R², fit runtime, paired cleaned-minus-corrupted deltas, mean, and sample standard deviation (ddof=1).
- Known limits: one chronological split, one baseline model, no rolling-origin validation, and one corruption family.


### Execution provenance

- **Workflow:** [Bike Sharing Regression Research run 44001202119](https://github.com/emtharva1047/DataSentry/actions/runs/44001202119).
- **Artifact:** [uci-bike-sharing-regression](https://github.com/emtharva1047/DataSentry/actions/runs/44001202119/artifacts/14291533864), retained for 30 days.
- **Artifact ZIP SHA-256:** `820a85eaf483620b77bdbd3a4ee6fe30e3a922b29cc1065250900d12ad5873b6`.
- **JSON payload SHA-256:** `79206a8c2312f8111805047e5469f9d879fa2edbe09df01fd8f43104b5e20525`.
- **Dataset:** 17,379 hourly rows, 1 January 2011 through 31 December 2012; 17 source columns; 13 model features plus target.
- **Features:** 8 semantic categorical features and 5 numeric features (four original continuous fields plus derived day_index).
- **Target:** cnt; casual and registered excluded as direct target components.
- **Source archive SHA-256:** `b70182d0d0508e9abbb79306ce5c0cec34869000f8220175ac83d11dbe845401`.
- **hour.csv SHA-256:** `e03de4ee4ef4dc376ac6e04bf829673c6269e8eba5c60fa121640fa2f829504f`.
- **Analysis-frame SHA-256:** `8ff14f833673fbad9c35ec3267c5c23335f98ba2b586e63bba67f98a755ee804`.
- **Software:** Python 3.12.16, pandas 2.3.3, NumPy 2.5.5, scikit-learn 1.9.1.
- **Split:** chronological 75/25; 13,034 training rows and 4,345 future test rows. All nine rate/seed runs used the same clean test fingerprint: `2f9613a31116dbdb6e0e272c123778ed3a45e62783393ead8df8c14cb7aef309`; every run recorded `test_partition_untouched=true`.
- **Runs:** seeds 42, 123, 2026; three rates; 27 total model fits across clean, corrupted, and cleaned-corrupted conditions. Each seed injected 1,695, 8,473, and 16,945 missing training cells at 1%, 5%, and 10%, respectively.

### Measured regression metrics

Values are mean ± sample standard deviation (ddof=1) across the three corruption seeds. The clean condition is identical across seeds because the chronological split and deterministic Ridge model are fixed.

| Missingness | Training condition | MAE ↓ | RMSE ↓ | R² ↑ |
|---:|---|---:|---:|---:|
| 1% | Clean | 100.722558 ± 0.000000 | 135.412598 ± 0.000000 | 0.621143 ± 0.000000 |
| 1% | Corrupted | 100.877907 ± 0.157496 | 135.394009 ± 0.027540 | 0.621248 ± 0.000154 |
| 1% | Cleaned-corrupted | 101.240666 ± 0.247452 | 136.231009 ± 1.069106 | 0.616535 ± 0.006030 |
| 5% | Clean | 100.722558 ± 0.000000 | 135.412598 ± 0.000000 | 0.621143 ± 0.000000 |
| 5% | Corrupted | 101.022371 ± 0.066836 | 134.996090 ± 0.103672 | 0.623470 ± 0.000578 |
| 5% | Cleaned-corrupted | 101.681875 ± 0.723305 | 135.849800 ± 0.523738 | 0.618689 ± 0.002937 |
| 10% | Clean | 100.722558 ± 0.000000 | 135.412598 ± 0.000000 | 0.621143 ± 0.000000 |
| 10% | Corrupted | 101.202511 ± 0.297523 | 134.579091 ± 0.112693 | 0.625793 ± 0.000626 |
| 10% | Cleaned-corrupted | 101.041455 ± 0.377982 | 134.776204 ± 0.234142 | 0.624695 ± 0.001303 |

### Paired production-cleaning effect

The following values are cleaned-corrupted minus corrupted on the same seed and test partition. Positive MAE/RMSE means the cleaned condition is worse; negative R² means the cleaned condition is worse.

| Missingness | ΔMAE | ΔRMSE | ΔR² |
|---:|---:|---:|---:|
| 1% | +0.362759 ± 0.231459 | +0.837001 ± 1.054259 | -0.004713 ± 0.005947 |
| 5% | +0.659504 ± 0.783233 | +0.853710 ± 0.616858 | -0.004781 ± 0.003456 |
| 10% | -0.161056 ± 0.206862 | +0.197114 ± 0.124674 | -0.001097 ± 0.000695 |

### Interpretation and limits

1. The production cleaning condition did not consistently improve the regression metrics. At 1% and 5%, all three aggregate metrics were worse than the corrupted-training condition. At 10%, MAE improved slightly, but RMSE and R² were worse.
2. The corrupted condition itself produced mixed metrics relative to clean training: MAE increased at each rate, while RMSE decreased and R² increased. This is not evidence that missingness improves the model; it shows that this single fixed future holdout and this feature/model combination do not exhibit a simple monotonic response.
3. The corrupted model's pipeline uses its training-fitted constant sentinel for missing categorical values; the cleaned-corrupted condition uses DataSentry's production mode imputation for categorical fields and median imputation for numeric fields. The comparison therefore evaluates those two explicit missing-value policies.
4. The three seeds vary training-cell selection only. They are not three independent temporal test periods. The clean baseline standard deviation of zero is a consequence of the fixed split and deterministic Ridge fit, not evidence of zero sampling uncertainty.
5. This is one chronological holdout, one fixed Ridge alpha, and one corruption family. It does not establish performance across seasons, other datasets, other regression models, or other defects. Rolling-origin validation and broader missingness mechanisms remain necessary.


## UCI Bike Sharing mixed-type detector benchmark — quality version 1 historical run

**Execution date:** 18 November 2026. This section records the original quality-version-1 categorical rule; its categorical precision rows are superseded by the quality-version-2 re-benchmark below. The final PR-head GitHub Actions workflow completed successfully; the job output and uploaded JSON artifact were inspected before recording these results.

- Dataset: UCI Bike Sharing hourly, dataset 275, DOI 10.24432/C5W894, CC BY 4.0.
- Detector reference: 17,379 rows and 13 predictors: eight semantic categorical fields and five numeric fields.
- Target exclusion: `cnt`, `casual`, and `registered` are not detector inputs. `instant` and `dteday` are not predictors.
- Category treatment: integer-coded source values are mapped to explicit season/year/month/hour/holiday/weekday/working-day/weather labels before corruption.
- Clean-reference preflight: zero missing cells, exact duplicate rows, categorical whitespace/case findings, and invalid numeric cells. Statistical outliers are retained and may count as false positives.
- Corruption rates: 1%, 5%, 10%; seeds: 42, 123, 2026.
- Parameters: Isolation Forest 100 estimators, contamination 0.05; IQR multiplier 1.5; modified robust-Z threshold 3.5.
- Coverage: five defect families and seven applicable detector adapters per rate (one each for missingness, duplicates, categorical inconsistency, invalid values; three for numerical anomalies), giving 21 detector/rate combinations and 63 detector-seed runs. No runs were skipped.
- Evaluation units: cell-level for missingness, categorical inconsistency, and invalid values; row-level for duplicate occurrences and numerical anomalies.
- Metrics: per-seed TP/FP/TN/FN, precision, recall, F1, accuracy, prediction runtime, and Python tracemalloc peak-allocation delta. Means and sample standard deviations (ddof=1) are retained for all completed three-seed experiments.
- Software: Python 3.12.16, pandas 2.3.3, NumPy 2.5.5, scikit-learn 1.9.1.

### Execution provenance

- **Workflow:** [Bike Sharing Detector Research run 44221377880](https://github.com/emtharva1047/DataSentry/actions/runs/44221377880).
- **Artifact:** [uci-bike-sharing-detector-benchmark](https://github.com/emtharva1047/DataSentry/actions/runs/44221377880/artifacts/14391430715), retained for 30 days.
- **Artifact ZIP SHA-256:** `921d1a3c4188cc0d4db1a13a8c043b4e5561cae58e4e704e3316e85e82211589`.
- **Source archive SHA-256:** `b70182d0d0508e9abbb79306ce5c0cec34869000f8220175ac83d11dbe845401`.
- **hour.csv SHA-256:** `e03de4ee4ef4dc376ac6e04bf829673c6269e8eba5c60fa121640fa2f829504f`.
- **Analysis-frame SHA-256:** `8ff14f833673fbad9c35ec3267c5c23335f98ba2b586e63bba67f98a755ee804`.
- **Semantic detector-frame SHA-256:** `93a00e87165516e6001877fcbb6ed30cdc58d73150f5198a826af063efb708d4`.
- **Detector frame:** 17,379 rows, 13 columns; eight categorical and five numeric predictors.

### Detector precision, recall, and F1

The values below are means across seeds 42, 123, and 2026. F1 includes its sample standard deviation. Full per-seed metrics and confusion counts are retained in the JSON artifact.

| Defect / detector | Rate | Precision | Recall | F1 mean ± sample SD |
|---|---:|---:|---:|---:|
| Missingness rule | 1% | 1.000000 | 1.000000 | 1.000000 ± 0 |
| Missingness rule | 5% | 1.000000 | 1.000000 | 1.000000 ± 0 |
| Missingness rule | 10% | 1.000000 | 1.000000 | 1.000000 ± 0 |
| Exact duplicate rule | 1% | 1.000000 | 1.000000 | 1.000000 ± 0 |
| Exact duplicate rule | 5% | 1.000000 | 1.000000 | 1.000000 ± 0 |
| Exact duplicate rule | 10% | 1.000000 | 1.000000 | 1.000000 ± 0 |
| Numeric parseability rule | 1% | 1.000000 | 1.000000 | 1.000000 ± 0 |
| Numeric parseability rule | 5% | 1.000000 | 1.000000 | 1.000000 ± 0 |
| Numeric parseability rule | 10% | 1.000000 | 1.000000 | 1.000000 ± 0 |
| Categorical consistency | 1% | 0.010005 | 1.000000 | 0.019812 ± 0 |
| Categorical consistency | 5% | 0.050004 | 1.000000 | 0.095245 ± 0 |
| Categorical consistency | 10% | 0.100007 | 1.000000 | 0.181830 ± 0.000002 |
| IQR | 1% | 0.873714 | 1.000000 | 0.932601 ± 0.000745 |
| IQR | 5% | 0.978796 | 1.000000 | 0.989284 ± 0.000531 |
| IQR | 10% | 0.995046 | 1.000000 | 0.997517 ± 0.000045 |
| Robust Z-score | 1% | 0.983010 | 1.000000 | 0.991432 ± 0.000371 |
| Robust Z-score | 5% | 0.996782 | 1.000000 | 0.998389 ± 0.000145 |
| Robust Z-score | 10% | 0.998781 | 1.000000 | 0.999390 ± 0.000107 |
| Isolation Forest | 1% | 0.976602 | 1.000000 | 0.988159 ± 0.002227 |
| Isolation Forest | 5% | 1.000000 | 0.221466 | 0.362621 ± 0.002259 |
| Isolation Forest | 10% | 1.000000 | 0.122435 | 0.218159 ± 0.000385 |

### Runtime and memory observations

Mean prediction runtime ± sample SD across the three seeds (seconds):

| Detector | 1% | 5% | 10% |
|---|---:|---:|---:|
| Missingness rule | 0.004844 ± 0.000174 | 0.005062 ± 0.000234 | 0.005294 ± 0.000388 |
| Exact duplicate rule | 0.009373 ± 0.000052 | 0.009964 ± 0.000058 | 0.010605 ± 0.000266 |
| Categorical consistency | 0.236091 ± 0.001858 | 0.244566 ± 0.000921 | 0.250910 ± 0.000525 |
| Numeric parseability | 0.134266 ± 0.001088 | 0.182622 ± 0.002474 | 0.250200 ± 0.025757 |
| IQR | 0.021511 ± 0.000152 | 0.088608 ± 0.000428 | 0.174289 ± 0.001729 |
| Robust Z-score | 0.019070 ± 0.000142 | 0.085758 ± 0.001237 | 0.168994 ± 0.000448 |
| Isolation Forest | 0.874620 ± 0.001702 | 0.893790 ± 0.000706 | 0.914021 ± 0.008002 |

The artifact also records the mean and sample SD of Python-traced peak allocation for every detector/rate pair. This is a partial memory proxy and does not capture every native NumPy/scikit-learn allocation.

### Interpretation and limits

1. The missingness, duplicate, and numeric-parseability rules achieved perfect metrics because the controlled defects closely match the deterministic rules and the reference schema is known. These results are optimistic and are not estimates of unknown-schema real-world performance.
2. The categorical consistency rule had recall 1.0 but very low precision (about 1%, 5%, and 10% at the corresponding injection rates). The production rule marks every value in a casefold-equivalent category group, so legitimate original category values are also flagged as false positives. This is the clearest detector weakness exposed by the larger mixed-type reference.
3. IQR and robust Z-score detected every injected extreme row in this experiment. Their precision improved with corruption rate because injected extremes became a larger share of the flagged set. The synthetic anomalies are deliberately high values; subtler multivariate anomalies are not evaluated here.
4. Isolation Forest retained high precision but recall dropped to 0.221 at 5% and 0.122 at 10%. The experiment fixes contamination at 5% while injecting anomalies at the cell level across five numeric columns; this does not hold row-level anomaly prevalence at 5%. The result motivates contamination-sensitivity experiments rather than a conclusion that Isolation Forest is generally inferior.
5. The benchmark uses one dataset, one documented semantic mapping, fixed detector thresholds, and synthetic defects. The exact-label rule metrics are not independent evidence of generalization.
6. Runtime excludes corruption generation and metric calculation. Python tracemalloc is not total process RSS and may omit native allocations.

**Next experiments:** improve categorical cell-level evidence to reduce false positives; vary Isolation Forest contamination against measured row-level anomaly prevalence; evaluate subtler and multivariate anomalies; and add downstream regression conditions for invalid values, duplicates, and numerical anomalies with the future test partition untouched.


## UCI Bike Sharing Isolation Forest contamination-sensitivity experiment

**Execution date:** 19 November 2026. The GitHub Actions workflow completed successfully; the JSON artifact was downloaded, parsed, and its payload SHA-256 verified before recording these results.

- **Dataset:** UCI Bike Sharing hourly, dataset 275, DOI 10.24432/C5W894, CC BY 4.0.
- **Reference:** 17,379 rows and 13 detector predictors (eight semantic categorical fields and five numeric fields); target and direct target components remain excluded.
- **Detector-frame SHA-256:** `93a00e87165516e6001877fcbb6ed30cdc58d73150f5198a826af063efb708d4`.
- **Cell corruption rates:** 1%, 5%, and 10%, applied to eligible cells across the five numeric predictors.
- **Seeds:** 42, 123, and 2026.
- **Isolation Forest contamination values:** 0.01, 0.05, and 0.10; 100 estimators.
- **Controls:** IQR multiplier 1.5 and modified robust-Z threshold 3.5.
- **Coverage:** 9 Isolation Forest contamination/rate combinations, 27 Isolation Forest seed runs, and 54 IQR/robust-Z control seed runs (81 detector-seed executions total). No runs were skipped.
- **Aggregation:** arithmetic mean and sample standard deviation (ddof=1) across the three seeds. Per-seed TP/FP/TN/FN and metrics are retained in the artifact.
- **Runtime:** corruption generation and metric calculation are excluded; the measured interval includes production detector execution.
- **Memory:** Python `tracemalloc` peak-allocation proxy; this is not total process RSS and may omit native NumPy/scikit-learn allocations.

### Execution provenance

- **Workflow:** [Bike Sharing Isolation Forest Sensitivity run 44442153834](https://github.com/emtharva1047/DataSentry/actions/runs/44442153834).
- **Artifact:** [uci-bike-sharing-if-contamination-sensitivity](https://github.com/emtharva1047/DataSentry/actions/runs/44442153834/artifacts/14491785761), retained until 19 December 2026.
- **Artifact ZIP SHA-256:** `422b188854fb86d89d155a2a0c875fa7d21798d970f1b73f6bfaaac174d2dc60`.
- **JSON payload SHA-256:** `9ad886358d00afe75425ca662f28cafcb9236d4736111288a6edc30054186ccf`.
- **Source archive SHA-256:** `b70182d0d0508e9abbb79306ce5c0cec34869000f8220175ac83d11dbe845401`.
- **hour.csv SHA-256:** `e03de4ee4ef4dc376ac6e04bf829673c6269e8eba5c60fa121640fa2f829504f`.
- **Analysis-frame SHA-256:** `8ff14f833673fbad9c35ec3267c5c23335f98ba2b586e63bba67f98a755ee804`.
- **Software:** Python 3.12 workflow; pandas 2.3.3, NumPy 2.5.5, scikit-learn 1.9.1.

### Measured Isolation Forest sensitivity

Ground-truth and predicted prevalence are row-level fractions over all 17,379 reference rows. The configured synthetic rate is cell-level and is not interchangeable with row prevalence. Precision and recall columns show means; F1, prevalence, runtime show mean ± sample SD.

| IF contamination | Cell corruption | Ground-truth row prevalence | Predicted row prevalence | Precision | Recall | F1 mean ± SD | Runtime seconds mean ± SD | Python peak allocation mean |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 0.01 | 1% | 4.8833% ± 0.0218 pp | 1.0012% ± 0.0000 pp | 1.000000 | 0.205030 | 0.340290 ± 0.001257 | 0.743766 ± 0.003941 | 5.040 MiB |
| 0.01 | 5% | 22.5789% ± 0.1716 pp | 1.0012% ± 0.0000 pp | 1.000000 | 0.044344 | 0.084923 ± 0.000619 | 0.753266 ± 0.001345 | 5.090 MiB |
| 0.01 | 10% | 40.8405% ± 0.0808 pp | 1.0012% ± 0.0000 pp | 1.000000 | 0.024515 | 0.047857 ± 0.000093 | 0.771546 ± 0.004373 | 5.132 MiB |
| 0.05 | 1% | 4.8833% ± 0.0218 pp | 5.0003% ± 0.0000 pp | 0.976602 | 1.000000 | 0.988159 ± 0.002227 | 0.755357 ± 0.002211 | 5.039 MiB |
| 0.05 | 5% | 22.5789% ± 0.1716 pp | 5.0003% ± 0.0000 pp | 1.000000 | 0.221466 | 0.362621 ± 0.002259 | 0.765121 ± 0.000405 | 5.090 MiB |
| 0.05 | 10% | 40.8405% ± 0.0808 pp | 5.0003% ± 0.0000 pp | 1.000000 | 0.122435 | 0.218159 ± 0.000385 | 0.786012 ± 0.002691 | 5.133 MiB |
| 0.10 | 1% | 4.8833% ± 0.0218 pp | 9.9968% ± 0.0066 pp | 0.488489 | 1.000000 | 0.656353 ± 0.002257 | 0.769051 ± 0.002091 | 5.038 MiB |
| 0.10 | 5% | 22.5789% ± 0.1716 pp | 9.9987% ± 0.0033 pp | 1.000000 | 0.442847 | 0.613847 ± 0.003105 | 0.778535 ± 0.002189 | 5.089 MiB |
| 0.10 | 10% | 40.8405% ± 0.0808 pp | 10.0006% ± 0.0000 pp | 1.000000 | 0.244870 | 0.393406 ± 0.000626 | 0.800657 ± 0.003199 | 5.132 MiB |

### Control checks

IQR and robust Z-score were each rerun for all three corruption rates under all three Isolation Forest contamination settings. All six detector/rate control groups compared three settings and passed: confusion counts and precision/recall/F1/accuracy were invariant, as expected because these production detectors do not consume the Isolation Forest contamination parameter.

### Interpretation

1. **The cell-level corruption rate produces a much larger row-level anomaly prevalence.** Across the five numeric columns, the measured affected-row prevalence was about 4.88% at 1% cell corruption, 22.58% at 5%, and 40.84% at 10%. This is why the cell injection rate must not be used as an Isolation Forest contamination setting without measuring row support.
2. **At 1% cell corruption, contamination 0.05 best matched the observed row prevalence among the three tested settings.** It predicted about 5.00% of rows and achieved mean precision 0.9766, recall 1.0, and F1 0.9882. Contamination 0.01 under-predicted positives (recall 0.2050); contamination 0.10 over-predicted them (precision 0.4885).
3. **At 5% and 10% cell corruption, even contamination 0.10 under-predicted row prevalence.** It selected about 10% of rows while measured ground truth was about 22.58% and 40.84%; recall was 0.4428 and 0.2449, respectively.
4. **Best F1 among only the tested thresholds** was contamination 0.05 for 1% cell corruption (0.9882), and 0.10 for 5% and 10% cell corruption (0.6138 and 0.3934). These are within-experiment comparisons, not a universal or production-calibrated optimum.
5. The sweep demonstrates the sensitivity of Isolation Forest's decision threshold to row-level anomaly prevalence. It does not establish that contamination should be set equal to observed synthetic prevalence in real datasets; real anomalies may be multivariate, subtle, clustered, or unknown.
6. Mean runtime ranged from about 0.744 to 0.801 seconds per run. Mean Python-traced peak allocation ranged from about 5.038 to 5.133 MiB; this is not total process memory.

### Limitations and next experiments

- One public reference dataset and one deliberately extreme numerical corruption mechanism.
- Three corruption seeds share one fixed reference; they are repeated synthetic realizations, not independent datasets.
- No contamination value is selected automatically and no universal optimum is claimed.
- The existing categorical consistency detector still needs cell-level evidence to reduce false positives.
- Downstream regression under invalid-value, duplicate, categorical, and numerical-anomaly corruption remains outstanding; future test partitions must remain untouched.
- Additional real-world or subtler anomaly references are needed before generalizing detector behaviour.


## Categorical consistency quality version 2 — refreshed detector benchmarks (19 November 2026)

**Implementation:** quality response version 2 flags surrounding whitespace independently. Within a casefold-equivalent group, a uniquely most-frequent trimmed spelling is treated as the observed canonical spelling; only less-frequent spellings are flagged. If the top frequency is tied, the group remains ambiguous and no case-only spelling is flagged. The detector benchmark imports the same production analysis helper, preventing the quality API and benchmark prediction logic from drifting.

Both public detector workflows were rerun on the quality-version-2 code. The table reports mean precision, recall, and F1 across seeds 42, 123, and 2026; F1 standard deviation is the sample standard deviation (ddof=1).

| Reference | Corruption rate | Injected categorical cells per seed | Precision | Recall | F1 mean ± sample SD |
|---|---:|---:|---:|---:|---:|
| UCI Wine (178 rows; derived alcohol_band) | 1% | 2 | 1.000 | 1.000 | 1.000000 ± 0 |
| UCI Wine | 5% | 9 | 1.000 | 1.000 | 1.000000 ± 0 |
| UCI Wine | 10% | 18 | 1.000 | 1.000 | 1.000000 ± 0 |
| UCI Bike Sharing (17,379 rows; 8 categorical predictors) | 1% | 1,391 | 1.000 | 1.000 | 1.000000 ± 0 |
| UCI Bike Sharing | 5% | 6,952 | 1.000 | 1.000 | 1.000000 ± 0 |
| UCI Bike Sharing | 10% | 13,904 | 1.000 | 1.000 | 1.000000 ± 0 |

Mean prediction runtime ± sample SD across seeds:

| Reference | 1% | 5% | 10% |
|---|---:|---:|---:|
| UCI Wine | 0.001273 ± 0.000046 s | 0.001293 ± 0.000030 s | 0.001315 ± 0.000009 s |
| UCI Bike Sharing | 0.353249 ± 0.003066 s | 0.370475 ± 0.001867 s | 0.384665 ± 0.006143 s |

Python-traced peak-allocation proxy (mean ± sample SD bytes):

| Reference | 1% | 5% | 10% |
|---|---:|---:|---:|
| UCI Wine | 31,519 ± 17 | 31,790 ± 12 | 32,137 ± 15 |
| UCI Bike Sharing | 5,170,632 ± 944 | 5,447,463 ± 2,089 | 6,003,000 ± 3,665 |

All 18 rate/seed combinations (six dataset/rate combinations × three seeds) completed with zero skips. For every seed and rate, TP equaled the injected cell count and FP/FN were zero. The clean-reference preflight passed for both references.

### Provenance and artifacts

- **UCI Wine workflow:** [Research Evaluation run 44444316810](https://github.com/emtharva1047/DataSentry/actions/runs/44444316810).
- **UCI Wine artifact:** [uci-wine-reference-experiment](https://github.com/emtharva1047/DataSentry/actions/runs/44444316810/artifacts/14492202525), retained for 30 days.
- **UCI Wine artifact ZIP SHA-256:** `7e1ccff12187ad403c8d4b86c9da300c1d0d8eb541cc7de0cd9d0487c4654c00`.
- **UCI Wine JSON SHA-256:** `4c68d58eca2338323cfe3c5bceac1411242878f2ad774ed0ec3f773694d0ee3b`.
- **UCI Bike Sharing workflow:** [Bike Sharing Detector Research run 44444316802](https://github.com/emtharva1047/DataSentry/actions/runs/44444316802).
- **UCI Bike Sharing artifact:** [uci-bike-sharing-detector-benchmark](https://github.com/emtharva1047/DataSentry/actions/runs/44444316802/artifacts/14492218315), retained for 30 days.
- **UCI Bike Sharing artifact ZIP SHA-256:** `15b60139c1f299089e66fad8f099d9fb7392d911cff522bfb39a96e8e9b4563e`.
- **UCI Bike Sharing JSON SHA-256:** `303510b1f37fe3bd1ed836ee336f9413d5c7db47554ac72893f6ace1f6c9fac9`.
- **Bike Sharing detector-frame SHA-256:** `93a00e87165516e6001877fcbb6ed30cdc58d73150f5198a826af063efb708d4`.
- **Software:** Python 3.12.16, pandas 2.3.3, NumPy 2.5.5, scikit-learn 1.9.1.

### Interpretation and limitations

1. The previous 18 November Bike Sharing precision of 0.010–0.100 was produced by quality version 1, which flagged every member of a casefold-equivalent group. The quality-version-2 results supersede those categorical rows; the other detector results in the historical benchmark are unchanged.
2. The synthetic categorical corruption utility currently adds both surrounding whitespace and swapped case. Since the revised detector always flags surrounding whitespace, the 1.0 precision/recall results validate the combined whitespace-plus-case defect and show that canonical category members are no longer false positives. They do **not** independently measure pure case-only detection.
3. Pure case-only majority/tie behavior is covered by direct unit tests: a unique modal spelling is retained, a minority spelling is flagged, and tied groups remain ambiguous. A separate pure-case-only public-reference benchmark remains future work.
4. The modal-spelling rule is a heuristic, not a business schema. A legitimate minority spelling can still be flagged; a genuine variant can be missed when counts tie or when the erroneous spelling becomes dominant.
5. The Wine benchmark uses one derived categorical feature (`alcohol_band`), not an original UCI feature. The Bike benchmark uses the documented semantic mappings for integer-coded categories.
6. These controlled synthetic results are not estimates of real-world performance. Runtime excludes corruption generation and metric calculation; `tracemalloc` is a partial allocation proxy and does not capture all native-library memory.

The refreshed results are part of the reproducible research record, but M9 remains open for additional downstream regression defect families, pure case-only evaluation, repeated-seed baseline uncertainty, and final analysis.


## Pure case-only categorical benchmark — 20 November 2026

**Experiment:** `pure_case_only_categorical_consistency`  
**Ground-truth schema:** 2  
**Categorical mode:** `case_only` (letter case swapped; no leading/trailing whitespace)  
**Rates:** 1%, 5%, 10% of eligible categorical cells  
**Seeds:** 42, 123, 2026  
**References:** UCI Wine Recognition (178 rows, 14 detector columns including derived `alcohol_band`) and UCI Bike Sharing (17,379 rows, 13 detector columns including eight semantically mapped categorical predictors).

### Measured detector results

All values are the arithmetic mean across three seeds; F1 sample standard deviation uses ddof=1.

| Reference | Rate | Injected cells per seed | Precision | Recall | F1 mean ± sample SD |
|---|---:|---:|---:|---:|---:|
| UCI Wine | 1% | 2 | 1.000 | 1.000 | 1.000000 ± 0 |
| UCI Wine | 5% | 9 | 1.000 | 1.000 | 1.000000 ± 0 |
| UCI Wine | 10% | 18 | 1.000 | 1.000 | 1.000000 ± 0 |
| UCI Bike Sharing | 1% | 1,391 | 1.000 | 1.000 | 1.000000 ± 0 |
| UCI Bike Sharing | 5% | 6,952 | 1.000 | 1.000 | 1.000000 ± 0 |
| UCI Bike Sharing | 10% | 13,904 | 1.000 | 1.000 | 1.000000 ± 0 |

For every seed/rate/reference, TP equaled the injected count and FP/FN were zero. All 18 reference/rate/seed trials completed; no detector runs were skipped. F1 sample SD was zero for every aggregate.

### Runtime and Python allocation proxy

Mean prediction runtime ± sample SD across seeds:

| Reference | 1% | 5% | 10% |
|---|---:|---:|---:|
| UCI Wine | 0.000821 ± 0.000049 s | 0.000791 ± 0.000029 s | 0.000777 ± 0.000018 s |
| UCI Bike Sharing | 0.315265 ± 0.014189 s | 0.320748 ± 0.003765 s | 0.332415 ± 0.006997 s |

Python-traced peak-allocation proxy (mean bytes ± sample SD):

| Reference | 1% | 5% | 10% |
|---|---:|---:|---:|
| UCI Wine | 31,754 ± 24 | 31,701 ± 16 | 31,637 ± 16 |
| UCI Bike Sharing | 5,149,495 ± 5,133 | 5,210,460 ± 618 | 5,394,556 ± 1,327 |

Runtime measures the production categorical prediction function only; corruption generation and metric calculation are excluded. `tracemalloc` is a Python allocation proxy and does not include every native NumPy/pandas allocation.

### Clean-reference preflight

Both references passed with zero missing cells, zero exact duplicate rows, zero pre-existing categorical findings, and zero invalid numeric cells. Statistical outliers were not rejected because unusual does not mean invalid.

### Provenance and artifacts

- **Workflow:** [Pure Case-Only Categorical Research run 44658968650](https://github.com/emtharva1047/DataSentry/actions/runs/44658968650).
- **Artifact:** [pure-case-only-categorical](https://github.com/emtharva1047/DataSentry/actions/runs/44658968650/artifacts/14593779461), retained for 30 days (expires 20 December 2026).
- **Artifact ZIP SHA-256:** `d488502b0388b292d6714dbaebaed935b8b420a89b98a94cebd7e4b9391a4ac0`.
- **JSON SHA-256:** `52538f330b0931ae88bbdd2ffa8a612123ec78df25798da388df82f044b88188`.
- **UCI Wine detector-frame SHA-256:** `44f38eddfcac4516356d48300c9b05a1f37b24605c2cb20b9a1f7b047a10eca6`.
- **UCI Bike Sharing detector-frame SHA-256:** `93a00e87165516e6001877fcbb6ed30cdc58d73150f5198a826af063efb708d4`.
- **Software:** Python 3.12.16, pandas 2.3.3, NumPy 2.5.5, scikit-learn 1.9.1.

### Interpretation and limitations

1. The experiment isolates pure case-only changes from the historical combined whitespace-plus-case transform. It directly tests the quality-v2 canonical-spelling heuristic rather than relying on whitespace detection.
2. The perfect controlled result depends on the synthetic generator changing only a minority of values within each casefold-equivalent group, leaving the original spelling uniquely dominant. It does not establish performance when erroneous spellings are dominant, when groups are tied, or when legitimate minority variants occur in real data.
3. The modal-spelling heuristic remains a review aid, not a business schema. Legitimate minority spellings can be flagged; tied groups remain ambiguous and are not case-only findings.
4. UCI Wine uses one derived feature (`alcohol_band`) for categorical coverage. Bike Sharing uses documented semantic labels for eight integer-coded calendar/weather predictors.
5. These two references and three synthetic seeds are not independent datasets or a real-world prevalence sample. The results must not be generalized to arbitrary schemas or production data.

The pure case-only benchmark closes the previously documented subtype-isolation gap. Additional downstream regression corruption families, repeated-seed baseline uncertainty, and final delivery remain outstanding.


## UCI Bike Sharing downstream duplicate-row regression — 21 November 2026

**Workflow:** [Bike Sharing Downstream Regression Research run 44854541701](https://github.com/emtharva1047/DataSentry/actions/runs/44854541701)  
**Artifact:** [uci-bike-sharing-regression](https://github.com/emtharva1047/DataSentry/actions/runs/44854541701/artifacts/14686439544) (30-day retention; expires 21 December 2026)  
**Artifact ZIP SHA-256:** 00a3a8164cb0c30103bb8336c4312fa6a5e5c9f195eafe3f4f58689978865725

The workflow completed 18 rate/seed experiments: missingness and exact duplicate-row corruption × 1%, 5%, and 10% × seeds 42, 123, and 2026. Each experiment fitted clean, corrupted, and cleaned-corrupted Ridge conditions (54 model fits total). No trials were skipped.

### Duplicate-row protocol and integrity checks

- Dataset: UCI Bike Sharing hourly, dataset 275, DOI 10.24432/C5W894, CC BY 4.0.
- Reference: 17,379 rows, 13 model predictors, target cnt.
- Target components casual and registered were excluded; instant was used only for ordering; day_index was derived from dteday.
- Chronological split: 13,034 training rows and 4,345 future test rows.
- Duplicate injection operated on the combined training frame containing all selected features and cnt, preserving target alignment.
- At 1%, 5%, and 10%, 131, 652, and 1,304 exact duplicate training rows were appended.
- The production drop_exact_duplicates transform removed exactly the appended rows and restored the original training feature/target pairs and row count.
- The future test partition was never passed to corruption or cleaning. Its SHA-256 (2f9613a31116dbdb6e0e272c123778ed3a45e62783393ead8df8c14cb7aef309) was identical for every rate and seed.

### Measured duplicate-row results

Values are mean ± sample standard deviation (ddof=1) across the three corruption seeds. The clean baseline is identical at all rates: MAE 100.722797 ± 0.000000, RMSE 135.412419 ± 0.000000, R² 0.621144 ± 0.000000.

| Rate | Condition | MAE | RMSE | R² |
|---:|---|---:|---:|---:|
| 1% | Corrupted | 100.730478 ± 0.067534 | 135.499997 ± 0.046698 | 0.620654 ± 0.000262 |
| 1% | Cleaned-corrupted | 100.722797 ± 0.000000 | 135.412419 ± 0.000000 | 0.621144 ± 0.000000 |
| 5% | Corrupted | 100.642324 ± 0.195718 | 135.397958 ± 0.069474 | 0.621225 ± 0.000389 |
| 5% | Cleaned-corrupted | 100.722797 ± 0.000000 | 135.412419 ± 0.000000 | 0.621144 ± 0.000000 |
| 10% | Corrupted | 100.816144 ± 0.247399 | 135.395768 ± 0.107894 | 0.621238 ± 0.000604 |
| 10% | Cleaned-corrupted | 100.722797 ± 0.000000 | 135.412419 ± 0.000000 | 0.621144 ± 0.000000 |

Paired cleaned-minus-corrupted deltas:

| Rate | ΔMAE | ΔRMSE | ΔR² |
|---:|---:|---:|---:|
| 1% | -0.007681 ± 0.067534 | -0.087578 ± 0.046698 | +0.000490 ± 0.000262 |
| 5% | +0.080473 ± 0.195718 | +0.014461 ± 0.069474 | -0.000081 ± 0.000389 |
| 10% | -0.093347 ± 0.247399 | +0.016651 ± 0.107894 | -0.000094 ± 0.000604 |

Exact duplicate insertion creates additional training weight and caused small, mixed metric changes. The production cleaning transform restored the clean training rows and reproduced the clean baseline metrics exactly. This is a controlled validation of duplicate removal for this reference, not a general rule that repeated event rows are invalid.

### Source provenance and software

- UCI archive SHA-256: b70182d0d0508e9abbb79306ce5c0cec34869000f8220175ac83d11dbe845401.
- hour.csv SHA-256: e03de4ee4ef4dc376ac6e04bf829673c6269e8eba5c60fa121640fa2f829504f.
- Analysis-frame SHA-256: 8ff14f833673fbad9c35ec3267c5c23335f98ba2b586e63bba67f98a755ee804.
- Python 3.12.16, pandas 2.3.3, NumPy 2.5.5, scikit-learn 1.9.1.

Limitations: one reference, one chronological 75/25 split, fixed Ridge alpha 1.0, and seeds that vary corruption selection but not the temporal split. This is not rolling-origin cross-validation. The same artifact includes the rerun missingness control; the earlier 17 November missingness result remains documented in its original section.


## UCI Bike Sharing downstream invalid-value regression — 22 November 2026

**Workflow:** [Bike Sharing Downstream Regression Research run 44974867255](https://github.com/emtharva1047/DataSentry/actions/runs/44974867255)  
**Artifact:** [uci-bike-sharing-regression](https://github.com/emtharva1047/DataSentry/actions/runs/44974867255/artifacts/14734839544) (30-day retention; expires 22 December 2026)  
**Artifact ZIP SHA-256:** ee7522b96b480136567f7d7012446d677375ae7d846d0eb0e693059478423e54  
**JSON SHA-256:** d9d971c8f98cd881fbb5bca54300da19c4866ffecfab310204d46e5bd22f6a80

The completed workflow evaluated three training-only defect families (missingness, exact duplicates, invalid_values) × three corruption rates (1%, 5%, 10%) × three seeds (42, 123, 2026): 27 rate/seed experiments and 81 Ridge fits. No trials were skipped. The invalid-value condition comprised nine rate/seed experiments and 27 model fits.

### Invalid-value protocol and integrity

- Dataset: UCI Bike Sharing hourly, dataset 275, DOI 10.24432/C5W894, CC BY 4.0; 17,379 rows, target cnt, 13 predictors.
- Chronological split: 13,034 training rows and 4,345 future test rows. casual and registered were excluded as direct target components; instant was used only for ordering; day_index was derived from dteday.
- The corruption generator received the explicit numeric feature list (temp, atemp, hum, windspeed, day_index). This prevents numeric-looking category-code strings from being treated as continuous predictors.
- Invalid tokens were injected only into training features, never into cnt or the future test partition. Rates 1%, 5%, and 10% affected 652, 3,259, and 6,517 numeric cells respectively, identical in count across the three seeds at each rate.
- The production fill_numeric_median operation converted exactly the injected invalid cells to missing, then imputed from finite training values. It reported zero pre-existing missing cells for these experiments, retained all 13,034 training rows, and did not modify the uploaded/reference source.
- The leakage-safe model pipeline independently coerced the invalid tokens to missing and fit its median imputer on training data only. The explicit production-cleaned condition produced exactly the same MAE/RMSE/R² as the pipeline-imputed corrupted condition for every seed and rate.
- The future test partition was never passed to corruption or cleaning. Its SHA-256 (2f9613a31116dbdb6e0e272c123778ed3a45e62783393ead8df8c14cb7aef309) was identical across all experiments.

### Measured invalid-value results

Values are mean ± sample standard deviation (ddof=1) across seeds 42, 123, and 2026. The clean baseline is identical at every rate: MAE 100.722797 ± 0.000000, RMSE 135.412419 ± 0.000000, R² 0.621144 ± 0.000000.

| Rate | Condition | MAE | RMSE | R² |
|---:|---|---:|---:|---:|
| 1% | Corrupted | 100.792503 ± 0.017518 | 135.356747 ± 0.009090 | 0.621456 ± 0.000051 |
| 1% | Production-cleaned | 100.792503 ± 0.017518 | 135.356747 ± 0.009090 | 0.621456 ± 0.000051 |
| 5% | Corrupted | 100.878201 ± 0.112688 | 135.094531 ± 0.015565 | 0.622921 ± 0.000087 |
| 5% | Production-cleaned | 100.878201 ± 0.112688 | 135.094531 ± 0.015565 | 0.622921 ± 0.000087 |
| 10% | Corrupted | 101.092482 ± 0.253956 | 134.789148 ± 0.025729 | 0.624624 ± 0.000143 |
| 10% | Production-cleaned | 101.092482 ± 0.253956 | 134.789148 ± 0.025729 | 0.624624 ± 0.000143 |

The paired production-cleaned-minus-corrupted deltas for MAE, RMSE, and R² were exactly 0.000000 (sample SD 0.000000) at all three rates. Mean fit runtimes (seconds) for clean/corrupted/production-cleaned conditions were respectively: 1% 0.071251/0.080507/0.081300; 5% 0.069811/0.080506/0.081008; 10% 0.070897/0.080773/0.080075.

### Interpretation and limitations

This experiment shows parity between two explicit training-only preprocessing paths: the model pipeline's numeric coercion plus training-fitted median imputer, and the production fill_numeric_median cleaning operation. The cleaned condition did not improve predictive metrics over the corrupted condition because both paths imputed the same invalid cells from the same training-only finite-value median. Relative to the clean baseline, MAE increased while RMSE and R² improved slightly as random feature cells were removed from model input; the effects are mixed and specific to this split. No general claim of predictive benefit or harm is warranted.

The injected token is an intentionally obvious non-numeric sentinel. This experiment does not test plausible-but-wrong finite numbers, unit errors, locale-specific parsing, or semantic range violations. It uses one chronological 75/25 holdout and a fixed Ridge alpha 1.0, not rolling-origin cross-validation. The three seeds vary corruption positions, not the temporal split. The results should not be generalized beyond this controlled reference.


## 23 November 2026 — Numerical-anomaly downstream regression (measured)

### Protocol and provenance

The UCI Bike Sharing hourly reference (UCI dataset 275; 17,379 rows) was split chronologically into 13,034 training rows and 4,345 future test rows. Only the five declared numeric training predictors were eligible for finite high-anomaly injection; the target, categorical predictors, and future test partition were not corrupted. The fixed model was Ridge regression (alpha 1.0), with training-only preprocessing. Rates were 1%, 5%, and 10%; seeds were 42, 123, and 2026.

The full downstream workflow now covers four corruption families—missingness, exact duplicate rows, invalid numeric tokens, and numerical anomalies—at three rates and three seeds: 36 rate/seed trials and 108 model fits. This section reports the numerical-anomaly subset (9 trials, 27 model fits). The production cleaned condition uses `clip_numeric_iqr`: Tukey 1.5×IQR fences fitted on the corrupted training partition only, clipping both tails without deleting rows.

### Measured regression metrics

Values are mean ± sample standard deviation (ddof=1) across the three corruption seeds. The clean baseline is identical across rates because the chronological split is fixed.

| Rate | Condition | MAE ↓ | RMSE ↓ | R² ↑ |
|---:|---|---:|---:|---:|
| — | Clean | 100.722797 ± 0 | 135.412419 ± 0 | 0.621144 ± 0 |
| 1% | Corrupted | 105.259599 ± 0.090470 | 138.013730 ± 0.019881 | 0.606449 ± 0.000114 |
| 1% | IQR clipped | 101.436026 ± 0.122883 | 135.638110 ± 0.001888 | 0.619880 ± 0.000011 |
| 5% | Corrupted | 105.262880 ± 0.062322 | 138.073959 ± 0.011749 | 0.606105 ± 0.000067 |
| 5% | IQR clipped | 102.841495 ± 0.192790 | 136.514814 ± 0.107695 | 0.614951 ± 0.000608 |
| 10% | Corrupted | 105.318074 ± 0.060401 | 138.076463 ± 0.005034 | 0.606091 ± 0.000029 |
| 10% | IQR clipped | 103.730188 ± 0.097265 | 137.028821 ± 0.097784 | 0.612046 ± 0.000554 |

### Paired IQR-clipped minus corrupted differences

Negative MAE/RMSE and positive R² indicate improvement after clipping.

| Rate | ΔMAE | ΔRMSE | ΔR² |
|---:|---:|---:|---:|
| 1% | -3.823573 ± 0.041716 | -2.375620 ± 0.021416 | +0.013432 ± 0.000123 |
| 5% | -2.421385 ± 0.149402 | -1.559145 ± 0.095975 | +0.008845 ± 0.000540 |
| 10% | -1.587886 ± 0.137907 | -1.047642 ± 0.092956 | +0.005955 ± 0.000526 |

### Ground truth, cleaning evidence, and test integrity

| Rate | Injected cells | IQR-clipped cells per seed |
|---:|---:|---:|
| 1% | 652 | 739, 736, 739 |
| 5% | 3,259 | 3,342, 3,339, 3,344 |
| 10% | 6,517 | 6,565, 6,565, 6,566 |

The IQR operation clipped 48–87 additional cells per seed beyond the injected anomalies. These are other training observations outside the fitted IQR fences; they are not ground-truth injected defects and may be legitimate extremes. This is why the operation is high-risk, never auto-selected, and requires preview plus explicit apply. Training row count remained 13,034 in every condition.

The future test partition retained SHA-256 `2f9613a31116dbdb6e0e272c123778ed3a45e62783393ead8df8c14cb7aef309` across all runs. Source provenance: UCI archive SHA-256 `b70182d0d0508e9abbb79306ce5c0cec34869000f8220175ac83d11dbe845401`; `hour.csv` SHA-256 `e03de4ee4ef4dc376ac6e04bf829673c6269e8eba5c60fa121640fa2f829504f`; analysis-frame SHA-256 `8ff14f833673fbad9c35ec3267c5c23335f98ba2b586e63bba67f98a755ee804`. Software: Python 3.12.16, pandas 2.3.3, NumPy 2.5.5, scikit-learn 1.9.1.

### Interpretation and limitations

IQR clipping improved all three reported metrics over the corrupted condition at each tested rate, but the clipped model did not recover the clean baseline. The benefit diminished as corruption rate increased. The operation also clipped pre-existing IQR outliers beyond the injected cells, so some changed observations may be valid. This experiment does not establish that IQR clipping is appropriate for arbitrary domains or that all statistical outliers are errors.

The experiment uses one chronological 75/25 holdout and fixed Ridge alpha 1.0, not rolling-origin validation or model tuning. Seeds vary corruption locations, not the temporal split. Results are specific to this controlled synthetic high-anomaly mechanism and the selected UCI reference.

### Artifact and reproducibility

Workflow: [Bike Sharing Downstream Regression Research](https://github.com/emtharva1047/DataSentry/actions/runs/45098990303). The JSON artifact contains per-seed metrics, paired differences, exact cell labels, cleaning summaries, runtime, and provenance. Artifact ZIP SHA-256: `828729300f41f23dafd3619ed0ed9e0a7f0f36484e171e77ba842c178287ffd0`; JSON SHA-256: `adca2809d3e9c392ef299f94a11a53f342cfacd3ebe7ebf78b9550b958d8683d`. The ZIP artifact is retained by GitHub Actions until 23 December 2026.


## 24 November 2026 — Pure case-only categorical downstream regression

### Dataset and protocol

The experiment uses the UCI Bike Sharing hourly reference (dataset 275, DOI 10.24432/C5W894, CC BY 4.0), with 17,379 rows and target cnt. Five numeric predictors and eight integer-coded calendar/weather predictors are used. The eight categorical codes are mapped to the shared, explicit semantic labels used by detector research; the mapping is stored in the artifact. The original analysis-frame SHA-256 is retained separately from the semantic regression-frame SHA-256.

| Configuration | Value |
|---|---:|
| Training rows | 13,034 |
| Future test rows | 4,345 |
| Split | Chronological 75/25 |
| Model | Ridge regression |
| Alpha | 1.0 |
| Defect families | Missingness, duplicates, invalid values, numerical anomalies, categorical inconsistency |
| Corruption rates | 1%, 5%, 10% |
| Seeds | 42, 123, 2026 |
| Total rate/seed trials | 45 |
| Total model fits | 135 |

The categorical condition isolates pure case-only corruption. The generator changes letter case only, records exact training row/column labels, and does not modify the target or future test partition. The cleaned condition applies the production lowercase_categories operation to training rows. It applies the same fixed deterministic lowercase transform to an inference copy of the future test features; no test statistics are fitted and the raw test frame remains unchanged.

### Case-only corruption counts

| Rate | Injected categorical cells per seed | Lowercase-cleaned cells per seed |
|---:|---:|---:|
| 1% | 1,043 | 1,043 |
| 5% | 5,214 | 5,214 |
| 10% | 10,428 | 10,428 |

### Downstream regression results

Metrics are mean ± sample standard deviation (ddof=1) across the three corruption seeds. The clean baseline is identical across seeds because the chronological split and model configuration are fixed.

| Rate | Condition | MAE ↓ | RMSE ↓ | R² ↑ |
|---:|---|---:|---:|---:|
| — | Clean baseline | 100.727961 ± 0 | 135.411983 ± 0 | 0.621147 ± 0 |
| 1% | Case-corrupted | 100.740612 ± 0.039058 | 135.388223 ± 0.106700 | 0.621280 ± 0.000597 |
| 1% | Production-cleaned | 100.727961 ± 0 | 135.411983 ± 0 | 0.621147 ± 0 |
| 5% | Case-corrupted | 100.751874 ± 0.144984 | 135.415725 ± 0.130946 | 0.621126 ± 0.000733 |
| 5% | Production-cleaned | 100.727961 ± 0 | 135.411983 ± 0 | 0.621147 ± 0 |
| 10% | Case-corrupted | 100.812485 ± 0.337342 | 135.474931 ± 0.233422 | 0.620794 ± 0.001307 |
| 10% | Production-cleaned | 100.727961 ± 0 | 135.411983 ± 0 | 0.621147 ± 0 |

### Paired cleaned-minus-corrupted differences

| Rate | ΔMAE | ΔRMSE | ΔR² |
|---:|---:|---:|---:|
| 1% | -0.012651 ± 0.039058 | +0.023760 ± 0.106700 | -0.000133 ± 0.000597 |
| 5% | -0.023913 ± 0.144984 | -0.003742 ± 0.130946 | +0.000021 ± 0.000733 |
| 10% | -0.084524 ± 0.337342 | -0.062948 ± 0.233422 | +0.000353 ± 0.001307 |

The cleaned condition exactly reproduces the clean baseline for MAE, RMSE, and R². The corrupted-condition differences are small and not consistently directional: MAE is slightly worse at all three rates, while RMSE and R² move in mixed directions at 1% and 5%, with small degradation at 10%. These results do not establish a large or universal predictive effect.

### Test integrity and interpretation

The raw chronological future-test partition retained SHA-256 `a1b865ceaeffc4246da5b08d3ee29c41f20dcb0a76c281d39baa8e335392f00b` across all 45 rate/seed trials. Every run reports test_partition_untouched=true and test_transform_fitted_parameters=false. The cleaned condition's lowercase transform is a fixed inference-time normalization applied to a copy; no test statistics or labels are used to fit preprocessing.

Lowercase normalization is high-risk because it can merge semantically distinct categories. It is used here only for the documented case-insensitive Bike Sharing semantic labels and is not a universal cleaning recommendation. The three seeds vary corruption locations, not the chronological split. This is one fixed holdout, not rolling-origin cross-validation or model tuning. The experiment uses one public reference and one fixed Ridge alpha.

### Provenance and reproducibility

- Workflow: [Bike Sharing Downstream Regression Research](https://github.com/emtharva1047/DataSentry/actions/runs/45310571907)
- Artifact: uci-bike-sharing-regression
- Artifact ZIP SHA-256: `28b8a3fa87f8d18059fd07fff70265cc4212eea79a2c451bbc72d9d10be2cd82`
- JSON SHA-256: `ec8345f423e21c4d2585db8b608ef5e3dd20c53751c5b106f425dcaf59e1504c`
- UCI archive SHA-256: `b70182d0d0508e9abbb79306ce5c0cec34869000f8220175ac83d11dbe845401`
- hour.csv SHA-256: `e03de4ee4ef4dc376ac6e04bf829673c6269e8eba5c60fa121640fa2f829504f`
- Original analysis-frame SHA-256: `8ff14f833673fbad9c35ec3267c5c23335f98ba2b586e63bba67f98a755ee804`
- Semantic regression-frame SHA-256: `8af8260347aad4b35c548b5b715cfb80aae545f9e23f76136933b846845b6714`
- Software: Python 3.12.16, pandas 2.3.3, NumPy 2.5.5, scikit-learn 1.9.1.


## 25 November 2026 — Clean Ridge baseline rolling-origin stability (measured)

### Dataset and protocol

The experiment uses the UCI Bike Sharing hourly reference (dataset 275, DOI 10.24432/C5W894, CC BY 4.0), with 17,379 chronologically ordered rows and target cnt. The semantic regression frame has 13 predictors: eight documented categorical calendar/weather labels and five numeric predictors. The casual and registered columns are excluded because they are direct components of cnt; day_index is derived from dteday and is documented in the artifact.

A clean Ridge baseline (alpha 1.0) is evaluated on three expanding training prefixes and the immediately following, non-overlapping 10% future windows. This places all evaluation windows in the final 30% of the chronological reference. Feature-type inference, median imputation, scaling, and one-hot encoding are fitted independently on each training prefix only. The model is deterministic; no random seed is used.

| Window | Training prefix | Training rows | Future test positions | Test rows | MAE | RMSE | R² |
|---:|---:|---:|---:|---:|---:|---:|---:|
| 1 | 70% | 12,165 | 12,165–13,902 | 1,738 | 108.992432 | 138.029885 | 0.602382 |
| 2 | 80% | 13,903 | 13,903–15,640 | 1,738 | 112.552795 | 149.426506 | 0.613383 |
| 3 | 90% | 15,641 | 15,641–17,378 | 1,738 | 85.467547 | 116.295765 | 0.617024 |

### Temporal-window dispersion

Mean and sample standard deviation (ddof=1) across the three future windows:

| Metric | Mean | Sample SD |
|---|---:|---:|
| MAE ↓ | 102.337591 | 14.717943 |
| RMSE ↓ | 134.584052 | 16.832018 |
| R² ↑ | 0.610930 | 0.007623 |

MAE and RMSE vary substantially by future window; the final 10% window is easier under these metrics than the preceding two. This is evidence of temporal heterogeneity in this reference and model setup. A single fixed 75/25 holdout would not expose this window-to-window variation.

This is temporal-window variability, not stochastic seed uncertainty. The sample SD is descriptive across three non-overlapping test windows and is not a confidence interval. Training prefixes overlap by design as the window expands; future test windows do not overlap. The analysis uses one public reference and one fixed Ridge alpha, with no model tuning or confidence-interval claim.

### Integrity and provenance

- Every fold records preprocessing_fit_scope = training_partition_only and test_partition_untouched = true.
- Future test-window SHA-256 values: window 1 a8472896fb25580df678b2efff056d27834534d87c0dabb580b83af7c8ff4aa7; window 2 22fdbfd9bb829a1c335389db9f21df10328886413ed04d0f9883c3ffb641b71; window 3 136bdd305f98e59b9d56158a3ccf1fa532ecdb6a96957da42ffa71398047adee.
- Semantic regression-frame SHA-256: 8af8260347aad4b35c548b5b715cfb80aae545f9e23f76136933b846845b6714.
- UCI archive SHA-256: b70182d0d0508e9abbb79306ce5c0cec34869000f8220175ac83d11dbe845401.
- hour.csv SHA-256: e03de4ee4ef4dc376ac6e04bf829673c6269e8eba5c60fa121640fa2f829504f.
- Software: Python 3.12.16, pandas 2.3.3, NumPy 2.5.5, scikit-learn 1.9.1.

### Artifact and reproducibility

Workflow: [Bike Sharing Rolling-Origin Baseline Stability](https://github.com/emtharva1047/DataSentry/actions/runs/45531043258). The JSON artifact contains the full configuration, semantic category maps, source fingerprints, per-window train/test positions, per-window metrics, aggregate mean/sample SD, and limitations.

- Artifact name: uci-bike-sharing-rolling-origin-baseline
- Artifact ID: 14984682241
- Artifact ZIP SHA-256: f957debce5246bb9957db457431929ba20cc41a08c6b7cf953fa6cd5b8ae26c3
- JSON SHA-256: e21d2b85a87a2774fb40cf9899a4c813d71caf694ac48ebf3f8eed5ce8f309a1
- GitHub Actions retention expiry: 25 December 2026.

