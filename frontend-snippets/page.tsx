"use client";

import { useState } from "react";

type Overview = {
  api: string;
  database: string;
  database_engine: string;
  dataset_count: number;
};

const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://127.0.0.1:8000";

export default function Home() {
  const [result, setResult] = useState<Overview | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  async function checkConnection() {
    setLoading(true);
    setError(null);
    setResult(null);

    try {
      const response = await fetch(`${API_BASE_URL}/api/overview`, {
        cache: "no-store",
      });
      if (!response.ok) {
        throw new Error(`Backend returned HTTP ${response.status}`);
      }
      const data: Overview = await response.json();
      setResult(data);
    } catch (err) {
      const message =
        err instanceof Error ? err.message : "Unknown connection error";
      setError(
        `${message}. Confirm that FastAPI is running at ${API_BASE_URL}.`,
      );
    } finally {
      setLoading(false);
    }
  }

  return (
    <main className="min-h-screen bg-slate-950 px-6 py-16 text-slate-100">
      <div className="mx-auto max-w-3xl">
        <p className="mb-3 text-sm font-semibold uppercase tracking-[0.25em] text-cyan-400">
          Phase 1 · Foundation
        </p>
        <h1 className="text-4xl font-bold tracking-tight sm:text-5xl">
          Data<span className="text-cyan-400">Sentry</span>
        </h1>
        <p className="mt-4 max-w-2xl text-lg text-slate-300">
          Intelligent dataset quality assessment and machine-learning readiness analysis.
        </p>

        <section className="mt-10 rounded-2xl border border-slate-800 bg-slate-900 p-6 shadow-2xl">
          <h2 className="text-xl font-semibold">System connection</h2>
          <p className="mt-2 text-sm text-slate-400">
            This request checks FastAPI and its SQLite database connection.
          </p>
          <button
            type="button"
            onClick={checkConnection}
            disabled={loading}
            className="mt-6 rounded-lg bg-cyan-500 px-5 py-3 font-semibold text-slate-950 transition hover:bg-cyan-400 disabled:cursor-not-allowed disabled:opacity-60"
          >
            {loading ? "Checking..." : "Check backend + database"}
          </button>

          {result && (
            <div className="mt-6 rounded-xl border border-emerald-800 bg-emerald-950/40 p-5">
              <p className="font-semibold text-emerald-300">Connection successful</p>
              <dl className="mt-4 grid gap-3 text-sm sm:grid-cols-2">
                <div><dt className="text-slate-400">API</dt><dd>{result.api}</dd></div>
                <div>
                  <dt className="text-slate-400">Database</dt>
                  <dd>{result.database} ({result.database_engine})</dd>
                </div>
                <div>
                  <dt className="text-slate-400">Saved datasets</dt>
                  <dd>{result.dataset_count}</dd>
                </div>
              </dl>
            </div>
          )}

          {error && (
            <div className="mt-6 rounded-xl border border-rose-800 bg-rose-950/40 p-5 text-sm text-rose-200">
              {error}
            </div>
          )}
        </section>
      </div>
    </main>
  );
}
