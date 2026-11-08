"use client";

import { useEffect, useMemo, useState } from "react";
import {
  applyDatasetCleaning,
  getCleaningRecommendations,
  getDatasetVersionQualityComparison,
  getDatasetVersions,
  previewDatasetCleaning,
  type CleaningApplyResult,
  type CleaningOperationName,
  type CleaningPreview,
  type CleaningRecommendation,
  type CleaningRequest,
  type Dataset,
  type DatasetVersion,
  type QualityVersionComparison,
} from "@/lib/api";

function recommendationKey(item: CleaningRecommendation): string {
  return item.operation + ":" + (item.column ?? "*");
}

function number(value: number): string {
  return new Intl.NumberFormat().format(value);
}

function operationLabel(operation: CleaningOperationName): string {
  const labels: Record<CleaningOperationName, string> = {
    drop_exact_duplicates: "Remove exact duplicate rows",
    fill_numeric_median: "Fill missing numeric values with median",
    fill_categorical_mode: "Fill missing categories with mode",
    trim_whitespace: "Trim leading and trailing whitespace",
    lowercase_categories: "Normalize category text to lowercase",
  };
  return labels[operation];
}

function riskClass(risk: CleaningRecommendation["risk"]): string {
  if (risk === "high") return "border-rose-400/20 bg-rose-400/[0.08] text-rose-200";
  if (risk === "medium") return "border-amber-300/20 bg-amber-300/[0.08] text-amber-100";
  return "border-emerald-300/15 bg-emerald-300/[0.06] text-emerald-100";
}

export default function CleaningPanel({ dataset }: { dataset: Dataset | null }) {
  const [recommendations, setRecommendations] = useState<CleaningRecommendation[]>([]);
  const [versions, setVersions] = useState<DatasetVersion[]>([]);
  const [baseVersionId, setBaseVersionId] = useState<number | null>(null);
  const [selectedKeys, setSelectedKeys] = useState<string[]>([]);
  const [preview, setPreview] = useState<CleaningPreview | null>(null);
  const [applied, setApplied] = useState<CleaningApplyResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [isLoadingRecommendations, setIsLoadingRecommendations] = useState(true);
  const [isLoadingVersions, setIsLoadingVersions] = useState(true);
  const [isPreviewing, setIsPreviewing] = useState(false);
  const [isApplying, setIsApplying] = useState(false);
  const [previewReviewed, setPreviewReviewed] = useState(false);
  const [comparison, setComparison] = useState<QualityVersionComparison | null>(null);
  const [comparisonError, setComparisonError] = useState<string | null>(null);
  const [isLoadingComparison, setIsLoadingComparison] = useState(false);

  useEffect(() => {
    if (!dataset) return;

    let active = true;
    void getDatasetVersions(dataset.id)
      .then((items) => {
        if (active) setVersions(items);
      })
      .catch((reason: unknown) => {
        if (active) {
          setError(reason instanceof Error ? reason.message : "Could not load version history.");
        }
      })
      .finally(() => {
        if (active) setIsLoadingVersions(false);
      });

    return () => {
      active = false;
    };
  }, [dataset]);

  useEffect(() => {
    if (!dataset) return;
    let active = true;

    void getCleaningRecommendations(dataset.id, baseVersionId)
      .then((result) => {
        if (!active) return;
        setRecommendations(result.recommendations);
        setSelectedKeys(
          result.recommendations
            .filter((item) => item.recommended)
            .map(recommendationKey),
        );
      })
      .catch((reason: unknown) => {
        if (active) {
          setError(reason instanceof Error ? reason.message : "Could not load cleaning recommendations.");
          setRecommendations([]);
          setSelectedKeys([]);
        }
      })
      .finally(() => {
        if (active) setIsLoadingRecommendations(false);
      });

    return () => {
      active = false;
    };
  }, [dataset, baseVersionId]);

  const datasetId = dataset?.id;

  useEffect(() => {
    if (datasetId === undefined || baseVersionId === null) return;
    let active = true;
    void getDatasetVersionQualityComparison(datasetId, baseVersionId)
      .then((result) => {
        if (active) {
          setComparison(result);
          setComparisonError(null);
        }
      })
      .catch((reason: unknown) => {
        if (active) {
          setComparison(null);
          setComparisonError(
            reason instanceof Error ? reason.message : "Could not compare dataset quality.",
          );
        }
      })
      .finally(() => {
        if (active) setIsLoadingComparison(false);
      });
    return () => {
      active = false;
    };
  }, [datasetId, baseVersionId]);

  const selectedRecommendations = useMemo(
    () => recommendations.filter((item) => selectedKeys.includes(recommendationKey(item))),
    [recommendations, selectedKeys],
  );

  const request = useMemo<CleaningRequest>(() => ({
    base_version_id: baseVersionId,
    drop_exact_duplicates: selectedRecommendations.some(
      (item) => item.operation === "drop_exact_duplicates",
    ),
    fill_numeric_median: selectedRecommendations
      .filter((item) => item.operation === "fill_numeric_median" && item.column)
      .map((item) => item.column as string),
    fill_categorical_mode: selectedRecommendations
      .filter((item) => item.operation === "fill_categorical_mode" && item.column)
      .map((item) => item.column as string),
    trim_whitespace: selectedRecommendations
      .filter((item) => item.operation === "trim_whitespace" && item.column)
      .map((item) => item.column as string),
    lowercase_categories: selectedRecommendations
      .filter((item) => item.operation === "lowercase_categories" && item.column)
      .map((item) => item.column as string),
  }), [baseVersionId, selectedRecommendations]);

  function changeBaseVersion(nextVersionId: number | null) {
    setIsLoadingRecommendations(true);
    setBaseVersionId(nextVersionId);
    setComparison(null);
    setComparisonError(null);
    setIsLoadingComparison(nextVersionId !== null);
    setPreview(null);
    setPreviewReviewed(false);
    setApplied(null);
    setError(null);
  }

  function toggleRecommendation(item: CleaningRecommendation) {
    const key = recommendationKey(item);
    setSelectedKeys((current) =>
      current.includes(key) ? current.filter((value) => value !== key) : [...current, key],
    );
    setPreview(null);
    setPreviewReviewed(false);
    setApplied(null);
  }

  async function handlePreview() {
    if (!dataset || selectedRecommendations.length === 0) return;
    setIsPreviewing(true);
    setError(null);
    setPreview(null);
    setPreviewReviewed(false);
    setApplied(null);
    try {
      const result = await previewDatasetCleaning(dataset.id, request);
      setPreview(result);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "The cleaning preview failed.");
    } finally {
      setIsPreviewing(false);
    }
  }

  async function handleApply() {
    if (!dataset || !preview || !preview.changed || !previewReviewed) return;
    setIsApplying(true);
    setError(null);
    try {
      const result = await applyDatasetCleaning(dataset.id, request);
      setApplied(result);
      setPreview(null);
      setPreviewReviewed(false);
      const updatedVersions = await getDatasetVersions(dataset.id);
      setVersions(updatedVersions);
      changeBaseVersion(result.version.id);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "The cleaned version could not be created.");
    } finally {
      setIsApplying(false);
    }
  }

  const canPreview = !!dataset && selectedRecommendations.length > 0 &&
    !isLoadingRecommendations && !isPreviewing && !isApplying;

  return (
    <section id="cleaning-workspace" className="surface overflow-hidden rounded-2xl">
      <div className="flex flex-wrap items-start justify-between gap-3 border-b border-slate-800 px-5 py-5 sm:px-6">
        <div>
          <p className="eyebrow">Safe cleaning · explicit approval</p>
          <h2 className="mt-2 text-lg font-semibold text-white">Cleaning recommendations & version history</h2>
          <p className="mt-1 text-xs text-slate-500">
            {dataset ? dataset.filename + " · original upload remains immutable" : "Select a dataset from the library to review suggested changes."}
          </p>
        </div>
        <span className="rounded-full border border-emerald-300/15 bg-emerald-300/[0.06] px-3 py-1 text-xs text-emerald-100">
          Preview before apply
        </span>
      </div>

      {!dataset ? (
        <div className="px-5 py-10 text-center text-sm text-slate-400">
          Choose “Review cleaning” beside a dataset to inspect recommendations and version history.
        </div>
      ) : (
        <>
          {baseVersionId !== null && (
            <div className="border-b border-slate-800 p-5 sm:p-6" aria-live="polite">
              <div className="flex flex-wrap items-start justify-between gap-3">
                <div>
                  <p className="eyebrow">Quality impact</p>
                  <h3 className="mt-2 text-base font-semibold text-white">
                    Version {comparison?.after.version_number ?? versions.find((item) => item.id === baseVersionId)?.version_number ?? ""}
                    {" "}versus original upload
                  </h3>
                  <p className="mt-1 text-xs text-slate-500">
                    The same inference-based DQS rules are recalculated for both files.
                  </p>
                </div>
                {comparison && (
                  <span className="rounded-full border border-slate-700 bg-slate-950/40 px-3 py-1 text-xs text-slate-300">
                    {number(comparison.before.issue_count)} → {number(comparison.after.issue_count)} findings
                  </span>
                )}
              </div>
              {isLoadingComparison ? (
                <p className="mt-4 text-sm text-slate-400">Recalculating quality for both versions...</p>
              ) : comparisonError ? (
                <p role="alert" className="mt-4 text-sm text-rose-200">{comparisonError}</p>
              ) : comparison ? (
                <>
                  <div className="mt-4 grid gap-3 sm:grid-cols-3">
                    <div className="rounded-xl border border-slate-800 bg-slate-950/35 p-4">
                      <p className="text-xs text-slate-500">Original DQS</p>
                      <p className="mt-2 text-2xl font-semibold text-white">
                        {comparison.before.overall === null ? "N/A" : comparison.before.overall.toFixed(2)}
                      </p>
                    </div>
                    <div className="rounded-xl border border-slate-800 bg-slate-950/35 p-4">
                      <p className="text-xs text-slate-500">Version DQS</p>
                      <p className="mt-2 text-2xl font-semibold text-white">
                        {comparison.after.overall === null ? "N/A" : comparison.after.overall.toFixed(2)}
                      </p>
                    </div>
                    <div className="rounded-xl border border-slate-800 bg-slate-950/35 p-4">
                      <p className="text-xs text-slate-500">DQS change</p>
                      <p className={
                        "mt-2 text-2xl font-semibold " +
                        (comparison.delta.overall === null
                          ? "text-slate-300"
                          : comparison.delta.overall > 0
                            ? "text-emerald-200"
                            : comparison.delta.overall < 0
                              ? "text-rose-200"
                              : "text-slate-100")
                      }>
                        {comparison.delta.overall === null
                          ? "N/A"
                          : (comparison.delta.overall > 0 ? "+" : "") + comparison.delta.overall.toFixed(2)}
                      </p>
                    </div>
                  </div>
                  <div className="mt-4 overflow-x-auto rounded-xl border border-slate-800">
                    <table className="w-full min-w-[560px] text-left text-xs">
                      <thead className="bg-slate-950/60 text-slate-400">
                        <tr>
                          <th className="px-3 py-3 font-semibold">DQS component</th>
                          <th className="px-3 py-3 font-semibold">Original</th>
                          <th className="px-3 py-3 font-semibold">Version</th>
                          <th className="px-3 py-3 font-semibold">Change</th>
                        </tr>
                      </thead>
                      <tbody>
                        {([
                          ["Completeness", "completeness"],
                          ["Validity", "validity"],
                          ["Uniqueness", "uniqueness"],
                          ["Consistency", "consistency"],
                        ] as const).map(([label, key]) => {
                          const change = comparison.delta.components[key].score_delta;
                          return (
                            <tr key={key} className="border-t border-slate-800 text-slate-300">
                              <th className="px-3 py-3 font-medium text-slate-200">{label}</th>
                              <td className="px-3 py-3">
                                {comparison.before.components[key].score === null
                                  ? "N/A"
                                  : comparison.before.components[key].score?.toFixed(2)}
                              </td>
                              <td className="px-3 py-3">
                                {comparison.after.components[key].score === null
                                  ? "N/A"
                                  : comparison.after.components[key].score?.toFixed(2)}
                              </td>
                              <td className="px-3 py-3">
                                {change === null ? "Not comparable" : (change > 0 ? "+" : "") + change.toFixed(2)}
                              </td>
                            </tr>
                          );
                        })}
                      </tbody>
                    </table>
                  </div>
                  <p className="mt-3 text-xs text-slate-500">
                    Rows: {number(comparison.before.shape.rows)} → {number(comparison.after.shape.rows)}
                    {" · "}Columns: {number(comparison.before.shape.columns)} → {number(comparison.after.shape.columns)}
                    {" · "}Findings: {number(comparison.before.issue_count)} → {number(comparison.after.issue_count)}
                  </p>
                  <ul className="mt-2 space-y-1 text-[11px] leading-5 text-slate-500">
                    {comparison.method_notes.slice(1, 4).map((note) => <li key={note}>{note}</li>)}
                  </ul>
                </>
              ) : null}
            </div>
          )}

          <div className="grid gap-5 border-b border-slate-800 p-5 sm:p-6">
            <div className="flex flex-wrap items-end justify-between gap-3">
              <label className="block min-w-[240px]">
                <span className="text-xs font-semibold uppercase tracking-wider text-slate-400">Base dataset version</span>
                <select
                  value={baseVersionId === null ? "original" : String(baseVersionId)}
                  onChange={(event) => {
                    const value = event.currentTarget.value;
                    changeBaseVersion(value === "original" ? null : Number(value));
                  }}
                  disabled={isApplying || isPreviewing}
                  className="mt-2 w-full rounded-xl border border-slate-700 bg-slate-950 px-3 py-2.5 text-sm text-slate-200"
                >
                  <option value="original">Original upload</option>
                  {versions.map((version) => (
                    <option key={version.id} value={String(version.id)}>
                      Version {version.version_number} · {number(version.rows_count)} rows
                    </option>
                  ))}
                </select>
              </label>
              <p className="text-xs text-slate-500">
                {isLoadingVersions ? "Loading version history..." : number(versions.length) + " immutable version(s)"}
              </p>
            </div>

            <div>
              <div className="flex flex-wrap items-center justify-between gap-2">
                <div>
                  <h3 className="text-sm font-semibold text-white">Recommended operations</h3>
                  <p className="mt-1 text-xs text-slate-500">
                    Recommendations are advisory. Select only changes justified by your data context.
                  </p>
                </div>
                <span className="text-xs text-slate-500">
                  {number(selectedRecommendations.length)} selected
                </span>
              </div>

              {isLoadingRecommendations ? (
                <div className="mt-4 rounded-xl border border-slate-800 bg-slate-950/35 p-5 text-sm text-slate-400" aria-live="polite">
                  Inspecting the selected base version...
                </div>
              ) : recommendations.length === 0 ? (
                <div className="mt-4 rounded-xl border border-slate-800 bg-slate-950/35 p-5 text-sm text-slate-400">
                  No supported cleaning recommendations were found for this version.
                </div>
              ) : (
                <ul className="mt-4 grid gap-3 lg:grid-cols-2">
                  {recommendations.map((item) => {
                    const key = recommendationKey(item);
                    const checked = selectedKeys.includes(key);
                    return (
                      <li key={key} className="rounded-xl border border-slate-800 bg-slate-950/35 p-4">
                        <label className="flex cursor-pointer items-start gap-3">
                          <input
                            type="checkbox"
                            checked={checked}
                            onChange={() => toggleRecommendation(item)}
                            disabled={isPreviewing || isApplying}
                            className="mt-1 accent-emerald-300"
                          />
                          <span className="min-w-0 flex-1">
                            <span className="flex flex-wrap items-center gap-2">
                              <span className="text-sm font-semibold text-slate-100">
                                {operationLabel(item.operation)}
                              </span>
                              {item.column && (
                                <span className="rounded-md bg-slate-800 px-2 py-0.5 font-mono text-[10px] text-slate-300">
                                  {item.column}
                                </span>
                              )}
                            </span>
                            <span className="mt-2 flex flex-wrap items-center gap-2">
                              <span className={"rounded-full border px-2 py-0.5 text-[10px] uppercase tracking-wider " + riskClass(item.risk)}>
                                {item.risk} risk
                              </span>
                              <span className="text-[11px] text-slate-500">
                                {number(item.affected_count)} affected
                              </span>
                              {!item.recommended && (
                                <span className="text-[10px] font-semibold text-amber-200">Manual review only</span>
                              )}
                            </span>
                            <span className="mt-2 block text-xs leading-5 text-slate-400">{item.reason}</span>
                          </span>
                        </label>
                      </li>
                    );
                  })}
                </ul>
              )}

              <button
                type="button"
                className="primary-button mt-5 focus-ring"
                onClick={() => void handlePreview()}
                disabled={!canPreview}
              >
                {isPreviewing ? "Generating read-only preview..." : "Preview selected changes"}
              </button>
            </div>
          </div>

          {error && (
            <div role="alert" className="mx-5 mt-5 rounded-xl border border-rose-400/20 bg-rose-400/[0.07] px-4 py-3 text-sm text-rose-100 sm:mx-6">
              {error}
            </div>
          )}

          {preview && (
            <div className="border-b border-slate-800 p-5 sm:p-6" aria-live="polite">
              <div className="flex flex-wrap items-start justify-between gap-3">
                <div>
                  <p className="eyebrow">Read-only preview</p>
                  <h3 className="mt-2 text-base font-semibold text-white">Review the proposed result</h3>
                  <p className="mt-1 text-xs text-slate-500">No file or database version has been created yet.</p>
                </div>
                <span className="rounded-full border border-amber-300/20 bg-amber-300/[0.06] px-3 py-1 text-xs text-amber-100">
                  {preview.changed ? "Changes detected" : "No changes"}
                </span>
              </div>

              <div className="mt-4 grid gap-3 sm:grid-cols-3">
                <div className="rounded-xl border border-slate-800 bg-slate-950/35 p-4">
                  <p className="text-xs text-slate-500">Rows before → after</p>
                  <p className="mt-2 text-xl font-semibold text-white">
                    {number(preview.rows_before)} <span className="text-slate-500">→</span> {number(preview.rows_after)}
                  </p>
                </div>
                <div className="rounded-xl border border-slate-800 bg-slate-950/35 p-4">
                  <p className="text-xs text-slate-500">Changed rows</p>
                  <p className="mt-2 text-xl font-semibold text-white">{number(preview.preview.changed_row_count)}</p>
                </div>
                <div className="rounded-xl border border-slate-800 bg-slate-950/35 p-4">
                  <p className="text-xs text-slate-500">Removed duplicates</p>
                  <p className="mt-2 text-xl font-semibold text-white">{number(preview.preview.removed_row_count)}</p>
                </div>
              </div>

              <div className="mt-4 rounded-xl border border-slate-800 bg-slate-950/35 p-4">
                <h4 className="text-xs font-semibold uppercase tracking-wider text-slate-400">Operation impact</h4>
                <ul className="mt-3 space-y-2">
                  {preview.preview.operations.map((operation, index) => (
                    <li key={operation.operation + ":" + index} className="flex flex-wrap items-center justify-between gap-2 text-xs">
                      <span className="text-slate-300">{operationLabel(operation.operation)}</span>
                      <span className="text-slate-500">
                        {operation.affected_rows !== undefined
                          ? number(operation.affected_rows) + " rows"
                          : number(operation.affected_cells ?? 0) + " cells"}
                        {operation.imputation_value ? " · value " + operation.imputation_value : ""}
                      </span>
                    </li>
                  ))}
                </ul>
              </div>

              <div className="mt-4">
                <h4 className="text-xs font-semibold uppercase tracking-wider text-slate-400">Before / after row evidence</h4>
                {preview.preview.sample_rows.length === 0 ? (
                  <p className="mt-2 text-sm text-slate-400">No changed rows were found in the preview.</p>
                ) : (
                  <ul className="mt-3 space-y-2">
                    {preview.preview.sample_rows.map((row) => (
                      <li key={row.row_number} className="rounded-lg border border-slate-800 bg-slate-950/35 p-3">
                        <div className="flex flex-wrap items-center justify-between gap-2">
                          <span className="text-xs font-semibold text-slate-200">Data row {row.row_number}</span>
                          {row.removed && <span className="text-[10px] uppercase tracking-wider text-rose-200">Removed duplicate</span>}
                        </div>
                        <ul className="mt-2 space-y-1">
                          {row.changes.map((change, index) => (
                            <li key={change.column + ":" + index} className="grid gap-1 text-[11px] sm:grid-cols-[110px_1fr]">
                              <span className="font-mono text-slate-400">{change.column}</span>
                              <span className="text-slate-300">
                                <span className="text-rose-200">{change.before ?? "∅"}</span>
                                <span className="px-2 text-slate-600">→</span>
                                <span className="text-emerald-200">{change.after ?? "∅"}</span>
                              </span>
                            </li>
                          ))}
                        </ul>
                      </li>
                    ))}
                  </ul>
                )}
                {preview.preview.sample_truncated && (
                  <p className="mt-2 text-[11px] text-slate-500">Evidence is truncated by the API to keep the response bounded.</p>
                )}
              </div>

              <div className="mt-5 rounded-xl border border-amber-300/20 bg-amber-300/[0.05] p-4">
                <label className="flex items-start gap-3 text-sm text-amber-50">
                  <input
                    type="checkbox"
                    checked={previewReviewed}
                    onChange={(event) => setPreviewReviewed(event.currentTarget.checked)}
                    disabled={!preview.changed || isApplying}
                    className="mt-1 accent-emerald-300"
                  />
                  <span>
                    I reviewed the proposed row and cell changes and understand that imputation, normalization, or duplicate removal can affect downstream analysis.
                  </span>
                </label>
                <button
                  type="button"
                  className="primary-button mt-4 focus-ring"
                  onClick={() => void handleApply()}
                  disabled={!preview.changed || !previewReviewed || isApplying}
                >
                  {isApplying ? "Creating immutable version..." : "Confirm and create new dataset version"}
                </button>
              </div>
            </div>
          )}

          {applied && (
            <div className="border-b border-slate-800 p-5 sm:p-6" role="status">
              <div className="rounded-xl border border-emerald-300/20 bg-emerald-300/[0.06] p-4">
                <p className="text-sm font-semibold text-emerald-100">
                  Version {applied.version.version_number} created successfully
                </p>
                <p className="mt-2 text-xs leading-5 text-slate-300">
                  {number(applied.version.rows_count)} rows · SHA-256 {applied.version.sha256_hash.slice(0, 16)}… · Original upload preserved.
                </p>
                <p className="mt-1 text-xs text-slate-500">
                  This version is now selected as the base for any further cleaning.
                </p>
              </div>
            </div>
          )}

          <div className="p-5 sm:p-6">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <div>
                <h3 className="text-sm font-semibold text-white">Immutable version history</h3>
                <p className="mt-1 text-xs text-slate-500">Each apply creates a new file and records its parent; earlier versions are retained.</p>
              </div>
              <span className="text-xs text-slate-500">{number(versions.length)} version(s)</span>
            </div>
            {versions.length === 0 ? (
              <p className="mt-4 rounded-xl border border-slate-800 bg-slate-950/35 p-4 text-sm text-slate-400">
                No cleaned versions exist yet. Preview and explicitly apply a change to create the first version.
              </p>
            ) : (
              <ol className="mt-4 space-y-3">
                {versions.map((version) => (
                  <li key={version.id} className="flex flex-wrap items-center justify-between gap-3 rounded-xl border border-slate-800 bg-slate-950/35 p-4">
                    <div>
                      <p className="text-sm font-semibold text-slate-100">
                        Version {version.version_number}
                        {version.id === baseVersionId && <span className="ml-2 text-[10px] font-medium uppercase tracking-wider text-emerald-200">Selected base</span>}
                      </p>
                      <p className="mt-1 text-xs text-slate-500">
                        {number(version.rows_count)} rows × {number(version.columns_count)} columns · Parent {version.parent_version_id ?? "original upload"}
                      </p>
                      <p className="mt-1 font-mono text-[10px] text-slate-600">{version.sha256_hash}</p>
                    </div>
                    <button
                      type="button"
                      className="secondary-button focus-ring text-xs"
                      onClick={() => {
                        changeBaseVersion(version.id);
                      }}
                      disabled={isApplying || isPreviewing || version.id === baseVersionId}
                    >
                      Use as base
                    </button>
                  </li>
                ))}
              </ol>
            )}
          </div>

          <div className="border-t border-slate-800 px-5 py-4 sm:px-6">
            <p className="text-[11px] leading-5 text-slate-500">
              The selected version DQS is recalculated against the original upload using the same rules. Full numeric distribution and correlation comparisons are not yet included. Review all transformations before using a derived version in research.
            </p>
          </div>
        </>
      )}
    </section>
  );
}
