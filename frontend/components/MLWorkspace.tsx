"use client";

import { useEffect, useState } from "react";
import {
  assessDatasetReadiness,
  getDatasetProfile,
  trainBaselineModel,
  type BaselineModelReport,
  type Dataset,
  type DatasetProfile,
  type MLReadinessReport,
  type MLTaskType,
} from "@/lib/api";

function formatMetric(value: number | undefined): string {
  return value === undefined || !Number.isFinite(value) ? "—" : value.toFixed(3);
}

function statusLabel(status: MLReadinessReport["readiness_status"]): string {
  if (status === "blocked") return "Blocked";
  if (status === "review_required") return "Review required";
  return "Ready for baseline";
}

export default function MLWorkspace({ dataset }: { dataset: Dataset | null }) {
  const datasetId = dataset?.id;
  const [profile, setProfile] = useState<DatasetProfile | null>(null);
  const [profileError, setProfileError] = useState<string | null>(null);
  const [isLoadingProfile, setIsLoadingProfile] = useState(true);
  const [targetColumn, setTargetColumn] = useState("");
  const [taskType, setTaskType] = useState<MLTaskType>("classification");
  const [selectedFeatures, setSelectedFeatures] = useState<string[]>([]);
  const [testSize, setTestSize] = useState("0.25");
  const [randomState, setRandomState] = useState("42");
  const [readiness, setReadiness] = useState<MLReadinessReport | null>(null);
  const [readinessError, setReadinessError] = useState<string | null>(null);
  const [modelReport, setModelReport] = useState<BaselineModelReport | null>(null);
  const [modelError, setModelError] = useState<string | null>(null);
  const [isAssessing, setIsAssessing] = useState(false);
  const [isTraining, setIsTraining] = useState(false);
  const [reloadKey, setReloadKey] = useState(0);

  useEffect(() => {
    if (datasetId === undefined) return;
    let active = true;
    void getDatasetProfile(datasetId)
      .then((result) => {
        if (!active) return;
        setProfile(result);
        const firstColumn = result.columns[0]?.name ?? "";
        setTargetColumn(firstColumn);
        setSelectedFeatures(result.columns
          .map((column) => column.name)
          .filter((name) => name !== firstColumn));
      })
      .catch((error: unknown) => {
        if (!active) return;
        setProfileError(error instanceof Error ? error.message : "Could not load dataset columns.");
      })
      .finally(() => {
        if (active) setIsLoadingProfile(false);
      });
    return () => {
      active = false;
    };
  }, [datasetId, reloadKey]);

  function clearResults() {
    setReadiness(null);
    setReadinessError(null);
    setModelReport(null);
    setModelError(null);
  }

  function changeTarget(value: string) {
    setTargetColumn(value);
    setSelectedFeatures((current) => current.filter((name) => name !== value));
    clearResults();
  }

  function toggleFeature(name: string) {
    setSelectedFeatures((current) => current.includes(name)
      ? current.filter((item) => item !== name)
      : [...current, name]);
    clearResults();
  }

  async function runReadiness() {
    if (datasetId === undefined || !targetColumn || selectedFeatures.length === 0) return;
    setIsAssessing(true);
    clearResults();
    try {
      const result = await assessDatasetReadiness(datasetId, {
        target_column: targetColumn,
        task_type: taskType,
        feature_columns: selectedFeatures,
      });
      setReadiness(result);
    } catch (error) {
      setReadinessError(error instanceof Error ? error.message : "ML-readiness assessment failed.");
    } finally {
      setIsAssessing(false);
    }
  }

  async function runBaseline() {
    if (datasetId === undefined || !targetColumn || selectedFeatures.length === 0) return;
    if (!readiness || readiness.readiness_status === "blocked") return;
    const parsedTestSize = Number(testSize);
    const parsedSeed = Number(randomState);
    if (!Number.isFinite(parsedTestSize) || parsedTestSize <= 0.1 || parsedTestSize >= 0.5) {
      setModelError("Test fraction must be greater than 0.10 and less than 0.50.");
      return;
    }
    if (!Number.isInteger(parsedSeed) || parsedSeed < 0 || parsedSeed > 4294967295) {
      setModelError("Random seed must be an integer from 0 to 4,294,967,295.");
      return;
    }
    setIsTraining(true);
    setModelReport(null);
    setModelError(null);
    try {
      const result = await trainBaselineModel(datasetId, {
        target_column: targetColumn,
        task_type: taskType,
        feature_columns: selectedFeatures,
        test_size: parsedTestSize,
        random_state: parsedSeed,
      });
      setModelReport(result);
    } catch (error) {
      setModelError(error instanceof Error ? error.message : "Baseline training failed.");
    } finally {
      setIsTraining(false);
    }
  }

  const featureColumns = profile?.columns.filter((column) => column.name !== targetColumn) ?? [];
  const canAssess = Boolean(datasetId !== undefined && targetColumn && selectedFeatures.length && !isAssessing && !isTraining);
  const canTrain = Boolean(canAssess && readiness && readiness.readiness_status !== "blocked" && !isTraining);

  if (!dataset) {
    return (
      <section id="ml-workspace" className="surface rounded-2xl p-6">
        <p className="eyebrow">Machine learning</p>
        <h2 className="mt-2 text-lg font-semibold text-white">ML readiness and baseline models</h2>
        <p className="mt-2 text-sm text-slate-400">Select a dataset from the library to inspect its target, feature risks, and baseline performance.</p>
      </section>
    );
  }

  return (
    <section id="ml-workspace" className="surface overflow-hidden rounded-2xl">
      <div className="flex flex-wrap items-start justify-between gap-3 border-b border-slate-800 px-5 py-5 sm:px-6">
        <div>
          <p className="eyebrow">Machine learning · diagnostic before training</p>
          <h2 className="mt-2 text-lg font-semibold text-white">ML readiness and baseline models</h2>
          <p className="mt-1 text-xs text-slate-500">{dataset.filename} · {dataset.rows_count.toLocaleString()} rows × {dataset.columns_count.toLocaleString()} columns</p>
        </div>
        <span className="rounded-full border border-emerald-300/20 bg-emerald-300/[0.07] px-3 py-1 text-[10px] font-semibold uppercase tracking-wider text-emerald-100">
          Source remains read-only
        </span>
      </div>

      <div className="grid gap-5 p-5 sm:p-6 xl:grid-cols-[minmax(0,0.9fr)_minmax(0,1.1fr)]">
        <div className="space-y-4">
          <div>
            <label htmlFor="ml-task" className="mb-2 block text-xs font-semibold text-slate-300">Prediction task</label>
            <select id="ml-task" className="w-full rounded-lg border border-slate-700 bg-slate-950/60 px-3 py-2 text-sm text-white outline-none focus:border-emerald-300" value={taskType} onChange={(event) => { setTaskType(event.target.value as MLTaskType); clearResults(); }}>
              <option value="classification">Classification</option>
              <option value="regression">Regression</option>
            </select>
          </div>

          <div>
            <label htmlFor="ml-target" className="mb-2 block text-xs font-semibold text-slate-300">Target column</label>
            {isLoadingProfile ? (
              <p className="rounded-lg border border-slate-800 bg-slate-950/40 px-3 py-3 text-xs text-slate-500">Loading dataset columns…</p>
            ) : profileError ? (
              <div className="rounded-lg border border-rose-300/20 bg-rose-300/[0.06] p-3 text-xs text-rose-100">
                <p role="alert">{profileError}</p>
                <button type="button" className="mt-2 underline" onClick={() => { setProfileError(null); setIsLoadingProfile(true); setReloadKey((value) => value + 1); }}>Retry column loading</button>
              </div>
            ) : (
              <select id="ml-target" className="w-full rounded-lg border border-slate-700 bg-slate-950/60 px-3 py-2 text-sm text-white outline-none focus:border-emerald-300" value={targetColumn} onChange={(event) => changeTarget(event.target.value)}>
                {profile?.columns.map((column) => (
                  <option key={column.name} value={column.name}>{column.name} · {column.inferred_type}</option>
                ))}
              </select>
            )}
          </div>

          <div>
            <div className="mb-2 flex items-center justify-between gap-2">
              <p className="text-xs font-semibold text-slate-300">Input features</p>
              <span className="text-[10px] text-slate-500">{selectedFeatures.length} selected</span>
            </div>
            <div className="max-h-48 space-y-2 overflow-y-auto rounded-xl border border-slate-800 bg-slate-950/40 p-3">
              {featureColumns.map((column) => (
                <label key={column.name} className="flex cursor-pointer items-center justify-between gap-3 text-xs text-slate-300">
                  <span className="min-w-0 truncate">{column.name}<span className="ml-2 text-[10px] text-slate-500">{column.inferred_type}</span></span>
                  <input type="checkbox" checked={selectedFeatures.includes(column.name)} onChange={() => toggleFeature(column.name)} className="h-4 w-4 accent-emerald-300" />
                </label>
              ))}
              {featureColumns.length === 0 && <p className="text-xs text-slate-500">Choose a target to list the remaining feature columns.</p>}
            </div>
            <p className="mt-2 text-[10px] text-slate-500">The target is excluded from features. Select at least one input column.</p>
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div>
              <label htmlFor="ml-test-size" className="mb-2 block text-xs font-semibold text-slate-300">Test fraction</label>
              <input id="ml-test-size" type="number" min="0.11" max="0.49" step="0.05" value={testSize} onChange={(event) => { setTestSize(event.target.value); setModelReport(null); }} className="w-full rounded-lg border border-slate-700 bg-slate-950/60 px-3 py-2 text-sm text-white outline-none focus:border-emerald-300" />
            </div>
            <div>
              <label htmlFor="ml-seed" className="mb-2 block text-xs font-semibold text-slate-300">Random seed</label>
              <input id="ml-seed" type="number" min="0" max="4294967295" step="1" value={randomState} onChange={(event) => { setRandomState(event.target.value); setModelReport(null); }} className="w-full rounded-lg border border-slate-700 bg-slate-950/60 px-3 py-2 text-sm text-white outline-none focus:border-emerald-300" />
            </div>
          </div>

          <div className="flex flex-wrap gap-2">
            <button type="button" className="primary-button focus-ring" onClick={() => void runReadiness()} disabled={!canAssess || isLoadingProfile}>
              {isAssessing ? "Assessing…" : "Assess ML readiness"}
            </button>
            <button type="button" className="secondary-button focus-ring" onClick={() => void runBaseline()} disabled={!canTrain}>
              {isTraining ? "Training…" : "Train baseline"}
            </button>
          </div>
          <p className="text-[10px] leading-5 text-slate-500">Run readiness first. Warnings require review but do not automatically block training; explicit blockers do. Baseline preprocessing is fitted on training rows only.</p>
        </div>

        <div className="space-y-4">
          {readinessError && <p role="alert" className="rounded-xl border border-rose-300/20 bg-rose-300/[0.06] p-3 text-xs text-rose-100">{readinessError}</p>}
          {modelError && <p role="alert" className="rounded-xl border border-rose-300/20 bg-rose-300/[0.06] p-3 text-xs text-rose-100">{modelError}</p>}

          {!readiness && !isAssessing && !readinessError && (
            <div className="rounded-xl border border-slate-800 bg-slate-950/35 p-5">
              <p className="text-sm font-semibold text-slate-200">Readiness report</p>
              <p className="mt-2 text-xs leading-5 text-slate-500">Select a target and features, then assess target completeness, class balance, leakage indicators, duplicate split risks, redundancy, and dataset size.</p>
            </div>
          )}

          {readiness && (
            <div className="space-y-4">
              <div className="flex flex-wrap items-center justify-between gap-3 rounded-xl border border-slate-800 bg-slate-950/35 p-4">
                <div>
                  <p className="text-xs text-slate-400">Readiness status</p>
                  <p className="mt-1 text-base font-semibold text-white">{statusLabel(readiness.readiness_status)}</p>
                </div>
                <span className={"rounded-full px-3 py-1 text-[10px] font-semibold uppercase " + (readiness.readiness_status === "blocked" ? "bg-rose-300/10 text-rose-100" : readiness.readiness_status === "review_required" ? "bg-amber-300/10 text-amber-100" : "bg-emerald-300/10 text-emerald-100")}>
                  {readiness.readiness_status.replace(/_/g, " ")}
                </span>
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div className="rounded-xl border border-slate-800 bg-slate-950/35 p-4">
                  <p className="text-[10px] uppercase tracking-wider text-slate-500">Target completeness</p>
                  <p className="mt-2 text-2xl font-semibold text-white">{readiness.target.completeness_pct.toFixed(1)}%</p>
                  <p className="mt-1 text-[10px] text-slate-500">{readiness.target.observed_count.toLocaleString()} observed · {readiness.target.missing_count.toLocaleString()} missing</p>
                </div>
                <div className="rounded-xl border border-slate-800 bg-slate-950/35 p-4">
                  <p className="text-[10px] uppercase tracking-wider text-slate-500">Duplicate split risk</p>
                  <p className="mt-2 text-2xl font-semibold text-white">{readiness.duplicate_split_risk.duplicate_rate_pct.toFixed(2)}%</p>
                  <p className="mt-1 text-[10px] text-slate-500">{readiness.duplicate_split_risk.duplicate_rows_after_first.toLocaleString()} repeated feature rows</p>
                </div>
                <div className="rounded-xl border border-slate-800 bg-slate-950/35 p-4">
                  <p className="text-[10px] uppercase tracking-wider text-slate-500">Leakage indicators</p>
                  <p className="mt-2 text-2xl font-semibold text-white">{readiness.leakage_indicators.length}</p>
                  <p className="mt-1 text-[10px] text-slate-500">Require feature provenance review</p>
                </div>
                <div className="rounded-xl border border-slate-800 bg-slate-950/35 p-4">
                  <p className="text-[10px] uppercase tracking-wider text-slate-500">Redundant feature pairs</p>
                  <p className="mt-2 text-2xl font-semibold text-white">{readiness.feature_redundancy.reported_pair_count}</p>
                  <p className="mt-1 text-[10px] text-slate-500">{readiness.dataset_size.rows_per_feature ?? "—"} rows per feature</p>
                </div>
              </div>

              {readiness.target.class_distribution && (
                <div className="rounded-xl border border-slate-800 bg-slate-950/35 p-4">
                  <h3 className="text-xs font-semibold text-slate-200">Class distribution</h3>
                  <div className="mt-3 space-y-2">
                    {readiness.target.class_distribution.map((item) => (
                      <div key={item.label} className="flex items-center gap-3 text-xs">
                        <span className="w-24 truncate text-slate-400">{item.label}</span>
                        <div className="h-2 flex-1 overflow-hidden rounded-full bg-slate-800">
                          <div className="h-full rounded-full bg-emerald-300" style={{ width: item.percentage + "%" }} />
                        </div>
                        <span className="w-16 text-right tabular-nums text-slate-300">{item.count} · {item.percentage.toFixed(1)}%</span>
                      </div>
                    ))}
                  </div>
                  {readiness.target.class_distribution_truncated && <p className="mt-2 text-[10px] text-slate-500">Only the highest-frequency classes are shown.</p>}
                </div>
              )}

              {(readiness.blockers.length > 0 || readiness.warnings.length > 0) && (
                <div className="rounded-xl border border-slate-800 bg-slate-950/35 p-4">
                  <h3 className="text-xs font-semibold text-slate-200">Findings requiring review</h3>
                  <ul className="mt-3 space-y-2">
                    {[...readiness.blockers, ...readiness.warnings].map((item, index) => (
                      <li key={item.code + index} className="text-xs leading-5 text-slate-400">
                        <span className={item.severity === "high" ? "font-semibold text-rose-200" : item.severity === "medium" ? "font-semibold text-amber-200" : "font-semibold text-slate-300"}>{item.severity.toUpperCase()} · </span>{item.message}
                      </li>
                    ))}
                  </ul>
                </div>
              )}

              <div className="rounded-xl border border-slate-800 bg-slate-950/35 p-4">
                <p className="text-xs font-semibold text-slate-200">Assessment provenance</p>
                <p className="mt-2 break-all font-mono text-[10px] text-slate-500">SHA-256 · {readiness.source_sha256 ?? "Unavailable"}</p>
                <p className="mt-1 text-[10px] text-slate-500">{readiness.software_versions.scikit_learn} · pandas {readiness.software_versions.pandas} · NumPy {readiness.software_versions.numpy}</p>
              </div>
            </div>
          )}

          {modelReport && (
            <div className="space-y-4 rounded-xl border border-emerald-300/20 bg-emerald-300/[0.035] p-4">
              <div className="flex flex-wrap items-start justify-between gap-2">
                <div>
                  <p className="text-xs font-semibold text-emerald-100">Baseline evaluation</p>
                  <h3 className="mt-1 text-sm font-semibold text-white">{modelReport.model === "logistic_regression" ? "Logistic Regression" : "Ridge Regression"}</h3>
                </div>
                <span className="rounded-full bg-emerald-300/10 px-2.5 py-1 text-[10px] text-emerald-100">Holdout metrics</span>
              </div>
              <div className="grid grid-cols-2 gap-3 sm:grid-cols-3">
                {(modelReport.task_type === "classification"
                  ? [["Accuracy", modelReport.metrics.accuracy], ["Balanced accuracy", modelReport.metrics.balanced_accuracy], ["Macro F1", modelReport.metrics.macro_f1], ["Macro precision", modelReport.metrics.macro_precision], ["Macro recall", modelReport.metrics.macro_recall], ["ROC AUC", modelReport.metrics.roc_auc ?? undefined]]
                  : [["MAE", modelReport.metrics.mae], ["RMSE", modelReport.metrics.rmse], ["R²", modelReport.metrics.r2]]
                ).map(([label, value]) => (
                  <div key={String(label)} className="rounded-lg border border-slate-800 bg-slate-950/50 p-3">
                    <p className="text-[10px] text-slate-500">{label}</p>
                    <p className="mt-1 text-lg font-semibold tabular-nums text-white">{formatMetric(value as number | undefined)}</p>
                  </div>
                ))}
              </div>
              {modelReport.metrics.confusion_matrix && (
                <div className="overflow-x-auto">
                  <p className="mb-2 text-xs font-semibold text-slate-300">Confusion matrix · rows actual, columns predicted</p>
                  <table className="min-w-full border-collapse text-xs">
                    <thead><tr><th className="p-2 text-left text-slate-500">Actual / predicted</th>{modelReport.metrics.confusion_matrix.labels.map((label) => <th key={label} className="p-2 text-right text-slate-400">{label}</th>)}</tr></thead>
                    <tbody>{modelReport.metrics.confusion_matrix.counts.map((row, index) => <tr key={modelReport.metrics.confusion_matrix?.labels[index]} className="border-t border-slate-800"><th className="p-2 text-left text-slate-400">{modelReport.metrics.confusion_matrix?.labels[index]}</th>{row.map((value, cellIndex) => <td key={cellIndex} className="p-2 text-right tabular-nums text-white">{value}</td>)}</tr>)}</tbody>
                  </table>
                </div>
              )}
              <div className="border-t border-slate-800 pt-3 text-[10px] leading-5 text-slate-500">
                <p>{modelReport.split.train_rows.toLocaleString()} training rows · {modelReport.split.test_rows.toLocaleString()} held-out rows · seed {modelReport.split.random_state} · {modelReport.duration_seconds.toFixed(3)}s</p>
                <p>Preprocessing fit scope: {modelReport.preprocessing.fit_scope}; test partition used to fit preprocessing: {String(modelReport.preprocessing.test_partition_used_to_fit_preprocessing)}.</p>
                <p className="break-all">Source SHA-256 · {modelReport.source_sha256}</p>
              </div>
            </div>
          )}
        </div>
      </div>
    </section>
  );
}
