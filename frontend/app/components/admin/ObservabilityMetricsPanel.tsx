"use client";

import { useCallback, type CSSProperties } from "react";

import adm from "./adminDashboard.module.css";

export type MetricsBucketDto = {
  bucket_start: string;
  query_count: number;
  retrieve_count: number;
  avg_query_latency_ms: number;
  p95_query_latency_ms: number;
  avg_retrieval_latency_ms: number;
  p95_retrieval_latency_ms: number;
  avg_llm_latency_ms: number;
  p95_llm_latency_ms: number;
  avg_total_tokens: number;
  avg_retrieval_accuracy_proxy: number;
  query_success_count: number;
  query_failure_count: number;
  retrieve_success_count: number;
  retrieve_failure_count: number;
  degraded_query_count: number;
};

export type MetricsTotalsDto = {
  query_events: number;
  retrieve_events: number;
  avg_query_latency_ms: number;
  p95_query_latency_ms: number;
  success_rate: number;
  failure_rate: number;
};

export type MetricsSummaryDto = {
  range: string;
  bucket_minutes: number;
  bucket_start: string;
  bucket_end: string;
  buckets: MetricsBucketDto[];
  previous_buckets: MetricsBucketDto[];
  totals: MetricsTotalsDto;
  previous_totals: MetricsTotalsDto;
  alert_thresholds: {
    warn_query_latency_ms: number;
    warn_llm_latency_ms: number;
    warn_retrieval_latency_ms: number;
    min_success_rate: number;
  };
};

type Props = {
  backendUrl: string;
  authHeaders: Record<string, string>;
  summary: MetricsSummaryDto | null;
  errorText: string;
  metricsRange: "24h" | "7d" | "30d";
  onMetricsRangeChange: (v: "24h" | "7d" | "30d") => void;
  exportingDisabled?: boolean;
};

function pct(prev: number, cur: number): string {
  if (!Number.isFinite(prev) || prev === 0) return "—";
  const ch = ((cur - prev) / prev) * 100;
  const rounded = Math.round(ch * 10) / 10;
  return `${rounded >= 0 ? "+" : ""}${rounded}%`;
}

function shortTick(iso: string, range: string): string {
  const d = Date.parse(iso);
  if (Number.isNaN(d)) return "?";
  const dt = new Date(d);
  if (range === "24h") return `${dt.getUTCHours().toString().padStart(2, "0")}h`;
  return `${dt.getUTCMonth() + 1}/${dt.getUTCDate()}`;
}

function deltaTone(deltaNote: string): CSSProperties | undefined {
  if (deltaNote.startsWith("+")) return { color: "#86efac" };
  if (deltaNote.startsWith("-")) return { color: "#fca5a5" };
  return undefined;
}

export function ObservabilityMetricsPanel({
  backendUrl,
  authHeaders,
  summary,
  errorText,
  metricsRange,
  onMetricsRangeChange,
  exportingDisabled,
}: Props) {
  const downloadExport = useCallback(
    async (format: "json" | "csv") => {
      if (!backendUrl || !authHeaders.Authorization) return;
      const qp = new URLSearchParams();
      qp.set("range", metricsRange);
      qp.set("format", format);
      const res = await fetch(`${backendUrl}/audit/metrics/export?${qp}`, { headers: authHeaders });
      if (!res.ok) return;
      const blob = await res.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `observability-metrics-${metricsRange}.${format === "csv" ? "csv" : "json"}`;
      a.click();
      URL.revokeObjectURL(url);
    },
    [backendUrl, authHeaders, metricsRange],
  );

  const th = summary?.alert_thresholds;
  const buckets = summary?.buckets ?? [];
  const prevBuckets = summary?.previous_buckets ?? [];
  const maxLat = Math.max(1, ...buckets.map((b) => Math.max(b.avg_query_latency_ms, b.p95_query_latency_ms * 0.85)));

  const alerts: string[] = [];
  if (summary && th) {
    if (summary.totals.avg_query_latency_ms > th.warn_query_latency_ms) {
      alerts.push(`Mean query latency (${Math.round(summary.totals.avg_query_latency_ms)} ms) exceeds warn threshold.`);
    }
    if (summary.totals.success_rate < th.min_success_rate && summary.totals.query_events >= 3) {
      alerts.push(`Success rate (${(summary.totals.success_rate * 100).toFixed(1)}%) dipped below guidance.`);
    }
  }

  const pt = summary?.previous_totals;
  const ct = summary?.totals;

  return (
    <section className={adm.obsWrap} data-testid="admin-observability-metrics">
      <div className={adm.obsHeaderRow}>
        <div>
          <h3 className={adm.obsTitle}>Observability · latency & quality</h3>
          <p className={adm.obsSub}>
            End-to-end query latency, segmented retrieval & LLM duration (via /query RAG path), Groq token totals when the provider returns usage metadata,
            and rolling success rates. Samples aggregate asynchronously after each response — zero blocking work on the hot path.
          </p>
        </div>
        <div className={adm.obsControls}>
          <select
            value={metricsRange}
            onChange={(e) => onMetricsRangeChange(e.target.value as "24h" | "7d" | "30d")}
            data-testid="admin-metrics-range"
            aria-label="Metrics time range"
          >
            <option value="24h">Last 24 hours</option>
            <option value="7d">Last 7 days</option>
            <option value="30d">Last 30 days</option>
          </select>
          <button
            type="button"
            data-testid="admin-metrics-export-json"
            disabled={exportingDisabled || !backendUrl}
            onClick={() => void downloadExport("json")}
          >
            Export JSON
          </button>
          <button
            type="button"
            data-testid="admin-metrics-export-csv"
            disabled={exportingDisabled || !backendUrl}
            onClick={() => void downloadExport("csv")}
          >
            Export CSV
          </button>
        </div>
      </div>

      {errorText ? (
        <div className={adm.alertBanner} role="alert" data-testid="admin-metrics-error">
          {errorText}
        </div>
      ) : null}

      {alerts.length ? (
        <div className={adm.obsAlertStrip} data-testid="admin-metrics-anomaly-strip">
          {alerts.join(" ")}
        </div>
      ) : null}

      {summary && pt && ct ? (
        <div className={adm.obsCompareRow} data-testid="admin-metrics-compare">
          <div className={adm.obsCompareCard}>
            <div className={adm.obsCompareLabel}>Avg query latency</div>
            <div className={adm.obsCompareValue}>{Math.round(ct.avg_query_latency_ms)} ms</div>
            <div className={adm.obsCompareDelta} style={deltaTone(pct(pt.avg_query_latency_ms, ct.avg_query_latency_ms))}>
              vs prior {pct(pt.avg_query_latency_ms, ct.avg_query_latency_ms)}
            </div>
          </div>
          <div className={adm.obsCompareCard}>
            <div className={adm.obsCompareLabel}>p95 query latency</div>
            <div className={adm.obsCompareValue}>{Math.round(ct.p95_query_latency_ms)} ms</div>
            <div className={adm.obsCompareDelta} style={deltaTone(pct(pt.p95_query_latency_ms, ct.p95_query_latency_ms))}>
              vs prior {pct(pt.p95_query_latency_ms, ct.p95_query_latency_ms)}
            </div>
          </div>
          <div className={adm.obsCompareCard}>
            <div className={adm.obsCompareLabel}>Success rate</div>
            <div className={adm.obsCompareValue}>{(ct.success_rate * 100).toFixed(1)}%</div>
            <div className={adm.obsCompareDelta} style={deltaTone(pct(pt.success_rate || 1e-9, ct.success_rate))}>
              vs prior {pct(pt.success_rate || 1e-9, ct.success_rate)}
            </div>
          </div>
          <div className={adm.obsCompareCard}>
            <div className={adm.obsCompareLabel}>Query samples</div>
            <div className={adm.obsCompareValue}>{ct.query_events}</div>
            <div className={adm.obsCompareDelta}>retrieve ops · {ct.retrieve_events}</div>
          </div>
        </div>
      ) : null}

      <div className={adm.obsChartBlock}>
        <h4 className={adm.obsChartTitle}>Query latency trend · avg bar · prior window ghost</h4>
        {buckets.length === 0 ? (
          <div className={adm.emptyState}>
            <p className={adm.emptyTitle}>Collecting first buckets…</p>
            <p className={adm.emptyBody}>Run /query or /retrieve traffic — metrics append post-response without delaying answers.</p>
          </div>
        ) : (
          <>
            <div className={adm.obsMetricChart} role="img" aria-label="Average query latency by bucket">
              {buckets.map((b, i) => {
                const pctH = (b.avg_query_latency_ms / maxLat) * 100;
                const ghost = prevBuckets[i];
                const ghostH = ghost ? (ghost.avg_query_latency_ms / maxLat) * 100 : 0;
                const warn =
                  th && (b.avg_query_latency_ms > th.warn_query_latency_ms || b.p95_query_latency_ms > th.warn_query_latency_ms * 1.1);
                const critical = th && b.avg_query_latency_ms > th.warn_query_latency_ms * 1.6;
                let barClass = adm.obsMetricBar;
                if (critical) barClass += ` ${adm.obsMetricBarCritical}`;
                else if (warn) barClass += ` ${adm.obsMetricBarWarn}`;
                const titleParts = [
                  `${b.bucket_start}`,
                  `avg query ${Math.round(b.avg_query_latency_ms)} ms`,
                  `p95 ${Math.round(b.p95_query_latency_ms)} ms`,
                  `retrieval Ø ${Math.round(b.avg_retrieval_latency_ms)} ms`,
                  `LLM Ø ${Math.round(b.avg_llm_latency_ms)} ms`,
                  `tokens Ø ${Math.round(b.avg_total_tokens)}`,
                  `accuracy proxy Ø ${(b.avg_retrieval_accuracy_proxy * 100).toFixed(1)}%`,
                ];
                return (
                  <div key={`${b.bucket_start}-${i}`} className={adm.obsMetricCol}>
                    {ghost ? (
                      <div
                        className={adm.obsMetricBarGhost}
                        style={{ height: `${Math.max(4, ghostH)}%` }}
                        title={`prior avg ${Math.round(ghost.avg_query_latency_ms)} ms`}
                      />
                    ) : null}
                    <div
                      className={barClass}
                      style={{ height: `${Math.max(6, pctH)}%` }}
                      title={titleParts.join(" · ")}
                      data-testid={`admin-metrics-latency-bar-${i}`}
                    />
                    <span className={adm.obsMetricTick}>{shortTick(b.bucket_start, metricsRange)}</span>
                  </div>
                );
              })}
            </div>
            <div className={adm.obsLegend}>
              <span className={adm.obsLegendSwatch}>Current window avg latency</span>
              <span className={adm.obsLegendGhostSwatch}>Prior window avg (aligned index)</span>
            </div>
          </>
        )}
      </div>

      <div className={adm.obsChartBlock}>
        <h4 className={adm.obsChartTitle}>Success ratio per bucket (queries)</h4>
        {buckets.length === 0 ? null : (
          <div className={adm.obsMetricChart} role="img" aria-label="Success rate by bucket" style={{ height: "100px" }}>
            {buckets.map((b, i) => {
              const denom = b.query_success_count + b.query_failure_count;
              const rate = denom ? b.query_success_count / denom : 1;
              const pctH = rate * 100;
              const title = `${b.bucket_start}: success ${(rate * 100).toFixed(0)}% (${b.query_success_count}/${denom || 0}) · degraded ${b.degraded_query_count}`;
              return (
                <div key={`succ-${b.bucket_start}-${i}`} className={adm.obsMetricCol}>
                  <div
                    className={adm.obsMetricBar}
                    style={{
                      height: `${Math.max(8, pctH)}%`,
                      background:
                        rate < (summary?.alert_thresholds.min_success_rate ?? 0.92) && denom >= 2
                          ? "linear-gradient(180deg, rgba(251, 191, 36, 0.95), rgba(245, 158, 11, 0.45))"
                          : undefined,
                    }}
                    title={title}
                    data-testid={`admin-metrics-success-bar-${i}`}
                  />
                  <span className={adm.obsMetricTick}>{shortTick(b.bucket_start, metricsRange)}</span>
                </div>
              );
            })}
          </div>
        )}
      </div>
    </section>
  );
}
