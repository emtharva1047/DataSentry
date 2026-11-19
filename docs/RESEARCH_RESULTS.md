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


## UCI Bike Sharing mixed-type detector benchmark

**Execution date:** 18 November 2026. The final PR-head GitHub Actions workflow completed successfully; the job output and uploaded JSON artifact were inspected before recording these results.

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
