"use client";

import {
  type ChangeEvent,
  type FormEvent,
  useCallback,
  useEffect,
  useRef,
  useState,
} from "react";
import CleaningPanel from "@/components/CleaningPanel";
import {
  API_DOCS_URL,
  getDatasetAnomalies,
  getDatasetQuality,
  getDatasets,
  getOverview,
  uploadDataset,
  type AnomalyDetectionRequest,
  type AnomalyDetectorName,
  type AnomalyReport,
  type Dataset,
  type Overview,
  type QualityComponent,
  type QualityReport,
} from "@/lib/api";

const MAX_UPLOAD_BYTES = 10 * 1024 * 1024;

function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

function formatNumber(value: number): string {
  return new Intl.NumberFormat().format(value);
}

function formatDate(value: string): string {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "Date unavailable";
  return new Intl.DateTimeFormat(undefined, {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(date);
}

function BrandMark() {
  return (
    <span className="flex h-10 w-10 items-center justify-center rounded-xl border border-emerald-300/25 bg-emerald-300/10 text-[#64e5c1]">
      <svg viewBox="0 0 24 24" width="22" height="22" fill="none" aria-hidden="true">
        <path d="M12 2.8 19 5.5v5.8c0 4.7-2.8 8.1-7 9.9-4.2-1.8-7-5.2-7-9.9V5.5l7-2.7Z" stroke="currentColor" strokeWidth="1.6" />
        <path d="m8.6 12.1 2.2 2.2 4.8-5" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" />
      </svg>
    </span>
  );
}

function MetricCard({
  label,
  value,
  note,
  icon,
}: {
  label: string;
  value: string;
  note: string;
  icon: React.ReactNode;
}) {
  return (
    <article className="surface rounded-2xl p-5">
      <div className="flex items-center justify-between">
        <p className="text-sm font-medium text-slate-400">{label}</p>
        <span className="flex h-9 w-9 items-center justify-center rounded-xl bg-white/[0.045] text-[#83dcca]">
          {icon}
        </span>
      </div>
      <p className="mt-5 text-3xl font-semibold tracking-tight text-white">{value}</p>
      <p className="mt-1 text-xs text-slate-500">{note}</p>
    </article>
  );
}

function EmptyState() {
  return (
    <div className="px-5 py-14 text-center">
      <div className="mx-auto flex h-14 w-14 items-center justify-center rounded-2xl border border-slate-700 bg-slate-800/70 text-[#83dcca]">
        <svg viewBox="0 0 24 24" width="25" height="25" fill="none" aria-hidden="true">
          <path d="M4 5.5h16v13H4zM4 9.5h16M9 5.5v13" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
        </svg>
      </div>
      <h3 className="mt-4 text-base font-semibold text-slate-100">Your workspace is ready</h3>
      <p className="mx-auto mt-2 max-w-sm text-sm leading-6 text-slate-400">
        Upload a CSV dataset to begin. Once it appears here, run a quality check to review its Data Quality Score and detected issues.
      </p>
    </div>
  );
}

function QualityReportPanel({
  report,
  isLoading,
  error,
}: {
  report: QualityReport | null;
  isLoading: boolean;
  error: string | null;
}) {
  if (isLoading) {
    return (
      <section id="quality-report" className="surface rounded-2xl p-6" aria-live="polite">
        <p className="eyebrow">Quality assessment</p>
        <h2 className="mt-2 text-lg font-semibold text-white">Analyzing dataset quality...</h2>
        <p className="mt-2 text-sm text-slate-400">The original CSV remains unchanged while DataSentry evaluates its quality.</p>
        <div className="mt-5 h-2 animate-pulse rounded-full bg-slate-700" />
      </section>
    );
  }

  if (error) {
    return (
      <section id="quality-report" className="surface rounded-2xl p-6" aria-live="polite">
        <p className="eyebrow">Quality assessment</p>
        <h2 className="mt-2 text-lg font-semibold text-white">Assessment could not be completed</h2>
        <p role="alert" className="mt-2 text-sm text-rose-200">{error}</p>
        <p className="mt-2 text-xs text-slate-500">Select the dataset again to retry. No source data was changed.</p>
      </section>
    );
  }

  if (!report) {
    return (
      <section id="quality-report" className="surface rounded-2xl p-6">
        <p className="eyebrow">Quality assessment</p>
        <h2 className="mt-2 text-lg font-semibold text-white">Dataset quality report</h2>
        <p className="mt-2 text-sm text-slate-400">Choose “Run quality check” beside a dataset to calculate its Data Quality Score and inspect evidence-backed findings.</p>
      </section>
    );
  }

  const components: { label: string; value: QualityComponent }[] = [
    { label: "Completeness", value: report.data_quality_score.components.completeness },
    { label: "Validity", value: report.data_quality_score.components.validity },
    { label: "Uniqueness", value: report.data_quality_score.components.uniqueness },
    { label: "Consistency", value: report.data_quality_score.components.consistency },
  ];
  const overall = report.data_quality_score.overall;

  return (
    <section id="quality-report" className="surface overflow-hidden rounded-2xl">
      <div className="flex flex-wrap items-start justify-between gap-3 border-b border-slate-800 px-5 py-5 sm:px-6">
        <div>
          <p className="eyebrow">Quality assessment · v{report.quality_version}</p>
          <h2 className="mt-2 text-lg font-semibold text-white">Data Quality Report</h2>
          <p className="mt-1 text-xs text-slate-500">{report.filename} · {formatNumber(report.shape.rows)} rows × {formatNumber(report.shape.columns)} columns</p>
        </div>
        <span className="rounded-full border border-slate-700 bg-slate-800/70 px-3 py-1 text-xs text-slate-300">
          {formatNumber(report.issue_count)} findings
        </span>
      </div>

      <div className="grid gap-5 p-5 sm:p-6 xl:grid-cols-[minmax(220px,0.75fr)_minmax(0,1.5fr)]">
        <div className="rounded-2xl border border-emerald-300/15 bg-emerald-300/[0.045] p-5">
          <p className="text-xs font-semibold uppercase tracking-wider text-slate-400">Overall DQS</p>
          <div className="mt-3 flex items-baseline gap-2">
            <span className="text-5xl font-semibold tracking-tight text-white">
              {overall === null ? "N/A" : overall.toFixed(1)}
            </span>
            {overall !== null && <span className="text-sm text-slate-500">/ 100</span>}
          </div>
          {overall !== null && (
            <div
              className="mt-4 h-2 overflow-hidden rounded-full bg-slate-800"
              role="progressbar"
              aria-label="Overall Data Quality Score"
              aria-valuemin={0}
              aria-valuemax={100}
              aria-valuenow={overall}
            >
              <div className="h-full rounded-full bg-[#64e5c1]" style={{ width: String(Math.max(0, Math.min(100, overall))) + "%" }} />
            </div>
          )}
          <p className="mt-4 text-xs leading-5 text-slate-400">
            {overall === null
              ? "No DQS component has an assessable denominator."
              : "Weighted mean of applicable components. Inapplicable components are excluded and active weights are renormalized."}
          </p>
          <div className="mt-5 grid grid-cols-3 gap-2 border-t border-slate-700/70 pt-4">
            {(["high", "medium", "low"] as const).map((severity) => (
              <div key={severity}>
                <p className="text-xl font-semibold text-white">{report.issues_by_severity[severity]}</p>
                <p className="text-[10px] uppercase tracking-wider text-slate-500">{severity}</p>
              </div>
            ))}
          </div>
        </div>

        <div>
          <div className="flex flex-wrap items-center justify-between gap-2">
            <h3 className="text-sm font-semibold text-white">Score breakdown</h3>
            <p className="text-[11px] text-slate-500">Nominal weights · active weights are renormalized</p>
          </div>
          <div className="mt-4 grid gap-4 sm:grid-cols-2">
            {components.map(({ label, value }) => {
              const activeWeight = value.applicable && report.data_quality_score.active_weight_total > 0
                ? (value.weight / report.data_quality_score.active_weight_total) * 100
                : 0;
              return (
                <div key={label} className="rounded-xl border border-slate-800 bg-slate-950/35 p-4">
                  <div className="flex items-center justify-between gap-2">
                    <p className="text-sm font-medium text-slate-200">{label}</p>
                    <p className="text-sm font-semibold text-white">
                      {value.score === null ? "N/A" : value.score.toFixed(1) + "%"}
                    </p>
                  </div>
                  <div className="mt-3 h-1.5 overflow-hidden rounded-full bg-slate-800">
                    <div
                      className="h-full rounded-full bg-[#64e5c1]"
                      style={{ width: String(value.score ?? 0) + "%" }}
                    />
                  </div>
                  <p className="mt-2 text-[10px] leading-4 text-slate-500">
                    {formatNumber(value.numerator)} / {formatNumber(value.denominator)} · {value.applicable ? "Active " + activeWeight.toFixed(1) + "% weight" : "Not applicable"}
                  </p>
                  <p className="mt-1 text-[10px] leading-4 text-slate-600">{value.basis}</p>
                </div>
              );
            })}
          </div>
        </div>
      </div>

      <div className="border-t border-slate-800 px-5 py-5 sm:px-6">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <div>
            <h3 className="text-sm font-semibold text-white">Detected issues</h3>
            <p className="mt-1 text-xs text-slate-500">Findings include affected counts and bounded, one-based data-row evidence.</p>
          </div>
          <span className="text-[11px] text-slate-500">Generated {formatDate(report.generated_at)}</span>
        </div>
        {report.issues.length === 0 ? (
          <div className="mt-4 rounded-xl border border-emerald-300/15 bg-emerald-300/[0.045] px-4 py-5 text-sm text-emerald-100">
            No rule-based issues were detected by the currently enabled checks.
          </div>
        ) : (
          <ul className="mt-4 space-y-3">
            {report.issues.map((issue, index) => {
              const rowNumbers = Array.isArray(issue.evidence.row_numbers)
                ? issue.evidence.row_numbers.filter((value): value is number => typeof value === "number")
                : [];
              const severityClass = issue.severity === "high"
                ? "border-rose-400/20 bg-rose-400/[0.08] text-rose-200"
                : issue.severity === "medium"
                  ? "border-amber-300/20 bg-amber-300/[0.08] text-amber-100"
                  : "border-slate-600 bg-slate-800/70 text-slate-300";
              return (
                <li key={issue.code + ":" + (issue.column ?? "dataset") + ":" + index} className="rounded-xl border border-slate-800 bg-slate-950/35 p-4">
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <div className="flex flex-wrap items-center gap-2">
                      <span className={"rounded-full border px-2.5 py-1 text-[10px] font-semibold uppercase tracking-wider " + severityClass}>
                        {issue.severity}
                      </span>
                      <span className="text-xs font-semibold text-slate-200">{issue.code.replace(/_/g, " ")}</span>
                      {issue.column && <span className="rounded-md bg-slate-800 px-2 py-1 font-mono text-[10px] text-slate-400">{issue.column}</span>}
                    </div>
                    <span className="text-xs tabular-nums text-slate-400">
                      {formatNumber(issue.affected_count)} / {formatNumber(issue.denominator)} · {issue.affected_pct.toFixed(2)}%
                    </span>
                  </div>
                  <p className="mt-3 text-sm leading-5 text-slate-300">{issue.message}</p>
                  {rowNumbers.length > 0 && (
                    <p className="mt-2 text-[11px] leading-5 text-slate-500">
                      Data rows: {rowNumbers.slice(0, 10).join(", ")}{rowNumbers.length > 10 ? ", …" : ""}
                    </p>
                  )}
                </li>
              );
            })}
          </ul>
        )}
        <div className="mt-5 border-t border-slate-800 pt-4">
          <details>
            <summary className="cursor-pointer text-xs font-semibold text-slate-400 hover:text-slate-200">Scoring and detector notes</summary>
            <ul className="mt-3 list-disc space-y-2 pl-5 text-xs leading-5 text-slate-500">
              {report.method_notes.map((note) => <li key={note}>{note}</li>)}
            </ul>
          </details>
        </div>
      </div>
    </section>
  );
}


type AnomalyParameterState = {
  iqrMultiplier: string;
  robustZThreshold: string;
  contamination: string;
  randomState: string;
  nEstimators: string;
};

type AnomalyParameterKey = keyof AnomalyParameterState;

function formatOptionalNumber(value: number | null | undefined): string {
  return typeof value === "number" && Number.isFinite(value)
    ? value.toLocaleString(undefined, { maximumFractionDigits: 4 })
    : "—";
}

function AnomalyReportPanel({
  report,
  dataset,
  isLoading,
  error,
  selectedDetectors,
  onToggleDetector,
  parameters,
  onParameterChange,
  onRun,
}: {
  report: AnomalyReport | null;
  dataset: Dataset | null;
  isLoading: boolean;
  error: string | null;
  selectedDetectors: AnomalyDetectorName[];
  onToggleDetector: (detector: AnomalyDetectorName) => void;
  parameters: AnomalyParameterState;
  onParameterChange: (key: AnomalyParameterKey, value: string) => void;
  onRun: () => void;
}) {
  const parsed = {
    iqrMultiplier: Number(parameters.iqrMultiplier),
    robustZThreshold: Number(parameters.robustZThreshold),
    contamination: Number(parameters.contamination),
    randomState: Number(parameters.randomState),
    nEstimators: Number(parameters.nEstimators),
  };
  const parametersValid =
    Number.isFinite(parsed.iqrMultiplier) && parsed.iqrMultiplier > 0 && parsed.iqrMultiplier <= 10 &&
    Number.isFinite(parsed.robustZThreshold) && parsed.robustZThreshold > 0 && parsed.robustZThreshold <= 20 &&
    Number.isFinite(parsed.contamination) && parsed.contamination > 0 && parsed.contamination <= 0.5 &&
    Number.isInteger(parsed.randomState) && parsed.randomState >= 0 && parsed.randomState <= 4294967295 &&
    Number.isInteger(parsed.nEstimators) && parsed.nEstimators >= 50 && parsed.nEstimators <= 500;
  const detectorLabels: Record<AnomalyDetectorName, string> = {
    iqr: "IQR fences",
    robust_zscore: "Modified robust Z-score",
    isolation_forest: "Isolation Forest",
  };

  return (
    <section id="anomaly-report" className="surface overflow-hidden rounded-2xl">
      <div className="flex flex-wrap items-start justify-between gap-3 border-b border-slate-800 px-5 py-5 sm:px-6">
        <div>
          <p className="eyebrow">Anomaly detection · review only</p>
          <h2 className="mt-2 text-lg font-semibold text-white">Numerical anomaly review</h2>
          <p className="mt-1 text-xs text-slate-500">
            {dataset ? dataset.filename + " · " + formatNumber(dataset.rows_count) + " rows" : "Select a dataset from the library to begin."}
          </p>
        </div>
        <span className="rounded-full border border-amber-300/20 bg-amber-300/[0.06] px-3 py-1 text-xs text-amber-100">
          No rows are changed or deleted
        </span>
      </div>

      {!dataset ? (
        <div className="px-5 py-10 text-center text-sm text-slate-400">
          Choose “Run anomaly scan” beside a dataset to configure detectors and inspect flagged rows.
        </div>
      ) : (
        <>
          <div className="grid gap-5 border-b border-slate-800 p-5 sm:p-6">
            <div>
              <p className="text-xs font-semibold uppercase tracking-wider text-slate-400">Detectors</p>
              <div className="mt-3 grid gap-3 sm:grid-cols-3">
                {(Object.keys(detectorLabels) as AnomalyDetectorName[]).map((detector) => (
                  <label key={detector} className="flex cursor-pointer items-start gap-3 rounded-xl border border-slate-800 bg-slate-950/35 p-3 text-sm text-slate-200">
                    <input
                      type="checkbox"
                      checked={selectedDetectors.includes(detector)}
                      onChange={() => onToggleDetector(detector)}
                      className="mt-0.5 accent-emerald-300"
                    />
                    <span>{detectorLabels[detector]}</span>
                  </label>
                ))}
              </div>
              {selectedDetectors.length === 0 && (
                <p className="mt-2 text-xs text-rose-200" role="alert">Select at least one detector.</p>
              )}
            </div>

            <div>
              <p className="text-xs font-semibold uppercase tracking-wider text-slate-400">Reproducible parameters</p>
              <div className="mt-3 grid gap-3 sm:grid-cols-2 xl:grid-cols-5">
                <label className="text-xs text-slate-400">
                  IQR multiplier
                  <input type="number" min="0.01" max="10" step="0.1" value={parameters.iqrMultiplier} onChange={(event) => onParameterChange("iqrMultiplier", event.currentTarget.value)} className="mt-2 w-full rounded-lg border border-slate-700 bg-slate-950 px-3 py-2 text-sm text-white" />
                  <span className="mt-1 block text-[10px] text-slate-600">Greater than 0, up to 10</span>
                </label>
                <label className="text-xs text-slate-400">
                  Robust Z threshold
                  <input type="number" min="0.01" max="20" step="0.1" value={parameters.robustZThreshold} onChange={(event) => onParameterChange("robustZThreshold", event.currentTarget.value)} className="mt-2 w-full rounded-lg border border-slate-700 bg-slate-950 px-3 py-2 text-sm text-white" />
                  <span className="mt-1 block text-[10px] text-slate-600">Greater than 0, up to 20</span>
                </label>
                <label className="text-xs text-slate-400">
                  IF contamination
                  <input type="number" min="0.001" max="0.5" step="0.01" value={parameters.contamination} onChange={(event) => onParameterChange("contamination", event.currentTarget.value)} className="mt-2 w-full rounded-lg border border-slate-700 bg-slate-950 px-3 py-2 text-sm text-white" />
                  <span className="mt-1 block text-[10px] text-slate-600">Greater than 0, at most 0.5</span>
                </label>
                <label className="text-xs text-slate-400">
                  Random seed
                  <input type="number" min="0" max="4294967295" step="1" value={parameters.randomState} onChange={(event) => onParameterChange("randomState", event.currentTarget.value)} className="mt-2 w-full rounded-lg border border-slate-700 bg-slate-950 px-3 py-2 text-sm text-white" />
                  <span className="mt-1 block text-[10px] text-slate-600">Integer from 0 to 2³²−1</span>
                </label>
                <label className="text-xs text-slate-400">
                  Isolation Forest trees
                  <input type="number" min="50" max="500" step="10" value={parameters.nEstimators} onChange={(event) => onParameterChange("nEstimators", event.currentTarget.value)} className="mt-2 w-full rounded-lg border border-slate-700 bg-slate-950 px-3 py-2 text-sm text-white" />
                  <span className="mt-1 block text-[10px] text-slate-600">Integer from 50 to 500</span>
                </label>
              </div>
              {!parametersValid && (
                <p className="mt-3 text-xs text-rose-200" role="alert">Check the parameter ranges before running the scan.</p>
              )}
            </div>

            <div className="flex flex-wrap items-center justify-between gap-3">
              <p className="max-w-2xl text-xs leading-5 text-slate-500">
                All eligible numeric-like columns are scanned. Columns need at least four finite values and 80% finite numeric parseability. Isolation Forest additionally needs at least ten observed rows.
              </p>
              <button
                type="button"
                className="primary-button focus-ring whitespace-nowrap"
                onClick={onRun}
                disabled={isLoading || selectedDetectors.length === 0 || !parametersValid}
              >
                {isLoading ? "Scanning..." : report ? "Run scan again" : "Run anomaly scan"}
              </button>
            </div>
          </div>

          {isLoading ? (
            <div className="p-6" aria-live="polite">
              <p className="text-sm font-semibold text-white">Running selected detectors...</p>
              <p className="mt-2 text-xs text-slate-500">The source CSV is read-only. Isolation Forest uses the configured random seed.</p>
              <div className="mt-4 h-2 animate-pulse rounded-full bg-slate-700" />
            </div>
          ) : error ? (
            <div className="p-6" aria-live="polite">
              <p className="text-sm font-semibold text-rose-200">Anomaly scan could not be completed</p>
              <p role="alert" className="mt-2 text-sm text-rose-100/80">{error}</p>
            </div>
          ) : !report ? (
            <div className="p-6 text-sm text-slate-400">
              Configure the detectors and run a scan. Results are review flags, not proof that a record is invalid.
            </div>
          ) : (
            <div className="space-y-6 p-5 sm:p-6">
              <div className="grid gap-3 sm:grid-cols-3">
                <div className="rounded-xl border border-amber-300/15 bg-amber-300/[0.045] p-4">
                  <p className="text-xs text-slate-400">Unique rows flagged</p>
                  <p className="mt-2 text-2xl font-semibold text-white">{formatNumber(report.summary.flagged_row_count)}</p>
                </div>
                <div className="rounded-xl border border-slate-800 bg-slate-950/35 p-4">
                  <p className="text-xs text-slate-400">Numeric columns eligible</p>
                  <p className="mt-2 text-2xl font-semibold text-white">{formatNumber(report.numeric_columns.filter((column) => column.eligible).length)} / {formatNumber(report.numeric_columns.length)}</p>
                </div>
                <div className="rounded-xl border border-slate-800 bg-slate-950/35 p-4">
                  <p className="text-xs text-slate-400">Random seed</p>
                  <p className="mt-2 text-2xl font-semibold text-white">{report.parameters.random_state}</p>
                </div>
              </div>

              <div>
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <h3 className="text-sm font-semibold text-white">Detector results</h3>
                  <span className="text-[11px] text-slate-500">Generated {formatDate(report.generated_at)}</span>
                </div>
                <div className="mt-3 grid gap-3 xl:grid-cols-3">
                  {selectedDetectors.map((detector) => {
                    const result = report.detectors[detector];
                    if (!result) return null;
                    const flaggedCount = result.flagged_row_count ?? result.flagged_count ?? (result.columns ?? []).reduce((sum, column) => sum + column.flagged_count, 0);
                    const rowNumbers = result.flagged_row_numbers ?? (result.columns ?? []).flatMap((column) => column.flagged_row_numbers);
                    const evidence = result.evidence ?? (result.columns ?? []).flatMap((column) => column.evidence ?? []);
                    return (
                      <article key={detector} className="rounded-xl border border-slate-800 bg-slate-950/35 p-4">
                        <div className="flex items-start justify-between gap-2">
                          <h4 className="text-sm font-semibold text-slate-100">{detectorLabels[detector]}</h4>
                          <span className={"rounded-full px-2 py-1 text-[10px] font-semibold uppercase " + (result.status === "completed" ? "bg-emerald-300/10 text-emerald-100" : "bg-slate-700 text-slate-300")}>{result.status}</span>
                        </div>
                        <p className="mt-3 text-2xl font-semibold text-white">{formatNumber(flaggedCount)}</p>
                        <p className="text-[10px] uppercase tracking-wider text-slate-500">Flagged rows</p>
                        {result.reason && <p className="mt-3 text-xs leading-5 text-slate-400">{result.reason}</p>}
                        {result.rows_scored !== undefined && <p className="mt-2 text-xs text-slate-500">Rows scored: {formatNumber(result.rows_scored)}</p>}
                        {result.feature_columns && <p className="mt-2 break-words text-xs text-slate-500">Features: {result.feature_columns.join(", ") || "None"}</p>}
                        {result.columns && result.columns.length > 0 && (
                          <ul className="mt-3 space-y-2 border-t border-slate-800 pt-3">
                            {result.columns.map((column) => (
                              <li key={column.column} className="text-xs">
                                <p className="font-medium text-slate-300">{column.column} · {formatNumber(column.flagged_count)} flagged</p>
                                <p className="mt-1 leading-5 text-slate-500">
                                  {column.reason ?? (column.lower_fence !== undefined
                                    ? "Fences: " + formatOptionalNumber(column.lower_fence) + " to " + formatOptionalNumber(column.upper_fence)
                                    : column.median !== undefined
                                      ? "Median: " + formatOptionalNumber(column.median) + " · MAD: " + formatOptionalNumber(column.mad)
                                      : column.status)}
                                </p>
                              </li>
                            ))}
                          </ul>
                        )}
                        {rowNumbers.length > 0 && (
                          <p className="mt-3 break-words text-[11px] leading-5 text-slate-500">
                            Data rows: {rowNumbers.slice(0, 12).join(", ")}{rowNumbers.length > 12 ? ", …" : ""}
                          </p>
                        )}
                        {evidence.length > 0 && (
                          <details className="mt-3 border-t border-slate-800 pt-3">
                            <summary className="cursor-pointer text-[11px] font-semibold text-slate-400">Inspect evidence ({evidence.length})</summary>
                            <ul className="mt-2 space-y-1 text-[10px] text-slate-500">
                              {evidence.slice(0, 20).map((item) => (
                                <li key={item.row_number}>
                                  Row {item.row_number}
                                  {item.value !== undefined && " · value " + formatOptionalNumber(item.value)}
                                  {item.modified_z_score !== undefined && " · |modified Z| " + formatOptionalNumber(item.modified_z_score)}
                                  {item.anomaly_score !== undefined && " · anomaly score " + formatOptionalNumber(item.anomaly_score)}
                                </li>
                              ))}
                            </ul>
                          </details>
                        )}
                      </article>
                    );
                  })}
                </div>
              </div>

              <div>
                <h3 className="text-sm font-semibold text-white">Numeric-column eligibility</h3>
                <div className="mt-3 overflow-x-auto rounded-xl border border-slate-800">
                  <table className="w-full min-w-[560px] text-left text-xs">
                    <thead className="bg-white/[0.025] text-[10px] uppercase tracking-wider text-slate-500">
                      <tr>
                        <th className="px-3 py-3">Column</th>
                        <th className="px-3 py-3">Eligible</th>
                        <th className="px-3 py-3">Finite parseability</th>
                        <th className="px-3 py-3">Reason</th>
                      </tr>
                    </thead>
                    <tbody>
                      {report.numeric_columns.map((column) => (
                        <tr key={column.column} className="border-t border-slate-800">
                          <td className="px-3 py-3 font-mono text-slate-300">{column.column}</td>
                          <td className="px-3 py-3 text-slate-300">{column.eligible ? "Yes" : "No"}</td>
                          <td className="px-3 py-3 tabular-nums text-slate-400">{column.finite_parseability_pct.toFixed(2)}%</td>
                          <td className="px-3 py-3 text-slate-500">{column.reason ?? "Meets numeric eligibility rules"}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>

              <div className="border-t border-slate-800 pt-4">
                <p className="text-[10px] text-slate-600">Source SHA-256: {report.source_sha256 ?? "Unavailable"}</p>
                <details className="mt-3">
                  <summary className="cursor-pointer text-xs font-semibold text-slate-400 hover:text-slate-200">Detector methodology and limitations</summary>
                  <ul className="mt-3 list-disc space-y-2 pl-5 text-xs leading-5 text-slate-500">
                    {report.method_notes.map((note) => <li key={note}>{note}</li>)}
                  </ul>
                </details>
              </div>
            </div>
          )}
        </>
      )}
    </section>
  );
}

export default function Home() {
  const [overview, setOverview] = useState<Overview | null>(null);
  const [datasets, setDatasets] = useState<Dataset[]>([]);
  const [selectedDatasetId, setSelectedDatasetId] = useState<number | null>(null);
  const [qualityReport, setQualityReport] = useState<QualityReport | null>(null);
  const [qualityError, setQualityError] = useState<string | null>(null);
  const [isLoadingQuality, setIsLoadingQuality] = useState(false);
  const [anomalyReport, setAnomalyReport] = useState<AnomalyReport | null>(null);
  const [anomalyError, setAnomalyError] = useState<string | null>(null);
  const [isLoadingAnomalies, setIsLoadingAnomalies] = useState(false);
  const [selectedDetectors, setSelectedDetectors] = useState<AnomalyDetectorName[]>([
    "iqr",
    "robust_zscore",
    "isolation_forest",
  ]);
  const [anomalyParameters, setAnomalyParameters] = useState<AnomalyParameterState>({
    iqrMultiplier: "1.5",
    robustZThreshold: "3.5",
    contamination: "0.05",
    randomState: "42",
    nEstimators: "100",
  });
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isUploading, setIsUploading] = useState(false);
  const [isRefreshing, setIsRefreshing] = useState(false);
  const [apiError, setApiError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const refreshData = useCallback(async () => {
    setIsRefreshing(true);
    setApiError(null);

    const [overviewResult, datasetsResult] = await Promise.allSettled([
      getOverview(),
      getDatasets(),
    ]);

    if (overviewResult.status === "fulfilled") {
      setOverview(overviewResult.value);
    }
    if (datasetsResult.status === "fulfilled") {
      setDatasets(datasetsResult.value);
    }

    const failedResult =
      overviewResult.status === "rejected"
        ? overviewResult
        : datasetsResult.status === "rejected"
          ? datasetsResult
          : null;

    if (failedResult) {
      const reason = failedResult.reason;
      setApiError(
        reason instanceof Error
          ? reason.message
          : "Could not load DataSentry workspace data.",
      );
    }

    setIsLoading(false);
    setIsRefreshing(false);
  }, []);

  useEffect(() => {
    let isActive = true;

    void Promise.allSettled([getOverview(), getDatasets()]).then(
      ([overviewResult, datasetsResult]) => {
        if (!isActive) return;

        if (overviewResult.status === "fulfilled") {
          setOverview(overviewResult.value);
        }
        if (datasetsResult.status === "fulfilled") {
          setDatasets(datasetsResult.value);
        }

        const failedResult =
          overviewResult.status === "rejected"
            ? overviewResult
            : datasetsResult.status === "rejected"
              ? datasetsResult
              : null;

        if (failedResult) {
          const reason = failedResult.reason;
          setApiError(
            reason instanceof Error
              ? reason.message
              : "Could not load DataSentry workspace data.",
          );
        }

        setIsLoading(false);
      },
    );

    return () => {
      isActive = false;
    };
  }, []);

  async function runQualityAssessment(dataset: Dataset) {
    setSelectedDatasetId(dataset.id);
    setQualityReport(null);
    setQualityError(null);
    setAnomalyReport(null);
    setAnomalyError(null);
    setIsLoadingQuality(true);

    try {
      const report = await getDatasetQuality(dataset.id);
      setQualityReport(report);
    } catch (error) {
      setQualityError(
        error instanceof Error ? error.message : "Could not run the quality assessment.",
      );
    } finally {
      setIsLoadingQuality(false);
    }
  }

  function toggleAnomalyDetector(detector: AnomalyDetectorName) {
    setSelectedDetectors((current) =>
      current.includes(detector)
        ? current.filter((item) => item !== detector)
        : [...current, detector],
    );
  }

  function updateAnomalyParameter(key: AnomalyParameterKey, value: string) {
    setAnomalyParameters((current) => ({ ...current, [key]: value }));
  }

  async function runAnomalyAssessment(dataset: Dataset) {
    setSelectedDatasetId(dataset.id);
    setQualityReport(null);
    setQualityError(null);
    setAnomalyReport(null);
    setAnomalyError(null);
    setIsLoadingAnomalies(true);

    const request: AnomalyDetectionRequest = {
      detectors: selectedDetectors,
      iqr_multiplier: Number(anomalyParameters.iqrMultiplier),
      robust_z_threshold: Number(anomalyParameters.robustZThreshold),
      contamination: Number(anomalyParameters.contamination),
      random_state: Number(anomalyParameters.randomState),
      n_estimators: Number(anomalyParameters.nEstimators),
      max_evidence_rows: 20,
    };

    try {
      const report = await getDatasetAnomalies(dataset.id, request);
      setAnomalyReport(report);
    } catch (error) {
      setAnomalyError(
        error instanceof Error ? error.message : "Could not run anomaly detection.",
      );
    } finally {
      setIsLoadingAnomalies(false);
    }
  }

  function handleFileChange(event: ChangeEvent<HTMLInputElement>) {
    const file = event.currentTarget.files?.[0] ?? null;
    setApiError(null);
    setNotice(null);

    if (!file) {
      setSelectedFile(null);
      return;
    }
    if (!file.name.toLowerCase().endsWith(".csv")) {
      setSelectedFile(null);
      event.currentTarget.value = "";
      setApiError("Choose a .csv file. Other file formats are not supported yet.");
      return;
    }
    if (file.size > MAX_UPLOAD_BYTES) {
      setSelectedFile(null);
      event.currentTarget.value = "";
      setApiError("This file exceeds the 10 MB upload limit.");
      return;
    }
    setSelectedFile(file);
  }

  async function handleUpload(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!selectedFile) return;

    setIsUploading(true);
    setApiError(null);
    setNotice(null);

    try {
      const uploaded = await uploadDataset(selectedFile);
      setNotice(`${uploaded.filename} was uploaded successfully.`);
      setSelectedFile(null);
      if (fileInputRef.current) fileInputRef.current.value = "";
      await refreshData();
      await runQualityAssessment(uploaded);
    } catch (error) {
      setApiError(
        error instanceof Error ? error.message : "The upload could not be completed.",
      );
    } finally {
      setIsUploading(false);
    }
  }

  const selectedDataset = datasets.find((dataset) => dataset.id === selectedDatasetId) ?? null;
  const totalRows = datasets.reduce((sum, dataset) => sum + dataset.rows_count, 0);
  const connectionState = overview ? "online" : apiError ? "offline" : "checking";

  return (
    <div className="min-h-screen">
      <aside className="fixed inset-y-0 left-0 z-20 hidden w-64 flex-col border-r border-slate-800/80 bg-[#0b1220]/90 px-5 py-6 backdrop-blur-xl lg:flex">
        <a href="#overview" className="flex items-center gap-3">
          <BrandMark />
          <span>
            <span className="block text-base font-bold tracking-tight text-white">
              Data<span className="text-[#64e5c1]">Sentry</span>
            </span>
            <span className="block text-[10px] font-semibold uppercase tracking-[0.16em] text-slate-500">
              Data intelligence
            </span>
          </span>
        </a>

        <div className="mt-12">
          <p className="eyebrow px-3">Workspace</p>
          <a
            href="#overview"
            className="mt-3 flex items-center gap-3 rounded-xl border border-emerald-300/15 bg-emerald-300/[0.08] px-3 py-3 text-sm font-semibold text-[#a3f1dc]"
          >
            <svg viewBox="0 0 24 24" width="18" height="18" fill="none" aria-hidden="true">
              <rect x="3.5" y="3.5" width="7" height="7" rx="1.5" stroke="currentColor" strokeWidth="1.5" />
              <rect x="13.5" y="3.5" width="7" height="7" rx="1.5" stroke="currentColor" strokeWidth="1.5" />
              <rect x="3.5" y="13.5" width="7" height="7" rx="1.5" stroke="currentColor" strokeWidth="1.5" />
              <rect x="13.5" y="13.5" width="7" height="7" rx="1.5" stroke="currentColor" strokeWidth="1.5" />
            </svg>
            Overview
          </a>
          <a
            href="#datasets"
            className="mt-2 flex items-center gap-3 rounded-xl px-3 py-3 text-sm font-medium text-slate-400 transition hover:bg-white/[0.04] hover:text-white"
          >
            <svg viewBox="0 0 24 24" width="18" height="18" fill="none" aria-hidden="true">
              <path d="M4 5.5h16v13H4zM4 9.5h16M9 5.5v13" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
            </svg>
            Dataset library
          </a>
        </div>

        <div className="mt-auto rounded-2xl border border-slate-800 bg-slate-900/75 p-4">
          <p className="text-xs font-semibold text-slate-200">Research prototype</p>
          <p className="mt-2 text-xs leading-5 text-slate-500">
            Profiling, explainable quality checks and reproducible ML experiments are being built in stages.
          </p>
          <div className="mt-4 flex items-center gap-2 text-[11px] text-slate-400">
            <span className="status-dot online" />
            Development workspace
          </div>
        </div>
      </aside>

      <main id="overview" className="mx-auto min-h-screen max-w-[1600px] px-4 pb-12 pt-5 sm:px-7 lg:ml-64 lg:px-10 lg:pt-8">
        <header className="flex flex-wrap items-center justify-between gap-4 border-b border-slate-800/80 pb-6">
          <div className="flex items-center gap-3 lg:hidden">
            <BrandMark />
            <span className="text-lg font-bold text-white">
              Data<span className="text-[#64e5c1]">Sentry</span>
            </span>
          </div>
          <div className="hidden lg:block">
            <p className="eyebrow">Data quality platform</p>
            <p className="mt-1 text-sm text-slate-400">Your dataset workspace</p>
          </div>
          <div className="ml-auto flex items-center gap-3">
            <div className="flex items-center gap-2 rounded-full border border-slate-800 bg-slate-900/80 px-3 py-2 text-xs text-slate-300">
              <span className={`status-dot ${connectionState === "online" ? "online" : connectionState === "offline" ? "offline" : ""}`} />
              {connectionState === "online"
                ? "API connected"
                : connectionState === "offline"
                  ? "API unavailable"
                  : "Checking API"}
            </div>
            <a className="secondary-button focus-ring" href={API_DOCS_URL} target="_blank" rel="noreferrer">
              API docs
              <svg viewBox="0 0 24 24" width="14" height="14" fill="none" aria-hidden="true">
                <path d="M14 4h6v6M20 4l-9 9M18 13v6a1 1 0 0 1-1 1H5a1 1 0 0 1-1-1V7a1 1 0 0 1 1-1h6" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" />
              </svg>
            </a>
          </div>
        </header>

        <section className="pt-8">
          <div className="flex flex-wrap items-end justify-between gap-4">
            <div>
              <p className="eyebrow">Workspace overview</p>
              <h1 className="mt-2 text-3xl font-semibold tracking-tight text-white sm:text-4xl">
                Good data starts here<span className="text-[#64e5c1]">.</span>
              </h1>
              <p className="mt-3 max-w-2xl text-sm leading-6 text-slate-400">
                Bring your tabular data into one place, then run an explainable quality assessment with evidence-backed findings.
              </p>
            </div>
            <button
              type="button"
              className="secondary-button focus-ring"
              onClick={() => void refreshData()}
              disabled={isRefreshing}
            >
              <svg viewBox="0 0 24 24" width="15" height="15" fill="none" aria-hidden="true">
                <path d="M20 7v5h-5M4 17v-5h5M5.6 9a7 7 0 0 1 11.8-2L20 12M4 12l2.6 5a7 7 0 0 0 11.8-2" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" />
              </svg>
              {isRefreshing ? "Refreshing..." : "Refresh data"}
            </button>
          </div>

          {apiError && (
            <div role="alert" className="mt-6 flex flex-wrap items-start justify-between gap-3 rounded-xl border border-rose-400/20 bg-rose-400/[0.07] px-4 py-3 text-sm text-rose-200">
              <div>
                <p className="font-semibold">Could not complete the API request</p>
                <p className="mt-1 text-rose-100/75">{apiError}</p>
                <p className="mt-1 text-xs text-rose-100/60">
                  Start FastAPI on 127.0.0.1:8000 or set NEXT_PUBLIC_API_BASE_URL in frontend/.env.local.
                </p>
              </div>
              <button type="button" className="text-xs font-semibold underline underline-offset-4" onClick={() => void refreshData()}>
                Try again
              </button>
            </div>
          )}

          {notice && (
            <div role="status" className="mt-6 rounded-xl border border-emerald-300/20 bg-emerald-300/[0.07] px-4 py-3 text-sm text-emerald-100">
              {notice}
            </div>
          )}

          <div className="mt-7 grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
            <MetricCard
              label="Datasets stored"
              value={isLoading ? "—" : formatNumber(datasets.length)}
              note={overview ? "Saved in the DataSentry workspace" : "Waiting for API connection"}
              icon={<svg viewBox="0 0 24 24" width="19" height="19" fill="none" aria-hidden="true"><path d="M4 5.5h16v13H4zM4 9.5h16M9 5.5v13" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" /></svg>}
            />
            <MetricCard
              label="Rows indexed"
              value={isLoading ? "—" : formatNumber(totalRows)}
              note="Across uploaded CSV files"
              icon={<svg viewBox="0 0 24 24" width="19" height="19" fill="none" aria-hidden="true"><path d="M5 5h14M5 10h14M5 15h14M5 20h14M3 5h.01M3 10h.01M3 15h.01M3 20h.01" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" /></svg>}
            />
            <MetricCard
              label="Database engine"
              value={overview?.database_engine ?? "—"}
              note={overview?.database ?? "Connection status unavailable"}
              icon={<svg viewBox="0 0 24 24" width="19" height="19" fill="none" aria-hidden="true"><ellipse cx="12" cy="5.5" rx="7.5" ry="2.8" stroke="currentColor" strokeWidth="1.5" /><path d="M4.5 5.5v6c0 1.6 3.4 2.8 7.5 2.8s7.5-1.2 7.5-2.8v-6M4.5 11.5v6c0 1.6 3.4 2.8 7.5 2.8s7.5-1.2 7.5-2.8v-6" stroke="currentColor" strokeWidth="1.5" /></svg>}
            />
          </div>
        </section>

        <section className="mt-7 grid items-start gap-5 xl:grid-cols-[minmax(0,1.5fr)_minmax(300px,0.8fr)]">
          <div id="datasets" className="surface overflow-hidden rounded-2xl">
            <div className="flex flex-wrap items-center justify-between gap-3 border-b border-slate-800 px-5 py-5 sm:px-6">
              <div>
                <h2 className="text-base font-semibold text-white">Dataset library</h2>
                <p className="mt-1 text-xs text-slate-500">Your uploaded CSV files and stored metadata</p>
              </div>
              <span className="rounded-full border border-slate-700 bg-slate-800/70 px-3 py-1 text-xs text-slate-300">
                {formatNumber(datasets.length)} {datasets.length === 1 ? "dataset" : "datasets"}
              </span>
            </div>

            {isLoading ? (
              <div className="space-y-3 p-6" aria-label="Loading datasets">
                <div className="h-10 animate-pulse rounded-lg bg-slate-800/70" />
                <div className="h-10 animate-pulse rounded-lg bg-slate-800/50" />
                <div className="h-10 animate-pulse rounded-lg bg-slate-800/40" />
              </div>
            ) : datasets.length === 0 ? (
              <EmptyState />
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full min-w-[650px] border-collapse text-left text-sm">
                  <thead className="bg-white/[0.018] text-[11px] uppercase tracking-wider text-slate-500">
                    <tr>
                      <th className="px-5 py-3 font-semibold sm:px-6">Dataset</th>
                      <th className="px-4 py-3 font-semibold">Dimensions</th>
                      <th className="px-4 py-3 font-semibold">File size</th>
                      <th className="px-4 py-3 font-semibold">Uploaded</th>
                      <th className="px-4 py-3 font-semibold">Analysis</th>
                    </tr>
                  </thead>
                  <tbody>
                    {datasets.map((dataset) => (
                      <tr key={dataset.id} className="table-row">
                        <td className="px-5 py-4 sm:px-6">
                          <div className="flex items-center gap-3">
                            <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg border border-emerald-300/15 bg-emerald-300/[0.07] text-[10px] font-bold text-[#8ce8d0]">
                              CSV
                            </span>
                            <div className="min-w-0">
                              <p className="max-w-[230px] truncate font-medium text-slate-100" title={dataset.filename}>
                                {dataset.filename}
                              </p>
                              <p className="mt-1 font-mono text-[10px] text-slate-500">
                                ID {dataset.id} · {dataset.encoding}
                              </p>
                            </div>
                          </div>
                        </td>
                        <td className="px-4 py-4 whitespace-nowrap text-slate-300">
                          {formatNumber(dataset.rows_count)} × {formatNumber(dataset.columns_count)}
                        </td>
                        <td className="px-4 py-4 whitespace-nowrap text-slate-400">
                          {formatBytes(dataset.file_size_bytes)}
                        </td>
                        <td className="px-4 py-4 whitespace-nowrap text-xs text-slate-400">
                          {formatDate(dataset.created_at)}
                        </td>
                        <td className="px-4 py-4">
                          <div className="flex flex-col items-start gap-2">
                            <button
                              type="button"
                              className="secondary-button focus-ring whitespace-nowrap text-[11px]"
                              onClick={() => void runQualityAssessment(dataset)}
                              disabled={isLoadingQuality || isLoadingAnomalies}
                              aria-label={"Run quality check for " + dataset.filename}
                            >
                              {isLoadingQuality && selectedDatasetId === dataset.id
                                ? "Analyzing..."
                                : selectedDatasetId === dataset.id && qualityReport
                                  ? "Report open"
                                  : "Run quality check"}
                            </button>
                            <button
                              type="button"
                              className="secondary-button focus-ring whitespace-nowrap text-[11px]"
                              onClick={() => void runAnomalyAssessment(dataset)}
                              disabled={isLoadingAnomalies || isLoadingQuality || selectedDetectors.length === 0}
                              aria-label={"Run anomaly scan for " + dataset.filename}
                            >
                              {isLoadingAnomalies && selectedDatasetId === dataset.id
                                ? "Scanning..."
                                : selectedDatasetId === dataset.id && anomalyReport
                                  ? "Anomaly report open"
                                  : "Run anomaly scan"}
                            </button>
                            <button
                              type="button"
                              className="secondary-button focus-ring whitespace-nowrap text-[11px]"
                              onClick={() => {
                                setSelectedDatasetId(dataset.id);
                                setQualityReport(null);
                                setQualityError(null);
                                setAnomalyReport(null);
                                setAnomalyError(null);
                              }}
                              aria-label={"Review cleaning for " + dataset.filename}
                            >
                              Review cleaning
                            </button>
                          </div>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>

          <aside className="surface rounded-2xl p-5 sm:p-6">
            <div className="flex items-center gap-3">
              <span className="flex h-10 w-10 items-center justify-center rounded-xl bg-emerald-300/[0.08] text-[#82e8ce]">
                <svg viewBox="0 0 24 24" width="20" height="20" fill="none" aria-hidden="true">
                  <path d="M12 3v12m0 0 4-4m-4 4-4-4M4.5 16.5v3h15v-3" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" />
                </svg>
              </span>
              <div>
                <h2 className="text-base font-semibold text-white">Upload a dataset</h2>
                <p className="mt-0.5 text-xs text-slate-500">CSV format · 10 MB maximum</p>
              </div>
            </div>

            <form className="mt-6" onSubmit={handleUpload}>
              <label
                htmlFor="dataset-file"
                className="focus-ring flex cursor-pointer flex-col items-center rounded-xl border border-dashed border-slate-600 bg-slate-950/40 px-4 py-7 text-center transition hover:border-emerald-300/60 hover:bg-emerald-300/[0.025]"
              >
                <span className="flex h-11 w-11 items-center justify-center rounded-full bg-slate-800 text-[#83dcca]">
                  <svg viewBox="0 0 24 24" width="22" height="22" fill="none" aria-hidden="true">
                    <path d="M12 15V4m0 0L8 8m4-4 4 4M5 14v5h14v-5" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" />
                  </svg>
                </span>
                <span className="mt-4 text-sm font-semibold text-slate-200">Choose a CSV file</span>
                <span className="mt-1 text-xs text-slate-500">Browse from your computer</span>
                <input
                  ref={fileInputRef}
                  id="dataset-file"
                  name="file"
                  type="file"
                  accept=".csv,text/csv"
                  className="sr-only"
                  onChange={handleFileChange}
                />
              </label>

              {selectedFile && (
                <div className="mt-4 flex items-center justify-between gap-3 rounded-lg border border-slate-700 bg-slate-950/50 px-3 py-3">
                  <div className="min-w-0">
                    <p className="truncate text-xs font-semibold text-slate-200">{selectedFile.name}</p>
                    <p className="mt-1 text-[11px] text-slate-500">{formatBytes(selectedFile.size)}</p>
                  </div>
                  <button
                    type="button"
                    className="text-xs text-slate-400 underline underline-offset-4 hover:text-white"
                    onClick={() => {
                      setSelectedFile(null);
                      if (fileInputRef.current) fileInputRef.current.value = "";
                    }}
                  >
                    Remove
                  </button>
                </div>
              )}

              <button
                type="submit"
                className="primary-button mt-4 w-full focus-ring"
                disabled={!selectedFile || isUploading}
              >
                {isUploading ? "Uploading dataset..." : "Upload dataset"}
                {!isUploading && (
                  <svg viewBox="0 0 24 24" width="15" height="15" fill="none" aria-hidden="true">
                    <path d="M5 12h14m-6-6 6 6-6 6" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" />
                  </svg>
                )}
              </button>
            </form>

            <div className="mt-6 border-t border-slate-800 pt-5">
              <p className="text-xs font-semibold text-slate-300">Upload safeguards</p>
              <ul className="mt-3 space-y-2 text-xs leading-5 text-slate-500">
                <li className="flex gap-2"><span className="text-[#64e5c1]">✓</span> CSV extension and content validation</li>
                <li className="flex gap-2"><span className="text-[#64e5c1]">✓</span> 10 MB, 100,000-row and 200-column limits</li>
                <li className="flex gap-2"><span className="text-[#64e5c1]">✓</span> Original file retained with generated storage name</li>
              </ul>
            </div>
          </aside>
        </section>

        <div className="mt-6">
          <QualityReportPanel
            report={qualityReport}
            isLoading={isLoadingQuality}
            error={qualityError}
          />
        </div>

        <div className="mt-6">
          <AnomalyReportPanel
            report={anomalyReport}
            dataset={selectedDataset}
            isLoading={isLoadingAnomalies}
            error={anomalyError}
            selectedDetectors={selectedDetectors}
            onToggleDetector={toggleAnomalyDetector}
            parameters={anomalyParameters}
            onParameterChange={updateAnomalyParameter}
            onRun={() => selectedDataset && void runAnomalyAssessment(selectedDataset)}
          />
        </div>

        <div className="mt-6">
          <CleaningPanel key={selectedDataset?.id ?? "no-dataset"} dataset={selectedDataset} />
        </div>

        <footer className="mt-10 flex flex-wrap items-center justify-between gap-2 border-t border-slate-800/80 pt-5 text-[11px] text-slate-600">
          <p>DataSentry · Research prototype · Explainable quality assessment</p>
          <p>Original files are preserved; no automatic cleaning is performed.</p>
        </footer>
      </main>
    </div>
  );
}
