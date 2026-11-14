# DataSentry Research Plan

## Working title

An Experimental Evaluation of Hybrid Rule-Based and Machine Learning Techniques for Automated Data Quality Assessment and ML Readiness.

## Research questions

1. How accurately do statistical, rule-based, and ML techniques detect controlled data defects?
2. How does a hybrid detector compare with individual techniques?
3. Does recommended cleaning improve downstream model performance under controlled corruption?
4. How does dataset size affect detection runtime?

## Candidate datasets

Use suitable public tabular datasets such as UCI Bank Marketing and Wine Quality after checking their source documentation and usage terms. Record the exact source, retrieval date/version, target, schema, and preprocessing.

## Controlled corruption

Create corrupted copies from a clean reference dataset using fixed random seeds. Candidate defects:
- Missing cells at configured rates.
- Exact duplicate records.
- Category casing and whitespace inconsistencies.
- Invalid type/domain values.
- Numerical extremes injected with a documented procedure.

Test example corruption proportions of 1%, 5%, and 10% where meaningful. These are experimental settings, not assumptions about real-world defect rates. Save row- and cell-level ground-truth labels.

## Implemented synthetic-corruption and ground-truth contract

The in-memory implementation is backend/app/services/dataset_research.py. It exposes inject_synthetic_corruption(frame, rate, seed, defects), evaluate_binary_detector(ground_truth, predictions), and aggregate_seed_metrics(runs). These functions are research primitives; no public API route, persisted experiment artifact, or detector result is claimed by this increment.

The generator accepts a non-empty DataFrame with unique, non-empty string column names, a finite rate in (0, 0.5], a 32-bit unsigned seed, and one or more supported defect names. A NumPy default_rng(seed) controls selection. For each cell-level defect, the requested count is the ceiling of the rate multiplied by the currently eligible cells, with a minimum of one when candidates exist. Duplicate insertion applies the same rule to eligible source rows. Actual eligible counts and skipped reasons are returned in the ground truth.

Supported defects and injection rules:

- **Missingness:** replace selected observed cells with pandas missing values.
- **Duplicates:** append exact copies of selected source rows. Source rows are reserved before cell corruption so the inserted record is an exact duplicate. Only the appended row is labeled as the duplicate, matching first-occurrence duplicate detectors.
- **Categorical inconsistency:** wrap selected non-empty string values in whitespace and swap their case. The original category is retained in the untouched input frame.
- **Invalid values:** replace selected finite values in inferred numeric-like columns with a collision-checked non-numeric sentinel.
- **Numerical anomalies:** replace selected finite numeric cells with a finite value above the original column maximum, where representable. Columns with insufficient numeric evidence or no representable higher finite value are skipped.

Numeric columns require at least four finite values and 80% finite parseability among non-missing values. Categorical candidates are non-numeric columns containing non-empty strings. Defect selections do not overlap at the same cell; duplicate source rows are not modified by cell corruptions. The input DataFrame is copied and never mutated. The returned frame is in memory only.

Ground-truth schema version 1 contains source/corrupted shapes, seed, rate, selected defects, inferred eligible columns, per-defect status/count/records, cell labels, duplicate-row records, and grouped row labels. Every cell label has a zero-based row position in the returned corrupted frame, a one-based data-row number (CSV header excluded), a column name, and a defect type. Duplicate records additionally include both inserted and source row positions. These labels describe only defects injected by this generator; pre-existing defects in the reference frame are not labeled.

evaluate_binary_detector computes TP, FP, TN, FN, precision, recall, F1, and accuracy for equal-length non-empty binary sequences. Undefined precision, recall, or F1 uses zero and is explicitly reported. aggregate_seed_metrics requires at least three distinct unsigned seeds, identical metric names, and finite numeric values. It reports the arithmetic mean and sample standard deviation (ddof=1), retaining per-seed values. It does not silently drop failed or missing runs.

The generator is now connected to a defect-specific benchmark runner in backend/app/services/dataset_benchmark.py. Missingness, exact duplicates, categorical inconsistency, and invalid numeric values use their applicable rule detectors; numerical anomalies are evaluated with the production IQR, modified robust-Z, and Isolation Forest implementations. Cell-level metrics are used for missingness/category/type defects and row-level metrics for duplicates/numerical anomalies. The runner records per-seed confusion counts, precision/recall/F1/accuracy, prediction runtime, and Python tracemalloc peak-allocation delta. It aggregates arithmetic means and sample standard deviations only when every requested seed completes. The CLI is backend/scripts/run_detector_benchmark.py. The runner is implemented but no benchmark results are claimed until it is executed against a documented clean reference dataset. The memory proxy does not capture every native allocation. Synthetic rates are controlled experimental settings and must not be interpreted as real-world defect prevalence.

## Methods

- Rule checks for missingness and exact duplicate rows.
- Inferred numeric type-drift checks: a column is treated as numeric-like only when at least 80% of non-missing values parse as finite numbers and at least two valid values exist.
- Categorical consistency checks for surrounding whitespace and case-only variants. Findings require review and are never silently normalized.
- Explicit schema/domain validation through a caller-supplied contract. Supported column types are string, integer, number, and boolean; contracts can specify required values, inclusive numeric bounds, allowed-value sets, case sensitivity, and whether undeclared columns are allowed. Missing expected columns, missing required cells, type mismatches, out-of-range values, disallowed values, and unexpected columns are reported with bounded row evidence. These findings are supplemental to the inference-based DQS in the current implementation.
- IQR anomaly flags are available through the read-only API using configurable Q1/Q3 fences (default multiplier 1.5).
- Modified robust Z-score flags use 0.67448975*(x - median)/MAD (default absolute threshold 3.5); zero-MAD columns are skipped and reported.
- Isolation Forest uses a caller-supplied contamination and random seed, median imputation, robust feature scaling, bounded per-tree samples, and a single worker. It requires at least ten rows with observed numeric values.
- Numeric candidates require at least four finite values and at least 80% finite parseability among non-missing values. These are implementation eligibility rules to evaluate, not universal data-quality standards.
- The current anomaly API returns bounded one-based row evidence and the source SHA-256 fingerprint. The dashboard now exposes detector selection, reproducible parameter controls, numeric eligibility diagnostics, per-detector findings, and evidence inspection. The UI currently scans all eligible numeric-like columns; API-level column filtering is not exposed. The workflow is read-only; anomaly flags are not incorporated into DQS and never delete records. Ground-truth detector evaluation remains outstanding.

Do not treat every unusual observation as a confirmed error. Compare only detectors applicable to each injected defect type. The current numeric type check does not infer business-specific minimum/maximum constraints.

## Data Quality Score

The implemented DQS has four components:
- Completeness: 30%; non-missing cells divided by all cells.
- Validity: 30%; finite, parseable values divided by non-missing values in inferred numeric-like columns.
- Uniqueness: 20%; rows excluding duplicate occurrences after the first divided by all rows.
- Consistency: 20%; categorical values without detected whitespace/case inconsistency divided by non-missing categorical values.

Each component is 0–100 with explicit numerator and denominator. A component with no assessable denominator is marked inapplicable; active weights are renormalized before calculating the weighted mean. The report exposes component applicability and active weight total. These weights are a design choice to be examined in sensitivity analysis, not a universal standard. Anomaly flags remain separate from the score. Explicit schema validation is reported independently and does not alter the DQS in this version.

Severity bands for rule findings are high at >=20% affected, medium at >=5% and <20%, and low below 5%. Evidence includes affected counts, denominators, and one-based data-row numbers (excluding the header).

The current anomaly endpoint is `POST /api/datasets/{id}/anomalies`. Record detector selection, IQR multiplier, modified-Z threshold, contamination, estimator count, random seed, numeric-column eligibility, and software versions for every evaluation run. Isolation Forest scores are anomaly rankings, not calibrated probabilities. Compare only detector/defect pairs for which the method is applicable.

## Cleaning and version provenance

The backend exposes advisory recommendations, a read-only preview, explicit apply, and version listing. Supported operations are exact duplicate removal (keep first), numeric median imputation, categorical mode imputation, whitespace trimming, and explicitly requested lower-case normalization. Recommendations never execute automatically. Preview returns bounded one-based row evidence and does not write a file. Apply creates a new generated CSV and immutable version record; the original upload and prior versions remain unchanged. Each version records its parent, operation manifest, row/column counts, file size, and SHA-256. A version may be used as the base for a subsequent version, preserving lineage.

Imputation is not universally safe: median can compress numeric variance, mode can overrepresent a category, and lower-case normalization can merge semantically distinct labels. These choices require review and must be described in experiment reports. A no-op operation is not persisted. The dashboard now supports selecting recommendations, choosing an original or derived base version, previewing bounded before/after row and cell changes, acknowledging the preview, explicitly applying operations, and reviewing immutable version lineage. When a derived version is selected, the API recalculates the original and derived CSV with the same DQS implementation and reports overall and component score deltas, applicability, issue/severity counts, shape changes, and source fingerprints. The dashboard displays these results and now also compares numeric summaries (min, max, mean, median, standard deviation, and quartiles), 10-bin histograms with shared per-column edges for columns numeric in both versions, and pairwise Pearson correlation deltas when both correlations are defined. The comparison is capped at the first 20 numeric columns; categorical frequency distributions are not compared. Histogram counts are directly comparable only when the response marks the bins as shared. These descriptive changes do not establish causality or downstream model improvement. A positive DQS delta means improvement only under the defined rule-based score; it is not evidence of improved predictive performance. If component applicability changes, the active-weight denominator also changes and must be considered. Full numeric distribution/correlation comparisons and live browser-to-FastAPI verification remain pending.

## Detector benchmark runner

The reproducible runner is `backend/app/services/dataset_benchmark.py`, with a local CSV CLI at `backend/scripts/run_detector_benchmark.py`. From the backend directory:

```powershell
python -m scripts.run_detector_benchmark reference.csv --rates 0.01,0.05,0.10 --seeds 42,123,2026 --output benchmark-report.json
```

The source CSV is read-only. The CLI records the source filename, SHA-256, byte size, shape, Python, pandas, NumPy, and scikit-learn versions. Before running, a clean-reference preflight rejects pre-existing missing cells, exact duplicate rows, detected categorical whitespace/case variants, and invalid values in inferred numeric-like columns. Statistical outliers are not rejected because unusual does not mean invalid; if a detector flags a baseline outlier, it counts as a false positive against injected-only labels. Each trial injects one defect into a fresh in-memory copy of the clean reference frame.

| Injected defect | Applicable detector | Evaluation unit |
|---|---|---|
| Missingness | Missing-value rule | Cell |
| Exact duplicates | Exact duplicate-row rule | Row |
| Categorical inconsistency | Whitespace/casefold-variant rule | Cell |
| Invalid numeric values | Finite numeric parseability rule using numeric columns inferred from the clean reference | Cell |
| Numerical anomalies | Production IQR, modified robust Z-score, and Isolation Forest | Row |

For every detector/rate pair, retain per-seed TP/FP/TN/FN, precision, recall, F1, accuracy, runtime, and Python tracemalloc peak-allocation delta. Runtime covers prediction only, excluding corruption generation and metric calculation. The memory value is a Python allocation proxy and does not fully include native NumPy/scikit-learn allocations. At least three distinct seeds are required. If any requested seed is skipped or incomplete for a detector, no aggregate is emitted for that detector/rate; the skipped reason remains in the report. Aggregates use arithmetic mean and sample standard deviation (ddof=1).

The numerical adapters deliberately reuse the same internal IQR, robust-Z, and Isolation Forest functions as the production anomaly endpoint. Rule-detector evaluation is controlled by the clean reference schema and should not be interpreted as an estimate of performance on unknown real-world schemas. The categorical rule may flag legitimate case variants. Duplicate metrics are row-level and mark inserted duplicate occurrences after the first. The runner is executed by the public UCI Wine GitHub Actions workflow; the uploaded report must be inspected before reporting detector performance.

## Public UCI Wine reference and downstream classification experiment

The first public reference workflow uses the Wine Recognition dataset (UCI Machine Learning Repository dataset 109). The scikit-learn loader provides 178 observations, 13 numeric predictors, and three classes. The experiment uses the bundled copy through `sklearn.datasets.load_wine(as_frame=True)`, so the CI job does not need a runtime dataset download. Provenance links:

- UCI dataset record: https://archive.ics.uci.edu/dataset/109/wine
- Original UCI data file: https://archive.ics.uci.edu/ml/machine-learning-databases/wine/wine.data
- scikit-learn loader documentation: https://scikit-learn.org/stable/modules/generated/sklearn.datasets.load_wine.html

A deterministic `alcohol_band` feature is derived from the original `alcohol` column with fixed edges at 12.0 and 13.0 and labels `low`, `medium`, and `high`. This is explicitly not an original UCI feature; it exists to make the categorical inconsistency detector applicable. The original target is excluded from detector benchmarking. The report records canonical frame hashes, target class counts, derived-feature rules, and software versions.

The detector benchmark runs at 1%, 5%, and 10% with seeds 42, 123, and 2026. All five defect types are requested; any ineligible detector or skipped seed remains visible and prevents an aggregate for that detector/rate. The UCI Wine frame has only one derived categorical feature, so categorical consistency results are based on that engineered column and must not be generalized to arbitrary categorical schemas.

The downstream classification experiment uses only the derived alcohol_band feature, deliberately excluding the source alcohol column and other predictors to prevent the model from bypassing the corrupted categorical representation. It uses a separate protocol:

1. Create a stratified 75/25 split from the untouched clean reference for each seed.
2. Infer feature types from the clean training partition only.
3. Inject 5%, 10%, and 20% categorical case/whitespace inconsistency in separate training-only runs; do not corrupt the target or test partition.
4. Compare three conditions on the same test rows within each seed: clean training, corrupted training, and cleaned-corrupted training.
5. The cleaned-corrupted condition applies the production whitespace-trim and lowercase operations to training categorical features only. Because those operations exactly reverse the injected case/whitespace variants, clean and cleaned-corrupted predictive metrics are expected to match and are asserted as a control.
6. Fit median imputation, scaling, and one-hot encoding inside a separate scikit-learn pipeline for each condition using that condition's training rows only.
7. Retain accuracy, balanced accuracy, macro precision/recall/F1, confusion matrices, runtime, per-seed test fingerprints, and mean/sample-standard-deviation aggregates.

The first downstream experiment is classification-only and uses the derived alcohol_band feature alone to isolate categorical inconsistency at 5%, 10%, and 20% corruption rates on one small public dataset. Its measured macro-F1 is unchanged across clean, corrupted, and cleaned-corrupted conditions in this experiment; see docs/RESEARCH_RESULTS.md. It does not yet cover regression or other training-only corruption types. A performance difference is descriptive evidence for this dataset, split protocol, corruption rate, and baseline; it is not a universal claim that cleaning always improves model quality.

The command is `python -m scripts.run_public_reference_experiments`. GitHub Actions workflow `.github/workflows/research-evaluation.yml` runs the full detector benchmark and downstream classification experiment and uploads the JSON report as `uci-wine-reference-experiment` for 30 days. The 14 November 2026 workflow artifact has been inspected; measured detector and downstream classification results, plus limitations, are recorded in docs/RESEARCH_RESULTS.md. Those results are specific to this small reference, derived feature, corruption protocol, and baseline and must not be generalized.

## Evaluation metrics

For defect detection: precision, recall, F1, confusion counts, and execution time. Record memory where feasible. For classification: F1 and appropriate complementary metrics. For regression: MAE and RMSE. Repeat stochastic experiments across seeds and report mean and standard deviation.

## ML-readiness diagnostics

The read-only endpoint `POST /api/datasets/{id}/ml-readiness` accepts a target column, task type, and optional feature-column selection. It reports target completeness; classification class counts, majority share, minority count, and imbalance ratio; regression target numeric parseability; feature missingness; duplicate feature vectors with the target excluded; near-exact target copies; near-perfect numeric target associations for regression; exact duplicate feature pairs; high Pearson-correlation feature pairs; and sample-size/dimensionality caveats. Numeric redundancy checks are capped at 20 eligible features. Thresholds are returned with the report, along with pandas, NumPy, and scikit-learn versions.

The diagnostics are deterministic heuristics, not proof of leakage or a guarantee that a dataset is model-ready. Exact target copies and very high associations require source/provenance review. Correlation can reflect a legitimate relationship. Duplicate feature vectors can create split contamination under random row splitting; group-aware splitting may be preferable. The diagnostic endpoint does not fit a model or modify data. A separate `POST /api/datasets/{id}/baseline-model` endpoint now fits a class-weighted logistic-regression classifier or Ridge regressor after a seeded holdout split. Feature-type inference, median/constant imputation, scaling, and one-hot encoding are fitted only on the training partition inside a scikit-learn Pipeline. The response records split parameters, train/test counts, preprocessing scope, source fingerprint, software versions, runtime, and task-appropriate holdout metrics. This is a single baseline holdout, not a tuned model or performance guarantee; dashboard integration, repeated-seed uncertainty estimates, and the controlled train-only corruption experiment remain outstanding.


## Baseline modeling protocol

The baseline endpoint is `POST /api/datasets/{id}/baseline-model`. It uses class-weighted logistic regression for classification and Ridge regression for regression. The default holdout is 25% with random seed 42; both are configurable. Classification uses stratified random splitting and requires at least two observations per class and enough rows to represent every class in both partitions. Regression excludes missing, non-numeric, and non-finite target labels before a seeded random split.

The split is performed before feature-type inference or preprocessing. Numeric-like feature inference uses only training rows (at least two finite observations and 80% finite parseability among non-missing values). Numeric median imputation and standard scaling, plus categorical constant imputation and one-hot encoding, are fitted inside the training pipeline. The test partition is transformed only by the fitted pipeline. Unknown test categories are ignored. Classification reports accuracy, balanced accuracy, macro precision/recall/F1, confusion counts, and binary ROC AUC when applicable. Regression reports MAE, RMSE, and R².

Every response records the source SHA-256, target rows excluded, selected features, inferred train-only feature types, split seed/fraction, train/test counts, preprocessing fit scope, runtime, and pandas/NumPy/scikit-learn versions. Models are not persisted. This baseline uses a random row split and does not prevent repeated entities or duplicate feature vectors from crossing partitions; the readiness diagnostics must be reviewed and group-aware splitting used where justified. A single holdout is not sufficient for comparative claims. Repeat experiments with at least three seeds and report mean and standard deviation. For the primary corruption experiment, split the clean reference first, corrupt training data only, and leave the test set untouched.

## Downstream model experiment

Split the clean reference data into training and test sets before corruption. Corrupt training data only for the primary experiment and keep the test set untouched. Fit imputation, scaling, encoding, and feature selection only on training data. Compare models trained on clean training data, corrupted training data, and cleaned corrupted training data using the same split and model configuration.

## Threats to validity

Synthetic defects may not represent real-world errors; detector performance depends on distributions and parameters; outlier methods can produce false positives; score weights are design choices; inferred numeric-like columns can misclassify identifiers or numeric-coded categories; categorical case variants may be legitimate; schema constraints may be incomplete or incorrect; cleaning can remove useful information or introduce bias; downstream results depend on model and split choices.

## Reproducibility checklist

- Record dataset provenance and preprocessing.
- Save corruption type, rate, seed, and exact ground-truth labels.
- Save detector parameters and software versions.
- Record train/test split seed and model hyperparameters.
- Report all evaluated runs, including negative results.
