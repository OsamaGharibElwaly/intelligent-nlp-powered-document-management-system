"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import adm from "./adminDashboard.module.css";
import { ObservabilityMetricsPanel, type MetricsSummaryDto } from "./ObservabilityMetricsPanel";

export type AuditLogEntry = {
  timestamp: string;
  action: string;
  user_id: string;
  role: string;
  document_id?: string | null;
  details: Record<string, unknown>;
};

export type ErrorIntelEntry = {
  request_id: string;
  timestamp: string;
  error_type: string;
  severity: string;
  endpoint: string;
  message: string;
  stack_trace?: string | null;
  extra?: Record<string, unknown>;
};

type Props = {
  backendUrl: string;
  authHeaders: Record<string, string>;
  documentCount: number;
  totalStorageBytes: number;
  onRefreshDocuments: () => void | Promise<void>;
  isLoadingDocs: boolean;
};

const POLL_MS = 28_000;

function padDay(isoDay: string): string {
  const [, m, d] = isoDay.split("-");
  return `${m}/${d}`;
}

function utcDayKey(isoTimestamp: string): string | null {
  const t = Date.parse(isoTimestamp);
  if (Number.isNaN(t)) return null;
  const d = new Date(t);
  const y = d.getUTCFullYear();
  const mo = String(d.getUTCMonth() + 1).padStart(2, "0");
  const da = String(d.getUTCDate()).padStart(2, "0");
  return `${y}-${mo}-${da}`;
}

function computeErrorSinceIso(range: "1h" | "24h" | "7d" | "all"): string | undefined {
  if (range === "all") return undefined;
  const ms = range === "1h" ? 3600000 : range === "24h" ? 86400000 : 7 * 86400000;
  return new Date(Date.now() - ms).toISOString();
}

function formatStorage(bytes: number): string {
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  if (bytes < 1024 ** 3) return `${(bytes / (1024 * 1024)).toFixed(2)} MB`;
  return `${(bytes / 1024 ** 3).toFixed(2)} GB`;
}

function AnimatedNumber({ value, decimals = 0 }: { value: number; decimals?: number }) {
  const [shown, setShown] = useState(0);
  const prev = useRef(0);

  useEffect(() => {
    const start = prev.current;
    const target = value;
    prev.current = target;
    const dur = 520;
    const t0 = performance.now();

    const tick = (now: number) => {
      const p = Math.min(1, (now - t0) / dur);
      const eased = 1 - (1 - p) ** 3;
      setShown(start + (target - start) * eased);
      if (p < 1) requestAnimationFrame(tick);
    };
    requestAnimationFrame(tick);
  }, [value]);

  return <>{decimals ? shown.toFixed(decimals) : Math.round(shown)}</>;
}

export function AdminCommandCenter({
  backendUrl,
  authHeaders,
  documentCount,
  totalStorageBytes,
  onRefreshDocuments,
  isLoadingDocs,
}: Props) {
  const [auditLogs, setAuditLogs] = useState<AuditLogEntry[]>([]);
  const [health, setHealth] = useState<Record<string, string> | null>(null);
  const [loadingAudit, setLoadingAudit] = useState(false);
  const [auditError, setAuditError] = useState("");
  const [lastSynced, setLastSynced] = useState<Date | null>(null);
  const [errorIntelEvents, setErrorIntelEvents] = useState<ErrorIntelEntry[]>([]);
  const [errorIntelErr, setErrorIntelErr] = useState("");
  const [errorFilterEndpoint, setErrorFilterEndpoint] = useState("");
  const [errorFilterSeverity, setErrorFilterSeverity] = useState("");
  const [errorFilterType, setErrorFilterType] = useState("");
  const [errorFilterRange, setErrorFilterRange] = useState<"1h" | "24h" | "7d" | "all">("24h");
  const [expandedErrorKeys, setExpandedErrorKeys] = useState<Set<string>>(() => new Set());
  const [metricsSummary, setMetricsSummary] = useState<MetricsSummaryDto | null>(null);
  const [metricsErr, setMetricsErr] = useState("");
  const [metricsRange, setMetricsRange] = useState<"24h" | "7d" | "30d">("24h");

  const fetchSnapshot = useCallback(async () => {
    if (!backendUrl || !authHeaders.Authorization) return;
    setLoadingAudit(true);
    setAuditError("");
    setErrorIntelErr("");
    setMetricsErr("");
    try {
      const qp = new URLSearchParams();
      qp.set("limit", "500");
      const prefix = errorFilterEndpoint.trim();
      if (prefix) qp.set("endpoint_prefix", prefix);
      if (errorFilterSeverity) qp.set("severity", errorFilterSeverity);
      if (errorFilterType) qp.set("error_type", errorFilterType);
      const since = computeErrorSinceIso(errorFilterRange);
      if (since) qp.set("since", since);

      const mp = new URLSearchParams();
      mp.set("range", metricsRange);
      const [logRes, healthRes, errRes, metRes] = await Promise.all([
        fetch(`${backendUrl}/audit/logs?limit=500`, { headers: authHeaders }),
        fetch(`${backendUrl}/health`),
        fetch(`${backendUrl}/audit/error-events?${qp}`, { headers: authHeaders }),
        fetch(`${backendUrl}/audit/metrics/summary?${mp}`, { headers: authHeaders }),
      ]);
      const healthJson = (await healthRes.json()) as Record<string, string>;
      setHealth(healthJson);

      if (!errRes.ok) {
        const errBody = (await errRes.json().catch(() => ({}))) as { detail?: unknown };
        const detail = typeof errBody.detail === "string" ? errBody.detail : "Unable to load error intelligence";
        setErrorIntelErr(errRes.status === 403 ? "Admin role required for error intelligence." : detail);
        setErrorIntelEvents([]);
      } else {
        const rows = (await errRes.json()) as ErrorIntelEntry[];
        setErrorIntelEvents(Array.isArray(rows) ? rows : []);
      }

      if (!metRes.ok) {
        const errBody = (await metRes.json().catch(() => ({}))) as { detail?: unknown };
        const detail = typeof errBody.detail === "string" ? errBody.detail : "Unable to load observability metrics";
        setMetricsErr(metRes.status === 403 ? "Admin role required for observability metrics." : detail);
        setMetricsSummary(null);
      } else {
        const payload = (await metRes.json()) as MetricsSummaryDto;
        setMetricsErr("");
        setMetricsSummary(payload);
      }

      if (!logRes.ok) {
        const errBody = (await logRes.json().catch(() => ({}))) as { detail?: unknown };
        const detail = typeof errBody.detail === "string" ? errBody.detail : "Unable to load audit logs";
        throw new Error(logRes.status === 403 ? "Admin role required for audit stream." : detail);
      }
      const logs = (await logRes.json()) as AuditLogEntry[];
      setAuditLogs(Array.isArray(logs) ? logs : []);

      setLastSynced(new Date());
    } catch (e) {
      setAuditError(e instanceof Error ? e.message : "Audit fetch failed");
      setAuditLogs([]);
    } finally {
      setLoadingAudit(false);
    }
  }, [backendUrl, authHeaders, errorFilterEndpoint, errorFilterSeverity, errorFilterType, errorFilterRange, metricsRange]);

  useEffect(() => {
    void fetchSnapshot();
  }, [fetchSnapshot]);

  useEffect(() => {
    const id = window.setInterval(() => void fetchSnapshot(), POLL_MS);
    return () => window.clearInterval(id);
  }, [fetchSnapshot]);

  const metrics = useMemo(() => {
    const queryEntries = auditLogs.filter((e) => e.action === "query");
    const byDay = new Map<string, number>();
    const todayKey = utcDayKey(new Date().toISOString());
    const horizonDays = 14;
    const start = Date.UTC(
      new Date().getUTCFullYear(),
      new Date().getUTCMonth(),
      new Date().getUTCDate() - (horizonDays - 1),
    );
    for (let i = 0; i < horizonDays; i++) {
      const dt = new Date(start + i * 86400000);
      const k = `${dt.getUTCFullYear()}-${String(dt.getUTCMonth() + 1).padStart(2, "0")}-${String(dt.getUTCDate()).padStart(2, "0")}`;
      byDay.set(k, 0);
    }
    let queriesToday = 0;
    let queriesLast24h = 0;
    const cutoff24 = Date.now() - 86400000;
    const usersWindow = new Set<string>();

    for (const e of auditLogs) {
      usersWindow.add(e.user_id);
      const day = utcDayKey(e.timestamp);
      if (day && byDay.has(day)) {
        byDay.set(day, (byDay.get(day) ?? 0) + (e.action === "query" ? 1 : 0));
      }
      if (e.action !== "query") continue;
      const ts = Date.parse(e.timestamp);
      if (!Number.isNaN(ts) && ts >= cutoff24) queriesLast24h += 1;
      if (day && todayKey && day === todayKey) queriesToday += 1;
    }

    const series = [...byDay.entries()].map(([day, count]) => ({ day, count }));
    const maxCount = Math.max(1, ...series.map((s) => s.count));

    const last7 = series.slice(-7);
    const avg7 = last7.reduce((s, x) => s + x.count, 0) / Math.max(1, last7.length);
    const spike = queriesToday > avg7 * 2.25 && avg7 > 0;

    const groqOk = health?.groq_configured === "true";

    return {
      queryEntries,
      queriesToday,
      queriesLast24h,
      activeUsers: usersWindow.size,
      series,
      maxCount,
      todayKey,
      spike,
      groqOk,
      avg7,
    };
  }, [auditLogs, health]);

  const groqConfigured = health?.groq_configured === "true";
  const apiOk = health?.status === "ok";

  const refreshAll = () => {
    void onRefreshDocuments();
    void fetchSnapshot();
  };

  const feedRows = useMemo(() => [...auditLogs].reverse().slice(0, 28), [auditLogs]);

  const errorsGrouped = useMemo(() => {
    const priority = (t: string) => {
      const order = ["system", "llm", "retrieval", "validation"];
      const i = order.indexOf(t);
      return i === -1 ? 99 : i;
    };
    const map = new Map<string, ErrorIntelEntry[]>();
    for (const e of errorIntelEvents) {
      const k = e.error_type || "unknown";
      if (!map.has(k)) map.set(k, []);
      map.get(k)!.push(e);
    }
    return [...map.entries()].sort((a, b) => priority(a[0]) - priority(b[0]));
  }, [errorIntelEvents]);

  const severityBadgeClass = (sev: string): string => {
    if (sev === "critical") return `${adm.errSevBadge} ${adm.errSevCritical}`;
    if (sev === "error") return `${adm.errSevBadge} ${adm.errSevError}`;
    if (sev === "warning") return `${adm.errSevBadge} ${adm.errSevWarn}`;
    return `${adm.errSevBadge} ${adm.errSevInfo}`;
  };

  const toggleErrorExpanded = (key: string) => {
    setExpandedErrorKeys((prev) => {
      const next = new Set(prev);
      if (next.has(key)) next.delete(key);
      else next.add(key);
      return next;
    });
  };

  const endpointSuggestions = useMemo(() => {
    const u = new Set<string>();
    for (const e of errorIntelEvents) {
      if (e.endpoint) u.add(e.endpoint);
    }
    return [...u].sort((a, b) => a.localeCompare(b));
  }, [errorIntelEvents]);

  return (
    <div style={{ display: "grid", gap: "1.1rem" }} data-testid="admin-command-center">
      <div className={`${adm.hero}`}>
        <div>
          <h2 className={adm.heroTitle}>AI system command center</h2>
          <p className={adm.heroMeta}>
            Near-real-time signals · polled every {Math.round(POLL_MS / 1000)}s
            {lastSynced ? ` · last sync ${lastSynced.toLocaleTimeString()}` : ""}
          </p>
        </div>
        <button
          type="button"
          className={adm.refreshBtn}
          data-testid="admin-dashboard-refresh"
          disabled={loadingAudit || isLoadingDocs}
          onClick={() => refreshAll()}
        >
          {loadingAudit || isLoadingDocs ? "Refreshing…" : "Refresh data"}
        </button>
      </div>

      {auditError ? (
        <div className={adm.alertBanner} data-testid="admin-dashboard-error" role="alert">
          {auditError}
        </div>
      ) : null}

      {loadingAudit && !lastSynced && !auditError ? (
        <div className={adm.adminSkeletonGrid} data-testid="admin-dashboard-skeleton" aria-busy="true" aria-label="Loading dashboard">
          {Array.from({ length: 6 }).map((_, i) => (
            <div key={i} className={adm.adminSkeletonPulse} />
          ))}
        </div>
      ) : null}

      <div className={adm.kpiGrid}>
        <div
          className={`${adm.kpiCard} ${adm.kpiHealthy}`}
          title="Total documents returned by the catalog for your tenant scope."
          data-testid="admin-kpi-documents"
        >
          <span className={adm.kpiLabel}>Documents indexed</span>
          <span className={adm.kpiValue}>
            <AnimatedNumber value={documentCount} />
          </span>
          <p className={adm.kpiHint}>Corpus size visible to your session.</p>
        </div>

        <div
          className={`${adm.kpiCard} ${totalStorageBytes > 1024 ** 3 * 5 ? adm.kpiWarn : adm.kpiHealthy}`}
          title="Sum of logical file sizes from document metadata."
          data-testid="admin-kpi-storage"
        >
          <span className={adm.kpiLabel}>Storage footprint</span>
          <span className={adm.kpiValue}>
            <AnimatedNumber value={totalStorageBytes / (1024 * 1024)} decimals={1} /> MB
          </span>
          <p className={adm.kpiHint}>{formatStorage(totalStorageBytes)} aggregate · metadata-derived</p>
        </div>

        <div
          className={`${adm.kpiCard} ${metrics.spike ? adm.kpiWarn : adm.kpiHealthy}`}
          title="Query events logged in audit trail for UTC calendar day."
          data-testid="admin-kpi-queries-today"
        >
          <span className={adm.kpiLabel}>Queries today</span>
          <span className={adm.kpiValue}>
            <AnimatedNumber value={metrics.queriesToday} />
          </span>
          <p className={adm.kpiHint}>
            {metrics.queriesLast24h} in last 24h · {metrics.spike ? "Elevated vs 7d avg" : "Stable vs rolling avg"}
          </p>
        </div>

        <div
          className={`${adm.kpiCard} ${groqConfigured ? adm.kpiHealthy : adm.kpiCritical}`}
          title="Groq API key presence on server. Token totals require provider billing — use query volume as a proxy."
          data-testid="admin-kpi-groq"
        >
          <span className={adm.kpiLabel}>Groq / LLM readiness</span>
          <span className={adm.kpiValue} style={{ fontSize: "1.05rem" }}>
            {groqConfigured ? "Configured" : "Missing key"}
          </span>
          <p className={adm.kpiHint}>
            {metrics.queryEntries.length} queries in sampled audit window — pair with Groq console for billed tokens.
          </p>
        </div>

        <div
          className={`${adm.kpiCard} ${adm.kpiHealthy}`}
          title="Distinct user IDs visible in the sampled audit window."
          data-testid="admin-kpi-users"
        >
          <span className={adm.kpiLabel}>Active identities</span>
          <span className={adm.kpiValue}>
            <AnimatedNumber value={metrics.activeUsers} />
          </span>
          <p className={adm.kpiHint}>Unique users in last {auditLogs.length} audit rows · expand retention for fuller MAU.</p>
        </div>

        <div
          className={`${adm.kpiCard} ${apiOk ? adm.kpiHealthy : adm.kpiCritical}`}
          title="/health status payload"
          data-testid="admin-kpi-api"
        >
          <span className={adm.kpiLabel}>API heartbeat</span>
          <span className={adm.kpiValue} style={{ fontSize: "1.05rem" }}>
            {health?.status ?? "Unknown"}
          </span>
          <p className={adm.kpiHint}>JWT {health?.jwt_configured === "true" ? "on" : "off"} · Groq {metrics.groqOk ? "ready" : "not ready"}</p>
        </div>
      </div>

      <div className={adm.twoCol}>
        <div className={adm.chartCard} data-testid="admin-chart-queries">
          <h3 className={adm.chartTitle}>Query rhythm · 14-day audit trail</h3>
          <p className={adm.chartSubtitle}>Each bar counts logged `query` actions · hover dates on narrow screens via tooltip title.</p>
          {metrics.series.every((s) => s.count === 0) ? (
            <div className={adm.emptyState}>
              <p className={adm.emptyTitle}>No query telemetry yet</p>
              <p className={adm.emptyBody}>Run grounded queries — events appear here for admins automatically.</p>
            </div>
          ) : (
            <div className={adm.barChart} role="img" aria-label="Queries per day last fourteen days">
              {metrics.series.map(({ day, count }) => {
                const pct = (count / metrics.maxCount) * 100;
                const isToday = metrics.todayKey === day;
                return (
                  <div key={day} className={adm.barCol} title={`${day}: ${count} queries`}>
                    <div
                      className={`${adm.bar} ${isToday ? adm.barToday : ""}`}
                      style={{ height: `${Math.max(6, pct)}%` }}
                      data-testid={`admin-chart-bar-${day}`}
                    />
                    <span className={adm.barLabel}>{padDay(day)}</span>
                  </div>
                );
              })}
            </div>
          )}
        </div>

        <div className={adm.feedCard} data-testid="admin-activity-feed">
          <h3 className={adm.feedTitle}>Live audit stream</h3>
          <div className={adm.feedScroll}>
            {feedRows.length === 0 ? (
              <div className={adm.emptyState}>
                <p className={adm.emptyTitle}>Quiet system</p>
                <p className={adm.emptyBody}>Uploads, retrievals, and queries will populate this trail.</p>
              </div>
            ) : (
              feedRows.map((row, i) => (
                <div key={`${row.timestamp}-${row.user_id}-${i}`} className={adm.feedRow} data-testid={`admin-feed-row-${i}`}>
                  <span className={adm.feedAction}>{row.action}</span>
                  <span className={adm.feedMeta}>
                    {" "}
                    · {row.timestamp} · {row.user_id}
                    {row.document_id ? ` · doc ${String(row.document_id).slice(0, 8)}…` : ""}
                  </span>
                  {Object.keys(row.details ?? {}).length ? (
                    <div style={{ marginTop: "0.25rem", opacity: 0.78, fontSize: "0.68rem", wordBreak: "break-word" }}>
                      {JSON.stringify(row.details).slice(0, 220)}
                      {JSON.stringify(row.details).length > 220 ? "…" : ""}
                    </div>
                  ) : null}
                </div>
              ))
            )}
          </div>
        </div>
      </div>

      <ObservabilityMetricsPanel
        backendUrl={backendUrl}
        authHeaders={authHeaders}
        summary={metricsSummary}
        errorText={metricsErr}
        metricsRange={metricsRange}
        onMetricsRangeChange={setMetricsRange}
        exportingDisabled={loadingAudit}
      />

      <section className={adm.errorIntelWrap} data-testid="admin-error-intelligence">
        <div className={adm.errorIntelHeader}>
          <h3 className={adm.errorIntelTitle}>Error intelligence</h3>
          <p className={adm.errorIntelSubtitle}>
            Classified failures (retrieval · LLM · validation · system). Stack traces stay server-side except in this admin view — never exposed to standard workspace clients.
          </p>
        </div>

        {errorIntelErr ? (
          <div className={adm.alertBanner} data-testid="admin-error-intel-banner" role="alert">
            {errorIntelErr}
          </div>
        ) : null}

        <div className={adm.errorFilterRow}>
          <label>
            Endpoint prefix
            <input
              type="text"
              placeholder="/query"
              value={errorFilterEndpoint}
              onChange={(e) => setErrorFilterEndpoint(e.target.value)}
              list="admin-error-endpoint-suggestions"
              data-testid="admin-error-filter-endpoint"
            />
            <datalist id="admin-error-endpoint-suggestions">
              {endpointSuggestions.map((p) => (
                <option key={p} value={p} />
              ))}
            </datalist>
          </label>
          <label>
            Severity
            <select
              value={errorFilterSeverity}
              onChange={(e) => setErrorFilterSeverity(e.target.value)}
              data-testid="admin-error-filter-severity"
            >
              <option value="">All</option>
              <option value="info">info</option>
              <option value="warning">warning</option>
              <option value="error">error</option>
              <option value="critical">critical</option>
            </select>
          </label>
          <label>
            Type
            <select
              value={errorFilterType}
              onChange={(e) => setErrorFilterType(e.target.value)}
              data-testid="admin-error-filter-type"
            >
              <option value="">All</option>
              <option value="retrieval">retrieval</option>
              <option value="llm">llm</option>
              <option value="validation">validation</option>
              <option value="system">system</option>
            </select>
          </label>
          <label>
            Time range
            <select
              value={errorFilterRange}
              onChange={(e) => setErrorFilterRange(e.target.value as "1h" | "24h" | "7d" | "all")}
              data-testid="admin-error-filter-range"
            >
              <option value="1h">Last hour</option>
              <option value="24h">Last 24h</option>
              <option value="7d">Last 7d</option>
              <option value="all">All time</option>
            </select>
          </label>
        </div>

        {errorsGrouped.length === 0 && !errorIntelErr ? (
          <div className={adm.emptyState}>
            <p className={adm.emptyTitle}>No classified errors in range</p>
            <p className={adm.emptyBody}>Adjust filters or trigger guarded failures — events attach X-Request-ID on every response.</p>
          </div>
        ) : null}

        {errorsGrouped.map(([etype, items]) => (
          <div key={etype} className={adm.errorGroup} data-testid={`admin-error-group-${etype}`}>
            <div className={adm.errorGroupTitle}>
              {etype} · {items.length} event{items.length === 1 ? "" : "s"}
            </div>
            {items.map((ev) => {
              const expandKey = `${ev.request_id}|${ev.timestamp}`;
              const open = expandedErrorKeys.has(expandKey);
              const extraKeys = ev.extra ? Object.keys(ev.extra) : [];
              return (
                <div key={expandKey} className={adm.errorCard} data-testid={`admin-error-card-${ev.request_id}`}>
                  <button
                    type="button"
                    className={adm.errorCardHead}
                    onClick={() => toggleErrorExpanded(expandKey)}
                    data-testid={`admin-error-card-toggle-${ev.request_id}`}
                  >
                    <span className={severityBadgeClass(ev.severity)}>{ev.severity}</span>
                    <span className={adm.errorCardMeta}>
                      <strong>{ev.endpoint}</strong>
                      {" · "}
                      {ev.timestamp}
                      {" · "}
                      <span style={{ opacity: 0.85 }}>req {ev.request_id.slice(0, 8)}…</span>
                    </span>
                    <span style={{ marginLeft: "auto", opacity: 0.65, fontSize: "0.72rem" }}>{open ? "▼" : "▶"}</span>
                  </button>
                  <div className={adm.errorCardMsg}>{ev.message}</div>
                  {open ? (
                    <div className={adm.errorCardDetail}>
                      {ev.stack_trace ? (
                        <pre className={adm.errorStack} data-testid={`admin-error-stack-${ev.request_id}`}>
                          {ev.stack_trace}
                        </pre>
                      ) : (
                        <p className={adm.errorExtra} style={{ margin: 0 }}>
                          No stack trace captured for this event.
                        </p>
                      )}
                      {extraKeys.length ? (
                        <div className={adm.errorExtra}>
                          <strong>extra</strong> · {JSON.stringify(ev.extra).slice(0, 1200)}
                          {JSON.stringify(ev.extra).length > 1200 ? "…" : ""}
                        </div>
                      ) : null}
                    </div>
                  ) : null}
                </div>
              );
            })}
          </div>
        ))}
      </section>
    </div>
  );
}
