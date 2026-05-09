"use client";

import type { StorageDoc, StorageFilterId } from "./types";
import { STORAGE_FILTER_ORDER, countByFilter } from "./storageFilters";
import styles from "./documentStorage.module.css";

const LABELS: Record<StorageFilterId, string> = {
  unread: "Unread",
  in_progress: "In progress",
  completed: "Completed",
  overdue: "Overdue",
  pinned: "Pinned",
  archived: "Archived",
};

type Props = {
  documents: StorageDoc[];
  selected: ReadonlySet<StorageFilterId>;
  onToggle: (id: StorageFilterId) => void;
  testIdPrefix?: string;
};

export function DocumentFilterPills({ documents, selected, onToggle, testIdPrefix = "storage-filter" }: Props) {
  return (
    <div
      role="toolbar"
      aria-label="Document filters"
      style={{ display: "flex", flexWrap: "wrap", gap: "0.5rem", marginBottom: "1rem", alignItems: "center" }}
    >
      <span style={{ fontSize: "0.78rem", opacity: 0.75, marginRight: "0.15rem" }}>Filters</span>
      {STORAGE_FILTER_ORDER.map((id) => {
        const active = selected.has(id);
        const count = countByFilter(documents, id);
        return (
          <button
            key={id}
            type="button"
            data-testid={`${testIdPrefix}-${id}`}
            aria-pressed={active}
            title={`${LABELS[id]} — ${count} document${count === 1 ? "" : "s"}`}
            className={`${styles.pill} ${active ? styles.pillActive : ""}`}
            onClick={() => onToggle(id)}
          >
            {LABELS[id]}
            <span className={styles.pillCount} aria-hidden>
              {count}
            </span>
          </button>
        );
      })}
      <span style={{ fontSize: "0.72rem", opacity: 0.55, marginLeft: "0.25rem" }}>Multi-select · AND</span>
    </div>
  );
}
