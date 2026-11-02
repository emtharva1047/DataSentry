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

export async function uploadDataset(file: File): Promise<Dataset> {
  const formData = new FormData();
  formData.append("file", file);

  const response = await fetch(`${API_BASE_URL}/api/datasets/upload`, {
    method: "POST",
    body: formData,
  });

  return readResponse<Dataset>(response);
}
