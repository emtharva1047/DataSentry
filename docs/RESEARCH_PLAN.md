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

Imputation is not universally safe: median can compress numeric variance, mode can overrepresent a category, and lower-case normalization can merge semantically distinct labels. These choices require review and must be described in experiment reports. A no-op operation is not persisted. The dashboard now supports selecting recommendations, choosing an original or derived base version, previewing bounded before/after row and cell changes, acknowledging the preview, explicitly applying operations, and reviewing immutable version lineage. When a derived version is selected, the API recalculates the original and derived CSV with the same DQS implementation and reports overall and component score deltas, applicability, issue/severity counts, shape changes, and source fingerprints. The dashboard displays these results. A positive DQS delta means improvement only under the defined rule-based score; it is not evidence of improved predictive performance. If component applicability changes, the active-weight denominator also changes and must be considered. Full numeric distribution/correlation comparisons and live browser-to-FastAPI verification remain pending.

## Evaluation metrics

For defect detection: precision, recall, F1, confusion counts, and execution time. Record memory where feasible. For classification: F1 and appropriate complementary metrics. For regression: MAE and RMSE. Repeat stochastic experiments across seeds and report mean and standard deviation.

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
