"use client";

import type { StorageDoc } from "./types";
import { isDocOverdue } from "./storageFilters";
import styles from "./documentStorage.module.css";

type Props = {
  doc: StorageDoc;
  selectedQueryId: string;
  formatFileSize: (n: number) => string;
  fileSize: number;
  canEdit: boolean;
  busy: boolean;
  onOpenQuery: () => void;
  onManage: () => void;
  onToggleRead: () => void;
  onQuickTodo: () => void;
  onArchive: () => void;
  onPinToggle: () => void;
};

function formatShortDate(iso: string | null | undefined): string {
  if (!iso || !String(iso).trim()) return "—";
  const d = new Date(String(iso));
  if (Number.isNaN(d.getTime())) return String(iso).slice(0, 16);
  return d.toLocaleString(undefined, { month: "short", day: "numeric", hour: "2-digit", minute: "2-digit" });
}

export function DocumentCard({
  doc,
  selectedQueryId,
  formatFileSize,
  fileSize,
  canEdit,
  busy,
  onOpenQuery,
  onManage,
  onToggleRead,
  onQuickTodo,
  onArchive,
  onPinToggle,
}: Props) {
  const rs = doc.read_status ?? "unread";
  const overdue = isDocOverdue(doc);
  const progress = Math.min(100, Math.max(0, Number(doc.reading_progress ?? 0)));
  const highPri = (doc.priority ?? "medium") === "high";
  const inProg = rs === "reading" || (rs !== "completed" && progress > 0 && progress < 100);

  const edgeState = overdue
    ? styles.stateOverdue
    : rs === "completed"
      ? styles.stateCompleted
      : inProg
        ? styles.stateReading
        : styles.stateUnread;

  const stateClasses = [
    styles.card,
    edgeState,
    doc.pinned ? styles.statePinned : "",
    highPri ? styles.priorityHigh : "",
    selectedQueryId === doc.document_id ? styles.cardSelected : "",
  ]
    .filter(Boolean)
    .join(" ");

  const readLabel = rs === "unread" ? "Mark read" : "Mark unread";

  return (
    <article
      tabIndex={0}
      data-testid={`document-card-${doc.document_id}`}
      className={stateClasses}
      onKeyDown={(e) => {
        if (e.key === "Enter" || e.key === " ") {
          e.preventDefault();
          onManage();
        }
      }}
      aria-label={`Document ${doc.filename}, ${rs}${overdue ? ", overdue" : ""}`}
    >
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", gap: "0.5rem" }}>
        <div style={{ minWidth: 0 }}>
          <h3
            style={{
              margin: "0 0 0.35rem",
              fontSize: "0.98rem",
              lineHeight: 1.35,
              wordBreak: "break-word",
              color: "#f8fafc",
            }}
          >
            {doc.filename}
          </h3>
          <div style={{ display: "flex", flexWrap: "wrap", gap: "0.35rem", alignItems: "center", fontSize: "0.72rem", opacity: 0.82 }}>
            <span
              style={{
                padding: "0.12rem 0.45rem",
                borderRadius: 999,
                background: rs === "completed" ? "rgba(34,197,94,0.2)" : rs === "reading" ? "rgba(59,130,246,0.2)" : "rgba(148,163,184,0.2)",
                border: `1px solid ${rs === "completed" ? "rgba(34,197,94,0.45)" : rs === "reading" ? "rgba(59,130,246,0.4)" : "rgba(148,163,184,0.35)"}`,
                color: "#e5e7eb",
              }}
            >
              {rs}
            </span>
            {overdue ? (
              <span style={{ color: "#fecaca", fontWeight: 600 }} title="Past due date">
                Due
              </span>
            ) : null}
            {doc.pinned ? (
              <span style={{ color: "#fde047" }} title="Pinned">
                📌 Pinned
              </span>
            ) : null}
            {doc.archived ? <span style={{ opacity: 0.75 }}>Archived</span> : null}
          </div>
        </div>
        <span style={{ fontSize: "0.72rem", opacity: 0.75, flexShrink: 0 }}>{formatFileSize(fileSize)}</span>
      </div>

      <div style={{ marginTop: "0.65rem" }}>
        <div style={{ display: "flex", justifyContent: "space-between", fontSize: "0.72rem", opacity: 0.8, marginBottom: "0.25rem" }}>
          <span>Progress</span>
          <span style={{ fontVariantNumeric: "tabular-nums" }}>{progress}%</span>
        </div>
        <div className={styles.progressTrack} aria-hidden>
          <div className={styles.progressFill} style={{ width: `${progress}%` }} />
        </div>
      </div>

      {doc.tags && doc.tags.length > 0 ? (
        <div style={{ marginTop: "0.55rem", display: "flex", flexWrap: "wrap", gap: "0.25rem" }}>
          {doc.tags.slice(0, 6).map((tag) => (
            <span
              key={tag}
              style={{
                fontSize: "0.68rem",
                padding: "0.12rem 0.38rem",
                borderRadius: 6,
                background: "rgba(51,65,85,0.75)",
                color: "#cbd5e1",
              }}
            >
              {tag}
            </span>
          ))}
        </div>
      ) : null}

      <p style={{ margin: "0.55rem 0 0", fontSize: "0.72rem", opacity: 0.72 }}>
        Last read: <span title={doc.last_read_at ?? ""}>{formatShortDate(doc.last_read_at)}</span>
        <span style={{ margin: "0 0.35rem", opacity: 0.45 }}>
          ·
        </span>
        <span title={doc.document_id}>ID …{doc.document_id.slice(-8)}</span>
      </p>

      <div className={styles.actionRail} role="group" aria-label="Quick actions">
        <button type="button" className={styles.actionBtn} data-testid={`card-open-query-${doc.document_id}`} title="Open in query workspace" onClick={onOpenQuery}>
          Open
        </button>
        <button
          type="button"
          className={styles.actionBtn}
          data-testid={`card-toggle-read-${doc.document_id}`}
          title={canEdit ? readLabel : "Lifecycle edits require user/admin"}
          disabled={!canEdit || busy}
          onClick={onToggleRead}
        >
          {readLabel}
        </button>
        <button
          type="button"
          className={styles.actionBtn}
          data-testid={`card-add-todo-${doc.document_id}`}
          title={canEdit ? "Add todo (quick)" : "Todos require user/admin"}
          disabled={!canEdit || busy}
          onClick={onQuickTodo}
        >
          + Todo
        </button>
        <button
          type="button"
          className={styles.actionBtn}
          data-testid={`card-archive-${doc.document_id}`}
          title={canEdit ? "Archive" : "Requires user/admin"}
          disabled={!canEdit || busy || doc.archived}
          onClick={onArchive}
        >
          Archive
        </button>
        <button
          type="button"
          className={styles.actionBtn}
          data-testid={`card-pin-${doc.document_id}`}
          title={canEdit ? (doc.pinned ? "Unpin" : "Pin") : "Requires user/admin"}
          disabled={!canEdit || busy}
          onClick={onPinToggle}
        >
          {doc.pinned ? "Unpin" : "Pin"}
        </button>
        <button type="button" className={styles.actionBtn} data-testid={`card-manage-${doc.document_id}`} title="Full productivity panel" onClick={onManage}>
          ⚙
        </button>
      </div>
    </article>
  );
}
