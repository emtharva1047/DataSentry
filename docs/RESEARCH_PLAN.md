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
- **Categorical inconsistency:** the generator supports `combined` (surrounding whitespace plus swapped case), `whitespace_only`, and `case_only` (swap alphabetic case without whitespace). Pure case-only candidates that do not change under `swapcase()` are ineligible and are reported as skipped when none remain.
- **Invalid values:** replace selected finite values in inferred numeric-like columns with a collision-checked non-numeric sentinel.
- **Numerical anomalies:** replace selected finite numeric cells with a finite value above the original column maximum, where representable. Columns with insufficient numeric evidence or no representable higher finite value are skipped.

Numeric columns require at least four finite values and 80% finite parseability among non-missing values. Categorical candidates are non-numeric columns containing non-empty strings. Defect selections do not overlap at the same cell; duplicate source rows are not modified by cell corruptions. The input DataFrame is copied and never mutated. The returned frame is in memory only.

Ground-truth schema version 2 contains source/corrupted shapes, seed, rate, selected defects, categorical corruption mode, inferred eligible columns, per-defect status/count/records, cell labels, duplicate-row records, and grouped row labels. Every cell label has a zero-based row position in the returned corrupted frame, a one-based data-row number (CSV header excluded), a column name, and a defect type. Duplicate records additionally include both inserted and source row positions. These labels describe only defects injected by this generator; pre-existing defects in the reference frame are not labeled.

evaluate_binary_detector computes TP, FP, TN, FN, precision, recall, F1, and accuracy for equal-length non-empty binary sequences. Undefined precision, recall, or F1 uses zero and is explicitly reported. aggregate_seed_metrics requires at least three distinct unsigned seeds, identical metric names, and finite numeric values. It reports the arithmetic mean and sample standard deviation (ddof=1), retaining per-seed values. It does not silently drop failed or missing runs.

The generator is now connected to a defect-specific benchmark runner in backend/app/services/dataset_benchmark.py. Missingness, exact duplicates, categorical inconsistency, and invalid numeric values use their applicable rule detectors; numerical anomalies are evaluated with the production IQR, modified robust-Z, and Isolation Forest implementations. Cell-level metrics are used for missingness/category/type defects and row-level metrics for duplicates/numerical anomalies. The runner records per-seed confusion counts, precision/recall/F1/accuracy, prediction runtime, and Python tracemalloc peak-allocation delta. It aggregates arithmetic means and sample standard deviations only when every requested seed completes. The CLI is backend/scripts/run_detector_benchmark.py. The runner is implemented but no benchmark results are claimed until it is executed against a documented clean reference dataset. The memory proxy does not capture every native allocation. Synthetic rates are controlled experimental settings and must not be interpreted as real-world defect prevalence.

## Methods

- Rule checks for missingness and exact duplicate rows.
- Inferred numeric type-drift checks: a column is treated as numeric-like only when at least 80% of non-missing values parse as finite numbers and at least two valid values exist.
- Categorical consistency checks always flag surrounding whitespace and flag non-dominant case-only spellings only when a casefold-equivalent group has a unique most-frequent trimmed spelling. Tied groups remain ambiguous. Findings require review and are never silently normalized.
- Explicit schema/domain validation through a caller-supplied contract. Supported column types are string, integer, number, and boolean; contracts can specify required values, inclusive numeric bounds, allowed-value sets, case sensitivity, and whether undeclared columns are allowed. Missing expected columns, missing required cells, type mismatches, out-of-range values, disallowed values, and unexpected columns are reported with bounded row evidence. These findings are supplemental to the inference-based DQS in the current implementation.
- IQR anomaly flags are available through the read-only API using configurable Q1/Q3 fences (default multiplier 1.5).
- Modified robust Z-score flags use 0.67448975*(x - median)/MAD (default absolute threshold 3.5); zero-MAD columns are skipped and reported.
- Isolation Forest uses a caller-supplied contamination and random seed, median imputation, robust feature scaling, bounded per-tree samples, and a single worker. It requires at least ten rows with observed numeric values.
- Numeric candidates require at least four finite values and at least 80% finite parseability among non-missing values. These are implementation eligibility rules to evaluate, not universal data-quality standards.
- The current anomaly API returns bounded one-based row evidence and the source SHA-256 fingerprint. The dashboard now exposes detector selection, reproducible parameter controls, numeric eligibility diagnostics, per-detector findings, and evidence inspection. The UI currently scans all eligible numeric-like columns; API-level column filtering is not exposed. The workflow is read-only; anomaly flags are not incorporated into DQS and never delete records. The first UCI Wine ground-truth detector evaluation is documented in docs/RESEARCH_RESULTS.md; the UCI Bike Sharing mixed-type detector benchmark has also executed; subtler anomaly settings and additional references remain outstanding.

Do not treat every unusual observation as a confirmed error. Compare only detectors applicable to each injected defect type. The current numeric type check does not infer business-specific minimum/maximum constraints.

## Data Quality Score

The implemented DQS has four components:
- Completeness: 30%; non-missing cells divided by all cells.
- Validity: 30%; finite, parseable values divided by non-missing values in inferred numeric-like columns.
- Uniqueness: 20%; rows excluding duplicate occurrences after the first divided by all rows.
- Consistency: 20%; categorical values without detected surrounding whitespace or non-dominant case-only spellings divided by non-missing categorical values.

Each component is 0–100 with explicit numerator and denominator. A component with no assessable denominator is marked inapplicable; active weights are renormalized before calculating the weighted mean. The report exposes component applicability and active weight total. These weights are a design choice to be examined in sensitivity analysis, not a universal standard. Anomaly flags remain separate from the score. Explicit schema validation is reported independently and does not alter the DQS in this version.

Severity bands for rule findings are high at >=20% affected, medium at >=5% and <20%, and low below 5%. Evidence includes affected counts, denominators, and one-based data-row numbers (excluding the header).

The current anomaly endpoint is `POST /api/datasets/{id}/anomalies`. Record detector selection, IQR multiplier, modified-Z threshold, contamination, estimator count, random seed, numeric-column eligibility, and software versions for every evaluation run. Isolation Forest scores are anomaly rankings, not calibrated probabilities. Compare only detector/defect pairs for which the method is applicable.

## Cleaning and version provenance

The backend exposes advisory recommendations, a read-only preview, explicit apply, and version listing. Supported operations are exact duplicate removal (keep first), numeric median imputation, categorical mode imputation, whitespace trimming, and explicitly requested lower-case normalization. Recommendations never execute automatically. Preview returns bounded one-based row evidence and does not write a file. Apply creates a new generated CSV and immutable version record; the original upload and prior versions remain unchanged. Each version records its parent, operation manifest, row/column counts, file size, and SHA-256. A version may be used as the base for a subsequent version, preserving lineage.

Imputation is not universally safe: median can compress numeric variance, mode can overrepresent a category, and lower-case normalization can merge semantically distinct labels. These choices require review and must be described in experiment reports. A no-op operation is not persisted. The dashboard now supports selecting recommendations, choosing an original or derived base version, previewing bounded before/after row and cell changes, acknowledging the preview, explicitly applying operations, and reviewing immutable version lineage. When a derived version is selected, the API recalculates the original and derived CSV with the same DQS implementation and reports overall and component score deltas, applicability, issue/severity counts, shape changes, and source fingerprints. The dashboard displays these results and now also compares numeric summaries (min, max, mean, median, standard deviation, and quartiles), 10-bin histograms with shared per-column edges for columns numeric in both versions, and pairwise Pearson correlation deltas when both correlations are defined. The comparison is capped at the first 20 numeric columns; categorical frequency distributions are not compared. Histogram counts are directly comparable only when the response marks the bins as shared. These descriptive changes do not establish causality or downstream model improvement. A positive DQS delta means improvement only under the defined rule-based score; it is not evidence of improved predictive performance. If component applicability changes, the active-weight denominator also changes and must be considered. Numeric summary, shared-bin histogram, and Pearson correlation comparisons are implemented. Categorical frequency comparison remains pending; the live browser-to-FastAPI workflow passed in Playwright Chromium on 16 November 2026.

## Detector benchmark runner

The reproducible runner is `backend/app/services/dataset_benchmark.py`, with a local CSV CLI at `backend/scripts/run_detector_benchmark.py`. From the backend directory:

```powershell
python -m scripts.run_detector_benchmark reference.csv --rates 0.01,0.05,0.10 --seeds 42,123,2026 --output benchmark-report.json
```

The source CSV is read-only. The CLI records the source filename, SHA-256, byte size, shape, Python, pandas, NumPy, and scikit-learn versions. Before running, a clean-reference preflight rejects pre-existing missing cells, exact duplicate rows, detected categorical whitespace or non-dominant case-only variants, and invalid values in inferred numeric-like columns. Statistical outliers are not rejected because unusual does not mean invalid; if a detector flags a baseline outlier, it counts as a false positive against injected-only labels. Each trial injects one defect into a fresh in-memory copy of the clean reference frame.

| Injected defect | Applicable detector | Evaluation unit |
|---|---|---|
| Missingness | Missing-value rule | Cell |
| Exact duplicates | Exact duplicate-row rule | Row |
| Categorical inconsistency | Whitespace/casefold-variant rule | Cell |
| Invalid numeric values | Finite numeric parseability rule using numeric columns inferred from the clean reference | Cell |
| Numerical anomalies | Production IQR, modified robust Z-score, and Isolation Forest | Row |

For every detector/rate pair, retain per-seed TP/FP/TN/FN, precision, recall, F1, accuracy, runtime, and Python tracemalloc peak-allocation delta. Runtime covers prediction only, excluding corruption generation and metric calculation. The memory value is a Python allocation proxy and does not fully include native NumPy/scikit-learn allocations. At least three distinct seeds are required. If any requested seed is skipped or incomplete for a detector, no aggregate is emitted for that detector/rate; the skipped reason remains in the report. Aggregates use arithmetic mean and sample standard deviation (ddof=1).

The numerical adapters deliberately reuse the same internal IQR, robust-Z, and Isolation Forest functions as the production anomaly endpoint. Rule-detector evaluation is controlled by the clean reference schema and should not be interpreted as an estimate of performance on unknown real-world schemas. The categorical rule may flag legitimate case variants. Duplicate metrics are row-level and mark inserted duplicate occurrences after the first. The public UCI Wine GitHub Actions workflow has executed and its report has been inspected; measured results and limitations are recorded in docs/RESEARCH_RESULTS.md.

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

The first downstream experiment is classification-only and uses the derived alcohol_band feature alone to isolate categorical inconsistency at 5%, 10%, and 20% corruption rates on one small public dataset. Its measured macro-F1 is unchanged across clean, corrupted, and cleaned-corrupted conditions in this experiment; see docs/RESEARCH_RESULTS.md. This Wine-specific experiment does not cover regression or other training-only corruption types; the separate Bike Sharing downstream regression experiment is documented below. A performance difference is descriptive evidence for this dataset, split protocol, corruption rate, and baseline; it is not a universal claim that cleaning always improves model quality.

The command is `python -m scripts.run_public_reference_experiments`. GitHub Actions workflow `.github/workflows/research-evaluation.yml` runs the full detector benchmark and downstream classification experiment and uploads the JSON report as `uci-wine-reference-experiment` for 30 days. The 14 November 2026 workflow artifact has been inspected; measured detector and downstream classification results, plus limitations, are recorded in docs/RESEARCH_RESULTS.md. Those results are specific to this small reference, derived feature, corruption protocol, and baseline and must not be generalized.

## Evaluation metrics

For defect detection: precision, recall, F1, confusion counts, and execution time. Record memory where feasible. For classification: F1 and appropriate complementary metrics. For regression: MAE and RMSE. Repeat stochastic experiments across seeds and report mean and standard deviation.

## ML-readiness diagnostics

The read-only endpoint `POST /api/datasets/{id}/ml-readiness` accepts a target column, task type, and optional feature-column selection. It reports target completeness; classification class counts, majority share, minority count, and imbalance ratio; regression target numeric parseability; feature missingness; duplicate feature vectors with the target excluded; near-exact target copies; near-perfect numeric target associations for regression; exact duplicate feature pairs; high Pearson-correlation feature pairs; and sample-size/dimensionality caveats. Numeric redundancy checks are capped at 20 eligible features. Thresholds are returned with the report, along with pandas, NumPy, and scikit-learn versions.

The diagnostics are deterministic heuristics, not proof of leakage or a guarantee that a dataset is model-ready. Exact target copies and very high associations require source/provenance review. Correlation can reflect a legitimate relationship. Duplicate feature vectors can create split contamination under random row splitting; group-aware splitting may be preferable. The diagnostic endpoint does not fit a model or modify data. A separate `POST /api/datasets/{id}/baseline-model` endpoint now fits a class-weighted logistic-regression classifier or Ridge regressor after a seeded holdout split. Feature-type inference, median/constant imputation, scaling, and one-hot encoding are fitted only on the training partition inside a scikit-learn Pipeline. The response records split parameters, train/test counts, preprocessing scope, source fingerprint, software versions, runtime, and task-appropriate holdout metrics. This is a single baseline holdout, not a tuned model or performance guarantee; dashboard integration is implemented; repeated-seed baseline uncertainty estimates and broader controlled train-only corruption experiments remain outstanding.


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


## Dashboard integration (15 November 2026)

The Next.js ML workspace loads the dataset profile to populate target and feature selection, then calls the existing `POST /api/datasets/{id}/ml-readiness` endpoint. It displays readiness status, target completeness, class distribution when applicable, duplicate split risk, leakage indicators, redundancy count, and warnings/blockers. Baseline execution is enabled only after a readiness report without blockers and calls `POST /api/datasets/{id}/baseline-model` with the selected target/features, holdout fraction, and random seed. It renders classification or regression metrics, the classification confusion matrix, train/test counts, preprocessing fit scope, source fingerprint, and software versions. The workspace does not persist models or modify the uploaded CSV.

The integration has frontend lint/type/build CI coverage and was exercised in Chromium against a real FastAPI/SQLite process on 16 November 2026. The smoke test completed upload, quality/schema/anomaly checks, cleaning preview/apply, immutable version comparison, readiness, and both baseline tasks.


## Application integration verification

A Playwright browser smoke test complements isolated backend tests. It runs a production Next.js build and a real FastAPI process with an isolated SQLite/upload/version root, then verifies browser upload, profile/quality, explicit schema validation, anomaly review, read-only cleaning preview, immutable apply, version DQS comparison, ML-readiness diagnostics, and classification/regression baseline requests. It asserts that the original upload SHA-256 remains unchanged and that both baseline tasks report preprocessing fitted only on training rows. This is application integration evidence, not an additional detector-performance experiment; no research metric is derived from the smoke test.


## Mixed-type UCI Bike Sharing downstream regression protocol

The second public reference is the hourly Bike Sharing dataset (UCI dataset 275; DOI 10.24432/C5W894; CC BY 4.0): https://archive.ics.uci.edu/dataset/275/bike+sharing+dataset. The runner downloads the official ZIP archive, reads only hour.csv without extracting files, records archive and CSV SHA-256 values, validates required fields, requires finite values and no missing cells in the analysis columns, verifies cnt equals casual plus registered, and sorts by the unique instant identifier.

The regression target is cnt. The direct target components casual and registered are excluded as predictors to prevent target leakage. instant is used only to order rows; dteday is used only to derive day_index (integer days since the first date). The model uses eight categorical calendar/weather codes (season, yr, mnth, hr, holiday, weekday, workingday, weathersit) and five numeric features (temp, atemp, hum, windspeed, day_index). The categorical declarations are explicit rather than inferred from integer-coded values.

The experiment uses an ordered chronological 75/25 holdout: the earliest 75% of records are training and the latest 25% are the future test partition. Seeds 42, 123, and 2026 change only the training missingness selection; the split and clean future test fingerprint remain identical across seeds and corruption rates. Missingness is injected into training features only at 1%, 5%, and 10%. Each rate compares (1) clean training, (2) corrupted training, and (3) corrupted training after the production median numeric / mode categorical cleaning transform. A Ridge regression pipeline fits imputation, scaling, and encoding on each training condition only. The future test rows and targets are never passed to corruption or cleaning.

Report MAE, RMSE, R², fit runtime, per-seed results, paired cleaned-minus-corrupted deltas, mean, and sample standard deviation (ddof=1). This is a single chronological holdout and a fixed Ridge alpha, not rolling-origin cross-validation or tuned model selection. The three seeds are repeated corruption realizations, not independent temporal test periods. Results must be interpreted as dataset- and split-specific.


## Mixed-type UCI Bike Sharing detector benchmark

The detector benchmark reuses the hourly UCI Bike Sharing reference (dataset 275, DOI 10.24432/C5W894, CC BY 4.0) already used for downstream regression. It excludes the target `cnt` and its direct components `casual` and `registered`. The detector input contains the eight calendar/weather categorical predictors and five continuous predictors; `instant` and `dteday` remain excluded as predictors.

The source represents categorical fields as integer codes. Before detector evaluation, the adapter maps these codes to explicit semantic labels: seasons, years, month names, hour labels, holiday state, weekdays, working-day state, and weather descriptions. This is necessary because the shared synthetic corruption utility infers numeric-like columns from finite parseability; leaving integer codes unchanged would incorrectly make the categorical fields ineligible for categorical inconsistency injection. The adapter validates every code against a documented mapping and records the mapping plus a SHA-256 fingerprint of the transformed detector frame.

The benchmark uses the shared `run_synthetic_detector_benchmark` implementation and therefore retains its clean-reference preflight, exact injected labels, detector-specific evaluation units, production detector adapters, per-seed confusion counts, precision/recall/F1/accuracy, full prediction runtime, Python tracemalloc peak-allocation proxy, and all-or-nothing seed aggregation. Configuration: corruption rates 1%, 5%, and 10%; seeds 42, 123, and 2026; Isolation Forest 100 estimators with contamination 0.05; IQR multiplier 1.5; modified robust-Z threshold 3.5. The workflow publishes the complete JSON report as a 30-day GitHub Actions artifact.

The expected detector set is one missingness rule, one exact-duplicate rule, one categorical-consistency rule, one numeric-parseability rule, and three numerical anomaly detectors (IQR, robust Z-score, Isolation Forest). Cell-level metrics apply to missingness, categorical inconsistency, and invalid values; row-level metrics apply to duplicate occurrences and numerical anomaly flags. The clean-reference preflight rejects deterministic defects but deliberately retains statistical outliers. The quality-version-2 categorical heuristic selects a unique most-frequent trimmed spelling as canonical and flags less-frequent case-only variants; tied groups remain ambiguous. A legitimate minority spelling can still be flagged, and a genuine error may remain unflagged when counts are tied. The benchmark is controlled synthetic evidence for one reference and must not be generalized as real-world detector performance. The workflow completed successfully on 18 November 2026; measured results, per-seed aggregates, artifact provenance, and limitations are recorded in docs/RESEARCH_RESULTS.md.


## Isolation Forest contamination-sensitivity protocol (19 November 2026)

The UCI Bike Sharing detector reference is reused with its eight semantic categorical fields and five numeric predictors; target components remain excluded. For each numerical-anomaly corruption rate (1%, 5%, 10%) and seed (42, 123, 2026), a fresh corrupted copy is generated once and evaluated under Isolation Forest contamination values 0.01, 0.05, and 0.10. The same clean reference, corruption rate, and seed are held constant across contamination settings; only the Isolation Forest threshold parameter changes.

The runner reports, for each seed, TP/FP/TN/FN, precision, recall, F1, accuracy, runtime, Python-traced peak allocation, ground-truth positive-row count/prevalence, and predicted-positive-row count/prevalence. Ground-truth row prevalence is calculated as TP+FN divided by the full reference row count. Predicted row prevalence is TP+FP divided by the full row count. This explicitly distinguishes a cell-level injection rate from the row-level prevalence that Isolation Forest contamination approximates.

IQR and robust Z-score are repeated under every contamination setting as negative controls. Their confusion counts and precision/recall/F1/accuracy must remain identical across contamination settings because their production algorithms do not consume the Isolation Forest parameter. The workflow fails if any requested detector/seed run is skipped or incomplete, or if control invariance fails. Aggregates use the existing arithmetic mean and sample standard deviation (ddof=1) helper and retain per-seed values. The output is a reproducible JSON artifact; no corrupted source file is persisted.

The sweep is a parameter-sensitivity experiment, not automatic contamination calibration. The best threshold may be dataset- and corruption-specific; no universal optimal contamination value is inferred. The benchmark's extreme synthetic anomalies and Python tracemalloc memory proxy retain their previously documented limitations.


## Isolation Forest contamination sensitivity — execution outcome (19 November 2026)

The protocol above was executed successfully on the UCI Bike Sharing detector frame. The run evaluated contamination values 0.01, 0.05, and 0.10 against cell corruption rates 1%, 5%, and 10%, with seeds 42, 123, and 2026. It completed 27 Isolation Forest seed runs and 54 IQR/Robust-Z control seed runs without skips. All six control groups passed confusion-count and quality-metric invariance checks.

The artifact was downloaded and inspected before measured results were committed to docs/RESEARCH_RESULTS.md. The observed row-level anomaly prevalence was 4.8833%, 22.5789%, and 40.8405%, demonstrating why a cell-level injection rate cannot be treated as row-level anomaly prevalence. At 1% cell corruption, 0.05 contamination gave the best F1 among the tested settings (0.9882). At 5% and 10%, 0.10 gave the best tested F1 (0.6138 and 0.3934), but recall remained limited (0.4428 and 0.2449). No universal or production contamination setting is inferred. See the research results for the complete per-seed metrics, confusion counts, runtime, memory proxy, artifact hashes, and limitations.


## Categorical consistency quality version 2 (19 November 2026)

The initial casefold rule flagged every member of a group whose trimmed values shared the same casefolded representation. This produced low precision on UCI Bike Sharing because legitimate original spellings were counted as false positives. The revised rule treats a uniquely most-frequent trimmed spelling as the observed canonical spelling and flags only less-frequent variants. If multiple spellings tie for the highest count, the group remains ambiguous and no case-only spelling is flagged. Surrounding whitespace is always flagged independently. The benchmark imports the same production analysis helper to avoid implementation drift.

This is intentionally a conservative heuristic, not schema inference. A legitimate minority spelling can still be flagged, and a genuine case inconsistency can be missed when the counts tie. The detector remains read-only and requires human review. Quality response version is incremented to 2 because the consistency component's semantics changed. The UCI Wine Research Evaluation (run 44444316810) and UCI Bike Sharing Detector Research (run 44444316802) were rerun on 19 November 2026 using quality version 2. All 18 categorical rate/seed runs completed with precision/recall/F1 = 1.0 on both references. The synthetic categorical defect combines whitespace and swapped case, so pure case-only performance remains a separate evaluation gap. Measured values, artifacts, and limitations are in docs/RESEARCH_RESULTS.md.


The quality-version-2 public re-benchmark does not isolate case-only changes because the current corruption generator injects whitespace and swapped case together. It verifies that canonical members are no longer flagged as false positives for the combined defect. A future generator revision should include separately labeled whitespace-only, case-only, and combined modes so detector performance can be attributed to each sub-type without conflating them.


## Pure case-only categorical benchmark

The categorical corruption generator now separates three modes: `combined` (the historical whitespace-plus-case transform), `whitespace_only`, and `case_only`. The pure case-only mode swaps alphabetic case without adding or trimming whitespace; candidates whose value is unchanged by `swapcase()` are excluded from the eligible set. Ground-truth schema version 2 records the mode so benchmark reports cannot conflate the subtypes.

The dedicated CLI is `backend/scripts/run_case_only_categorical_benchmark.py`. It evaluates the production quality-v2 canonical-spelling rule on UCI Wine's derived `alcohol_band` and the semantically mapped UCI Bike Sharing categorical predictors, at 1%, 5%, and 10% over seeds 42, 123, and 2026. The clean-reference preflight remains active. These controlled results evaluate only the injected case-only variants and do not establish performance on unknown business schemas; the modal-spelling heuristic can still flag legitimate minority spellings and leaves tied groups ambiguous.


### Pure case-only public-reference benchmark (20 November 2026)

The dedicated `run_case_only_public_reference_benchmark` evaluates the production quality-v2 canonical-spelling rule with the generator's `case_only` mode. It runs UCI Wine and semantically mapped UCI Bike Sharing at rates 0.01/0.05/0.10 with seeds 42/123/2026. Pure case-only injection swaps alphabetic case and adds no whitespace. Ground-truth schema v2 records the categorical mode. The workflow completed all 18 reference/rate/seed runs without skips; measured results and artifact provenance are recorded in docs/RESEARCH_RESULTS.md. The F1=1.0 result is limited to the controlled generator and these two clean references and must not be generalized to real-world category drift.


## UCI Bike Sharing downstream duplicate-row regression protocol (21 November 2026)

The existing chronological Bike Sharing regression experiment is extended with an exact duplicate-row training condition alongside training-feature missingness. For each seed, split the clean reference chronologically first. Construct a combined training frame containing all 13 selected predictors and the cnt target, then call the shared synthetic corruption utility with the duplicates defect. This duplicates complete feature/target pairs; duplicating only predictors is prohibited because it would misalign labels. Duplicate insertion rate is the fraction of eligible source training rows, rounded up according to the shared generator contract.

Compare three conditions on the same future test partition: (1) clean training, (2) training with appended exact feature/target duplicates, and (3) the corrupted training frame after DataSentry's production drop-exact-duplicates transform. The production transform must restore the original training feature/target pairs and row count exactly. The test partition is not supplied to corruption or cleaning, and its SHA-256 fingerprint must remain identical across all seeds and rates.

Configuration: UCI Bike Sharing hourly dataset 275; target cnt; exclude casual and registered as direct target components; exclude instant as an identifier; derive day_index from dteday; eight semantic categorical and five numeric predictors; chronological 75/25 holdout; Ridge alpha 1.0; rates 1%, 5%, 10%; seeds 42, 123, 2026. Report per-seed injected duplicate rows, source-row lineage, training row counts before/after corruption and cleaning, exact ground-truth hash, clean/corrupted/cleaned MAE/RMSE/R2, fit runtime, paired cleaned-minus-corrupted deltas, means, and sample standard deviations (ddof=1).

This experiment tests the effect of duplicated observations as increased training weight. It does not claim that exact duplicate removal is always appropriate: repeated rows may represent legitimate repeated events in other datasets. The clean reference itself must pass the exact-duplicate preflight. The model uses a single chronological holdout and fixed Ridge alpha; it is not rolling-origin validation or a tuned model. The future test partition and its targets remain untouched.
