"use client";

import {
  type ChangeEvent,
  type FormEvent,
  useCallback,
  useEffect,
  useRef,
  useState,
} from "react";
import {
  API_DOCS_URL,
  getDatasetQuality,
  getDatasets,
  getOverview,
  uploadDataset,
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

export default function Home() {
  const [overview, setOverview] = useState<Overview | null>(null);
  const [datasets, setDatasets] = useState<Dataset[]>([]);
  const [selectedDatasetId, setSelectedDatasetId] = useState<number | null>(null);
  const [qualityReport, setQualityReport] = useState<QualityReport | null>(null);
  const [qualityError, setQualityError] = useState<string | null>(null);
  const [isLoadingQuality, setIsLoadingQuality] = useState(false);
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
                          <button
                            type="button"
                            className="secondary-button focus-ring whitespace-nowrap text-[11px]"
                            onClick={() => void runQualityAssessment(dataset)}
                            disabled={isLoadingQuality}
                            aria-label={"Run quality check for " + dataset.filename}
                          >
                            {isLoadingQuality && selectedDatasetId === dataset.id
                              ? "Analyzing..."
                              : selectedDatasetId === dataset.id && qualityReport
                                ? "Report open"
                                : "Run quality check"}
                          </button>
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

        <footer className="mt-10 flex flex-wrap items-center justify-between gap-2 border-t border-slate-800/80 pt-5 text-[11px] text-slate-600">
          <p>DataSentry · Research prototype · Explainable quality assessment</p>
          <p>Original files are preserved; no automatic cleaning is performed.</p>
        </footer>
      </main>
    </div>
  );
}
