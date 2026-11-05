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

export async function uploadDataset(file: File): Promise<Dataset> {
  const formData = new FormData();
  formData.append("file", file);

  const response = await fetch(`${API_BASE_URL}/api/datasets/upload`, {
    method: "POST",
    body: formData,
  });

  return readResponse<Dataset>(response);
}
