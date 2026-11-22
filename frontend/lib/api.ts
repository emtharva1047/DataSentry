export type Overview = {
  api: string;
  database: string;
  database_engine: string;
  dataset_count: number;
};

export type Dataset = {
  id: number;
  filename: string;
  rows_count: number;
  columns_count: number;
  file_size_bytes: number;
  sha256_hash: string | null;
  encoding: string;
  created_at: string;
};

export type QualityComponent = {
  score: number | null;
  weight: number;
  applicable: boolean;
  numerator: number;
  denominator: number;
  basis: string;
};

export type QualityIssue = {
  code: string;
  scope: string;
  column: string | null;
  severity: "high" | "medium" | "low";
  affected_count: number;
  denominator: number;
  affected_pct: number;
  message: string;
  evidence: Record<string, unknown>;
};

export type QualityReport = {
  dataset_id: number;
  filename: string;
  quality_version: number;
  generated_at: string;
  shape: { rows: number; columns: number };
  issue_count: number;
  issues_by_severity: { high: number; medium: number; low: number };
  issues: QualityIssue[];
  data_quality_score: {
    overall: number | null;
    scale: string;
    active_weight_total: number;
    weighting: string;
    components: {
      completeness: QualityComponent;
      validity: QualityComponent;
      uniqueness: QualityComponent;
      consistency: QualityComponent;
    };
  };
  method_notes: string[];
};


export type AnomalyDetectorName = "iqr" | "robust_zscore" | "isolation_forest";

export type AnomalyDetectionRequest = {
  detectors: AnomalyDetectorName[];
  iqr_multiplier: number;
  robust_z_threshold: number;
  contamination: number;
  random_state: number;
  n_estimators: number;
  max_evidence_rows: number;
};

export type AnomalyNumericColumn = {
  column: string;
  eligible: boolean;
  valid_count: number;
  non_missing_count: number;
  parse_failure_count: number;
  finite_parseability_pct: number;
  reason: string | null;
};

export type AnomalyEvidence = {
  row_number: number;
  value?: number | null;
  distance_beyond_fence?: number | null;
  modified_z_score?: number | null;
  anomaly_score?: number | null;
};

export type AnomalyColumnResult = {
  column: string;
  status: "completed" | "skipped";
  reason?: string;
  valid_count?: number;
  q1?: number | null;
  q3?: number | null;
  iqr?: number | null;
  lower_fence?: number | null;
  upper_fence?: number | null;
  median?: number | null;
  mad?: number | null;
  flagged_count: number;
  flagged_row_numbers: number[];
  flagged_row_numbers_truncated?: boolean;
  evidence?: AnomalyEvidence[];
  evidence_truncated?: boolean;
};

export type AnomalyDetectorResult = {
  status: "completed" | "skipped";
  reason?: string;
  parameters?: Record<string, number | string | null>;
  columns?: AnomalyColumnResult[];
  flagged_row_count?: number;
  flagged_count?: number;
  flagged_row_numbers?: number[];
  flagged_row_numbers_truncated?: boolean;
  feature_columns?: string[];
  rows_scored?: number;
  evidence?: AnomalyEvidence[];
  evidence_truncated?: boolean;
};

export type AnomalyReport = {
  dataset_id: number;
  filename: string;
  anomaly_detection_version: number;
  generated_at: string;
  source_sha256: string | null;
  shape: { rows: number; columns: number };
  numeric_columns: AnomalyNumericColumn[];
  parameters: AnomalyDetectionRequest;
  detectors: Partial<Record<AnomalyDetectorName, AnomalyDetectorResult>>;
  summary: {
    flagged_row_count: number;
    flagged_row_numbers: number[];
    evidence_truncated: boolean;
    flagged_count_by_detector: Partial<Record<AnomalyDetectorName, number>>;
  };
  method_notes: string[];
};



export type DatasetProfileColumn = {
  name: string;
  inferred_type: string;
  non_null_count: number;
  missing_count: number;
  missing_pct: number;
  unique_count: number;
  sample_values: string[];
  numeric_summary?: Record<string, number | null> | null;
  histogram?: Array<{ bin_start: number | null; bin_end: number | null; count: number }>;
  top_values?: Array<{ value: string; count: number }>;
  other_count?: number;
};

export type DatasetProfile = {
  dataset_id: number;
  filename: string;
  source_sha256: string | null;
  shape: { rows: number; columns: number };
  columns: DatasetProfileColumn[];
};

export type MLTaskType = "classification" | "regression";

export type MLReadinessRequest = {
  target_column: string;
  task_type: MLTaskType;
  feature_columns: string[];
};

export type MLReadinessFinding = {
  code: string;
  message: string;
  severity: "high" | "medium" | "low";
};

export type MLReadinessReport = {
  dataset_id: number;
  filename: string;
  source_sha256: string | null;
  generated_at: string;
  shape: { rows: number; columns: number };
  readiness_status: "blocked" | "review_required" | "ready_for_baseline";
  target: {
    column: string;
    task_type: MLTaskType;
    row_count: number;
    observed_count: number;
    missing_count: number;
    completeness_pct: number;
    class_count?: number;
    class_distribution?: Array<{ label: string; count: number; percentage: number }>;
    class_distribution_truncated?: boolean;
    majority_class_share_pct?: number;
    minority_class_count?: number;
    majority_to_minority_ratio?: number | null;
    numeric_parseable_count?: number;
    non_numeric_or_non_finite_count?: number;
    numeric_completeness_pct?: number;
  };
  selected_features: string[];
  feature_missingness: Array<{ column: string; missing_count: number; missing_pct: number }>;
  duplicate_split_risk: {
    duplicate_rows_after_first: number;
    duplicate_groups: number;
    duplicate_rate_pct: number;
    row_numbers: number[];
    row_numbers_truncated: boolean;
    definition: string;
  };
  leakage_indicators: Array<{
    feature: string;
    kind: string;
    agreement_pct?: number;
    coverage_pct?: number;
    absolute_pearson_correlation?: number;
    compared_rows: number;
    review_required: boolean;
  }>;
  feature_redundancy: {
    exact_duplicate_feature_pairs: Array<Record<string, unknown>>;
    high_correlation_pairs: Array<Record<string, unknown>>;
    reported_pair_count: number;
    numeric_columns_assessed: string[];
    numeric_columns_truncated: boolean;
    pairs_truncated: boolean;
  };
  dataset_size: {
    rows: number;
    feature_count: number;
    rows_per_feature: number | null;
    category: string;
    minimum_row_guidance: number;
  };
  warnings: MLReadinessFinding[];
  blockers: MLReadinessFinding[];
  model_training_performed: false;
  baseline_models: { status: string; note: string };
  parameters: Record<string, number>;
  software_versions: Record<string, string>;
  method_notes: string[];
};

export type BaselineModelRequest = {
  target_column: string;
  task_type: MLTaskType;
  feature_columns: string[];
  test_size: number;
  random_state: number;
};

export type BaselineModelReport = {
  dataset_id: number;
  filename: string;
  source_sha256: string;
  generated_at: string;
  task_type: MLTaskType;
  model: "logistic_regression" | "ridge_regression";
  model_training_performed: true;
  target: { column: string; eligible_rows: number; excluded_rows: number };
  features: {
    selected_columns: string[];
    numeric_columns_inferred_from_training: string[];
    categorical_columns_inferred_from_training: string[];
    numeric_parseability_threshold: number;
    max_categories_per_feature: number;
  };
  split: {
    strategy: string;
    random_state: number;
    test_size: number;
    train_rows: number;
    test_rows: number;
  };
  preprocessing: {
    fit_scope: string;
    fit_rows: number;
    test_partition_used_to_fit_preprocessing: false;
    numeric: string;
    categorical: string;
  };
  model_parameters: Record<string, number | string>;
  metrics: {
    accuracy?: number;
    balanced_accuracy?: number;
    macro_precision?: number;
    macro_recall?: number;
    macro_f1?: number;
    confusion_matrix?: { labels: string[]; counts: number[][] };
    roc_auc?: number | null;
    roc_auc_positive_class?: string | null;
    mae?: number;
    rmse?: number;
    r2?: number;
  };
  duration_seconds: number;
  software_versions: Record<string, string>;
  method_notes: string[];
};

const API_BASE_URL = (
  process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://127.0.0.1:8000"
).replace(/\/+$/, "");

export const API_DOCS_URL = `${API_BASE_URL}/docs`;

async function readResponse<T>(response: Response): Promise<T> {
  const payload: unknown = await response.json().catch(() => null);

  if (!response.ok) {
    let message = `Request failed with HTTP ${response.status}.`;
    if (
      payload &&
      typeof payload === "object" &&
      "detail" in payload &&
      typeof payload.detail === "string"
    ) {
      message = payload.detail;
    }
    throw new Error(message);
  }

  return payload as T;
}

export async function getOverview(): Promise<Overview> {
  const response = await fetch(`${API_BASE_URL}/api/overview`, {
    cache: "no-store",
  });
  return readResponse<Overview>(response);
}

export async function getDatasets(): Promise<Dataset[]> {
  const response = await fetch(`${API_BASE_URL}/api/datasets`, {
    cache: "no-store",
  });
  return readResponse<Dataset[]>(response);
}

export async function getDatasetQuality(datasetId: number): Promise<QualityReport> {
  const response = await fetch(`${API_BASE_URL}/api/datasets/${datasetId}/quality`, {
    cache: "no-store",
  });
  return readResponse<QualityReport>(response);
}

export async function getDatasetAnomalies(
  datasetId: number,
  request: AnomalyDetectionRequest,
): Promise<AnomalyReport> {
  const response = await fetch(`${API_BASE_URL}/api/datasets/${datasetId}/anomalies`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(request),
    cache: "no-store",
  });
  return readResponse<AnomalyReport>(response);
}



export type QualityComparisonComponentName =
  | "completeness"
  | "validity"
  | "uniqueness"
  | "consistency";

export type NumericProfileSummary = {
  min: number | null;
  max: number | null;
  mean: number | null;
  median: number | null;
  std: number | null;
  q1: number | null;
  q3: number | null;
};

export type ProfileHistogramBin = {
  bin_start: number | null;
  bin_end: number | null;
  count: number;
};

export type NumericProfileComparisonColumn = {
  column: string;
  status: "comparable" | "not_comparable";
  before_summary: NumericProfileSummary | null;
  after_summary: NumericProfileSummary | null;
  summary_deltas: NumericProfileSummary;
  before_histogram: ProfileHistogramBin[];
  after_histogram: ProfileHistogramBin[];
  histogram_bins_comparable: boolean;
};

export type CorrelationComparisonPair = {
  left_column: string;
  right_column: string;
  before: number;
  after: number;
  delta: number;
};

export type NumericProfileComparison = {
  numeric_column_count_before: number;
  numeric_column_count_after: number;
  numeric_columns_truncated: boolean;
  numeric_columns: NumericProfileComparisonColumn[];
  correlations: {
    method: "pearson";
    before_column_count: number;
    after_column_count: number;
    comparable_pair_count: number;
    skipped_pair_count: number;
    pairs: CorrelationComparisonPair[];
  };
  method_notes: string[];
};

export type QualityVersionComparison = {
  dataset_id: number;
  filename: string;
  compared_at: string;
  before: {
    source_version_id: number | null;
    version_number: number | null;
    source_sha256: string | null;
    shape: { rows: number; columns: number };
    overall: number | null;
    active_weight_total: number;
    components: Record<QualityComparisonComponentName, QualityComponent>;
    issue_count: number;
    issues_by_severity: { high: number; medium: number; low: number };
  };
  after: {
    source_version_id: number | null;
    version_number: number | null;
    source_sha256: string | null;
    shape: { rows: number; columns: number };
    overall: number | null;
    active_weight_total: number;
    components: Record<QualityComparisonComponentName, QualityComponent>;
    issue_count: number;
    issues_by_severity: { high: number; medium: number; low: number };
  };
  delta: {
    overall: number | null;
    rows: number;
    columns: number;
    issue_count: number;
    issues_by_severity: { high: number; medium: number; low: number };
    components: Record<
      QualityComparisonComponentName,
      {
        score_delta: number | null;
        numerator_delta: number;
        denominator_delta: number;
        applicable_before: boolean;
        applicable_after: boolean;
      }
    >;
  };
  profile_comparison: NumericProfileComparison;
  method_notes: string[];
};

export type CleaningOperationName =
  | "drop_exact_duplicates"
  | "fill_numeric_median"
  | "fill_categorical_mode"
  | "trim_whitespace"
  | "lowercase_categories";

export type CleaningRecommendation = {
  operation: CleaningOperationName;
  column?: string;
  recommended: boolean;
  affected_count: number;
  risk: "low" | "medium" | "high";
  reason: string;
};

export type CleaningRequest = {
  base_version_id: number | null;
  drop_exact_duplicates: boolean;
  fill_numeric_median: string[];
  fill_categorical_mode: string[];
  trim_whitespace: string[];
  lowercase_categories: string[];
};

export type CleaningOperationSummary = {
  operation: CleaningOperationName;
  columns?: string[];
  affected_cells?: number;
  affected_rows?: number;
  imputation_value?: string;
  missing_cells_filled?: number;
  invalid_cells_coerced_to_missing?: number;
  review_required?: boolean;
  comparison?: string;
};

export type CleaningPreviewChange = {
  column: string;
  before: string | null;
  after: string | null;
  operations: string[];
};

export type CleaningPreviewRow = {
  row_number: number;
  removed: boolean;
  changes: CleaningPreviewChange[];
};

export type CleaningPreview = {
  dataset_id: number;
  filename: string;
  base_version_id: number | null;
  source_sha256: string | null;
  previewed_at: string;
  changed: boolean;
  rows_before: number;
  rows_after: number;
  columns: number;
  preview: {
    changed_row_count: number;
    removed_row_count: number;
    sample_rows: CleaningPreviewRow[];
    sample_truncated: boolean;
    operations: CleaningOperationSummary[];
  };
  method_notes: string[];
};

export type DatasetVersion = {
  id: number;
  dataset_id: number;
  parent_version_id: number | null;
  version_number: number;
  filename: string;
  rows_count: number;
  columns_count: number;
  file_size_bytes: number;
  sha256_hash: string;
  operations: Record<string, unknown>;
  created_at: string | null;
};

export type CleaningApplyResult = {
  dataset_id: number;
  filename: string;
  version: {
    id: number;
    version_number: number;
    parent_version_id: number | null;
    rows_count: number;
    columns_count: number;
    file_size_bytes: number;
    sha256_hash: string;
    created_at: string | null;
  };
  base_sha256: string | null;
  preview: CleaningPreview["preview"];
  source_preserved: boolean;
  method_notes: string[];
};

export type CleaningRecommendations = {
  dataset_id: number;
  filename: string;
  base_version_id: number | null;
  source_sha256: string | null;
  shape: { rows: number; columns: number };
  recommendation_count: number;
  recommendations: CleaningRecommendation[];
  method_notes: string[];
};

export async function getCleaningRecommendations(
  datasetId: number,
  baseVersionId: number | null,
): Promise<CleaningRecommendations> {
  const query = baseVersionId === null ? "" : "?base_version_id=" + baseVersionId;
  const response = await fetch(
    API_BASE_URL + "/api/datasets/" + datasetId + "/cleaning/recommendations" + query,
    { cache: "no-store" },
  );
  return readResponse<CleaningRecommendations>(response);
}

export async function getDatasetVersions(datasetId: number): Promise<DatasetVersion[]> {
  const response = await fetch(
    API_BASE_URL + "/api/datasets/" + datasetId + "/cleaning/versions",
    { cache: "no-store" },
  );
  return readResponse<DatasetVersion[]>(response);
}

export async function getDatasetVersionQualityComparison(
  datasetId: number,
  versionId: number,
): Promise<QualityVersionComparison> {
  const response = await fetch(
    API_BASE_URL + "/api/datasets/" + datasetId + "/cleaning/versions/" +
      versionId + "/quality-comparison",
    { cache: "no-store" },
  );
  return readResponse<QualityVersionComparison>(response);
}

export async function previewDatasetCleaning(
  datasetId: number,
  request: CleaningRequest,
): Promise<CleaningPreview> {
  const response = await fetch(
    API_BASE_URL + "/api/datasets/" + datasetId + "/cleaning/preview",
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(request),
      cache: "no-store",
    },
  );
  return readResponse<CleaningPreview>(response);
}

export async function applyDatasetCleaning(
  datasetId: number,
  request: CleaningRequest,
): Promise<CleaningApplyResult> {
  const response = await fetch(
    API_BASE_URL + "/api/datasets/" + datasetId + "/cleaning/apply",
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(request),
      cache: "no-store",
    },
  );
  return readResponse<CleaningApplyResult>(response);
}


export async function getDatasetProfile(datasetId: number): Promise<DatasetProfile> {
  const response = await fetch(`${API_BASE_URL}/api/datasets/${datasetId}/profile`, {
    cache: "no-store",
  });
  return readResponse<DatasetProfile>(response);
}

export async function assessDatasetReadiness(
  datasetId: number,
  request: MLReadinessRequest,
): Promise<MLReadinessReport> {
  const response = await fetch(`${API_BASE_URL}/api/datasets/${datasetId}/ml-readiness`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(request),
    cache: "no-store",
  });
  return readResponse<MLReadinessReport>(response);
}

export async function trainBaselineModel(
  datasetId: number,
  request: BaselineModelRequest,
): Promise<BaselineModelReport> {
  const response = await fetch(`${API_BASE_URL}/api/datasets/${datasetId}/baseline-model`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(request),
    cache: "no-store",
  });
  return readResponse<BaselineModelReport>(response);
}

export async function uploadDataset(file: File): Promise<Dataset> {
  const formData = new FormData();
  formData.append("file", file);

  const response = await fetch(`${API_BASE_URL}/api/datasets/upload`, {
    method: "POST",
    body: formData,
  });

  return readResponse<Dataset>(response);
}
