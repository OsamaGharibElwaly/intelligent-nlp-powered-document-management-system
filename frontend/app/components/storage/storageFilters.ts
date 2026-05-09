import type { StorageDoc, StorageFilterId } from "./types";

export const STORAGE_FILTER_ORDER: StorageFilterId[] = ["unread", "in_progress", "completed", "overdue", "pinned", "archived"];

export function parseDueDate(value: string | null | undefined): Date | null {
  if (!value || !String(value).trim()) return null;
  const d = new Date(String(value).trim().slice(0, 10) + "T12:00:00");
  return Number.isNaN(d.getTime()) ? null : d;
}

export function isDocOverdue(doc: StorageDoc, today = new Date()): boolean {
  if ((doc.read_status ?? "") === "completed") return false;
  const due = parseDueDate(doc.due_date ?? null);
  if (!due) return false;
  const t = new Date(today.getFullYear(), today.getMonth(), today.getDate());
  return due < t;
}

export function isDocInProgress(doc: StorageDoc): boolean {
  const rs = doc.read_status ?? "unread";
  const prog = Number(doc.reading_progress ?? 0);
  if (rs === "reading") return true;
  if (rs === "completed") return false;
  return prog > 0 && prog < 100;
}

/** Single-axis membership for pill counters (full library). */
export function matchesFilterAxis(doc: StorageDoc, id: StorageFilterId): boolean {
  switch (id) {
    case "unread":
      return (doc.read_status ?? "unread") === "unread";
    case "in_progress":
      return isDocInProgress(doc);
    case "completed":
      return (doc.read_status ?? "") === "completed";
    case "overdue":
      return isDocOverdue(doc);
    case "pinned":
      return Boolean(doc.pinned);
    case "archived":
      return Boolean(doc.archived);
    default:
      return false;
  }
}

/**
 * Multi-select AND filter. Empty selection ⇒ hide archived (default shelf), show active docs only.
 */
export function passesSelectedFilters(doc: StorageDoc, selected: ReadonlySet<StorageFilterId>): boolean {
  if (selected.size === 0) return !doc.archived;
  if (!selected.has("archived") && doc.archived) return false;
  for (const id of selected) {
    if (!matchesFilterAxis(doc, id)) return false;
  }
  return true;
}

export function countByFilter(documents: StorageDoc[], id: StorageFilterId): number {
  return documents.reduce((n, d) => n + (matchesFilterAxis(d, id) ? 1 : 0), 0);
}
