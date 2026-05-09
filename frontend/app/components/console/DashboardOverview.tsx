"use client";

import ws from "./workspace.module.css";

type Props = {
  documentCount: number;
  lastUploadId?: string | null;
  backendHealthy?: boolean | null;
};

export function DashboardOverview({ documentCount, lastUploadId, backendHealthy }: Props) {
  return (
    <div style={{ display: "grid", gap: "1rem" }}>
      <div className={`${ws.glassElevated}`} style={{ padding: "1.15rem" }}>
        <h2 style={{ margin: "0 0 0.35rem", fontSize: "1.05rem" }}>Workspace pulse</h2>
        <p style={{ margin: 0, fontSize: "0.82rem", opacity: 0.78 }}>
          Upload sources → query with grounding → review retrieval & confidence → ship feedback loops.
        </p>
      </div>
      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit,minmax(160px,1fr))", gap: "0.85rem" }}>
        <div className={`${ws.statTile}`} data-testid="dash-stat-docs">
          <span style={{ fontSize: "0.72rem", opacity: 0.7 }}>Documents indexed</span>
          <strong style={{ fontSize: "1.55rem", fontVariantNumeric: "tabular-nums" }}>{documentCount}</strong>
        </div>
        <div className={`${ws.statTile}`} data-testid="dash-stat-api">
          <span style={{ fontSize: "0.72rem", opacity: 0.7 }}>API status</span>
          <strong style={{ fontSize: "1.05rem", color: backendHealthy === false ? "#fca5a5" : backendHealthy === true ? "#86efac" : "#cbd5e1" }}>
            {backendHealthy === true ? "Healthy" : backendHealthy === false ? "Unreachable" : "Unknown"}
          </strong>
        </div>
        <div className={`${ws.statTile}`} data-testid="dash-stat-last-upload">
          <span style={{ fontSize: "0.72rem", opacity: 0.7 }}>Last upload ID</span>
          <span style={{ fontFamily: "ui-monospace, monospace", fontSize: "0.72rem", wordBreak: "break-all", opacity: 0.9 }}>
            {lastUploadId ?? "—"}
          </span>
        </div>
      </div>
      <div className={`${ws.glassElevated}`} style={{ padding: "1rem 1.15rem", borderLeft: "3px solid rgba(59,130,246,0.55)" }}>
        <h3 style={{ margin: "0 0 0.35rem", fontSize: "0.92rem" }}>Guided flow</h3>
        <ol style={{ margin: 0, paddingLeft: "1.15rem", fontSize: "0.82rem", lineHeight: 1.55, opacity: 0.88 }}>
          <li>Open Documents — ingest PDF/DOCX/TXT.</li>
          <li>Jump to Query — paste ID or pick from grid.</li>
          <li>Watch chunks & confidence update live on the right.</li>
        </ol>
      </div>
    </div>
  );
}
