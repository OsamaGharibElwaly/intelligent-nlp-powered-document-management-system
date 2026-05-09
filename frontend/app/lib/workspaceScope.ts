export const WORKSPACE_SCOPE_KEY = "rag_workspace_scope";

export type WorkspaceScopeValue = "" | "personal" | (string & {});

export function readWorkspaceScope(): WorkspaceScopeValue {
  if (typeof window === "undefined") return "";
  try {
    const v = window.localStorage.getItem(WORKSPACE_SCOPE_KEY) ?? "";
    return v as WorkspaceScopeValue;
  } catch {
    return "";
  }
}

export function writeWorkspaceScope(scope: WorkspaceScopeValue): void {
  if (typeof window === "undefined") return;
  try {
    if (!scope) window.localStorage.removeItem(WORKSPACE_SCOPE_KEY);
    else window.localStorage.setItem(WORKSPACE_SCOPE_KEY, scope);
    window.dispatchEvent(new Event("rag-workspace-scope-changed"));
  } catch {
    /* ignore */
  }
}

export function documentMatchesWorkspaceScope(
  doc: { workspace_id?: string | null },
  scope: WorkspaceScopeValue,
): boolean {
  if (!scope || scope === "") return true;
  const wid = doc.workspace_id;
  if (scope === "personal") return wid == null || String(wid).trim() === "";
  return String(wid ?? "").trim() === String(scope).trim();
}
