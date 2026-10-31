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

- Rule checks for missingness, duplicates, and schema/domain constraints.
- Categorical normalization checks for whitespace/case variants.
- IQR and robust Z-score for univariate numerical outliers.
- Isolation Forest for multivariate anomaly flags, with preprocessing and contamination settings recorded.

Do not treat every unusual observation as a confirmed error. Compare only detectors applicable to each injected defect type.

## Evaluation metrics

For defect detection: precision, recall, F1, confusion counts, and execution time. Record memory where feasible. For classification: F1 and appropriate complementary metrics. For regression: MAE and RMSE. Repeat stochastic experiments across seeds and report mean and standard deviation.

## Downstream model experiment

Split the clean reference data into training and test sets before corruption. Corrupt training data only for the primary experiment and keep the test set untouched. Fit imputation, scaling, encoding, and feature selection only on training data. Compare models trained on clean training data, corrupted training data, and cleaned corrupted training data using the same split and model configuration.

## Data Quality Score proposal

Initial component weights:
- Completeness: 30%.
- Validity: 30%.
- Uniqueness: 20%.
- Consistency: 20%.

Each component is on a 0–100 scale with explicit denominator and applicability rules. If a dimension cannot be assessed, renormalize active weights and disclose this. Keep anomaly counts separate unless evidence supports including them.

## Threats to validity

Synthetic defects may not represent real-world errors; detector performance depends on distributions and parameters; outlier methods can produce false positives; score weights are design choices; cleaning can remove useful information or introduce bias; downstream results depend on model and split choices.

## Reproducibility checklist

- Record dataset provenance and preprocessing.
- Save corruption type, rate, seed, and exact ground-truth labels.
- Save detector parameters and software versions.
- Record train/test split seed and model hyperparameters.
- Report all evaluated runs, including negative results.
