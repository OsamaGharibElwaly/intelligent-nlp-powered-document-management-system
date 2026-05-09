"use client";

import { FormEvent, useCallback, useEffect, useState } from "react";

import ws from "./workspace.module.css";

export type WorkspaceRow = {
  workspace_id: string;
  name: string;
  owner_id: string;
  members: Record<string, string>;
  my_role?: string;
};

type Props = {
  backendUrl: string;
  authHeaders: Record<string, string>;
  pushToast: (type: "success" | "error" | "info", message: string) => void;
};

export function TeamCollaborationPanel({ backendUrl, authHeaders, pushToast }: Props) {
  const [workspaces, setWorkspaces] = useState<WorkspaceRow[]>([]);
  const [busy, setBusy] = useState(false);
  const [newName, setNewName] = useState("Team workspace");
  const [selectedId, setSelectedId] = useState("");
  const [memberEmail, setMemberEmail] = useState("");
  const [memberRole, setMemberRole] = useState<"editor" | "viewer">("viewer");

  const refresh = useCallback(async () => {
    if (!backendUrl || !authHeaders.Authorization) return;
    const res = await fetch(`${backendUrl}/collaboration/workspaces`, { headers: authHeaders });
    const data = (await res.json().catch(() => [])) as WorkspaceRow[];
    if (!res.ok) return;
    setWorkspaces(Array.isArray(data) ? data : []);
    window.dispatchEvent(new Event("rag-workspaces-changed"));
  }, [backendUrl, authHeaders]);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  useEffect(() => {
    if (!selectedId && workspaces.length) setSelectedId(workspaces[0].workspace_id);
  }, [selectedId, workspaces]);

  const createWs = async (e: FormEvent) => {
    e.preventDefault();
    if (!backendUrl || !authHeaders.Authorization) return;
    setBusy(true);
    try {
      const res = await fetch(`${backendUrl}/collaboration/workspaces`, {
        method: "POST",
        headers: { "Content-Type": "application/json", ...authHeaders },
        body: JSON.stringify({ name: newName.trim() || "Workspace" }),
      });
      const err = (await res.json().catch(() => ({}))) as { detail?: string };
      if (!res.ok) throw new Error(typeof err.detail === "string" ? err.detail : "Create failed");
      pushToast("success", "Workspace created");
      setNewName("Team workspace");
      await refresh();
    } catch (ex) {
      pushToast("error", ex instanceof Error ? ex.message : "Create failed");
    } finally {
      setBusy(false);
    }
  };

  const addMember = async (e: FormEvent) => {
    e.preventDefault();
    if (!selectedId || !memberEmail.trim()) return;
    setBusy(true);
    try {
      const res = await fetch(`${backendUrl}/collaboration/workspaces/${encodeURIComponent(selectedId)}/members`, {
        method: "POST",
        headers: { "Content-Type": "application/json", ...authHeaders },
        body: JSON.stringify({ email: memberEmail.trim(), role: memberRole }),
      });
      const err = (await res.json().catch(() => ({}))) as { detail?: string };
      if (!res.ok) throw new Error(typeof err.detail === "string" ? err.detail : "Invite failed");
      pushToast("success", "Member updated");
      setMemberEmail("");
      await refresh();
    } catch (ex) {
      pushToast("error", ex instanceof Error ? ex.message : "Invite failed");
    } finally {
      setBusy(false);
    }
  };

  const selected = workspaces.find((w) => w.workspace_id === selectedId);

  return (
    <section
      className={ws.glassElevated}
      style={{ padding: "0.75rem", display: "grid", gap: "0.55rem", borderStyle: "dashed", borderColor: "rgba(129,140,248,0.35)" }}
      data-testid="team-collaboration-panel"
    >
      <h3 style={{ margin: 0, fontSize: "0.88rem" }}>Team</h3>
      <p style={{ margin: 0, fontSize: "0.72rem", opacity: 0.72, lineHeight: 1.4 }}>
        Shared workspaces · invite editors/viewers · uploads can target a workspace from the Documents panel.
      </p>
      <form onSubmit={(ev) => void createWs(ev)} style={{ display: "grid", gap: "0.35rem" }}>
        <label style={{ fontSize: "0.72rem", display: "grid", gap: "0.25rem" }}>
          New workspace name
          <input
            value={newName}
            onChange={(e) => setNewName(e.target.value)}
            data-testid="team-new-workspace-name"
            className={ws.inputGlow}
            style={{ padding: "0.45rem", borderRadius: 8, border: "1px solid #334155", background: "#0f172a", color: "#e5e7eb" }}
          />
        </label>
        <button
          type="submit"
          disabled={busy || !authHeaders.Authorization}
          data-testid="team-create-workspace"
          style={{
            padding: "0.45rem",
            borderRadius: 8,
            border: "1px solid rgba(99,102,241,0.45)",
            background: busy ? "rgba(30,27,75,0.4)" : "#4f46e5",
            color: "white",
            fontWeight: 600,
            cursor: busy ? "wait" : "pointer",
          }}
        >
          Create workspace
        </button>
      </form>
      {workspaces.length ? (
        <>
          <label style={{ fontSize: "0.72rem", display: "grid", gap: "0.25rem" }}>
            Active team (members)
            <select
              value={selectedId}
              onChange={(e) => setSelectedId(e.target.value)}
              data-testid="team-workspace-select"
              className={ws.inputGlow}
              style={{ padding: "0.45rem", borderRadius: 8, border: "1px solid #334155", background: "#0f172a", color: "#e5e7eb" }}
            >
              {workspaces.map((w) => (
                <option key={w.workspace_id} value={w.workspace_id}>
                  {w.name} ({w.my_role ?? "member"})
                </option>
              ))}
            </select>
          </label>
          {selected ? (
            <ul style={{ margin: 0, paddingLeft: "1rem", fontSize: "0.72rem", opacity: 0.85, maxHeight: 120, overflowY: "auto" }} data-testid="team-member-list">
              <li>Owner · {selected.owner_id}</li>
              {Object.entries(selected.members ?? {}).map(([email, role]) => (
                <li key={email}>
                  {email} · {role}
                </li>
              ))}
            </ul>
          ) : null}
          <form onSubmit={(ev) => void addMember(ev)} style={{ display: "grid", gap: "0.35rem" }}>
            <span style={{ fontSize: "0.72rem", opacity: 0.75 }}>Invite member (owner only)</span>
            <input
              type="email"
              placeholder="colleague@company.com"
              value={memberEmail}
              onChange={(e) => setMemberEmail(e.target.value)}
              data-testid="team-invite-email"
              className={ws.inputGlow}
              style={{ padding: "0.45rem", borderRadius: 8, border: "1px solid #334155", background: "#0f172a", color: "#e5e7eb" }}
            />
            <select
              value={memberRole}
              onChange={(e) => setMemberRole(e.target.value as "editor" | "viewer")}
              data-testid="team-invite-role"
              className={ws.inputGlow}
              style={{ padding: "0.45rem", borderRadius: 8, border: "1px solid #334155", background: "#0f172a", color: "#e5e7eb" }}
            >
              <option value="editor">Editor (upload · query · comment)</option>
              <option value="viewer">Viewer (read · query)</option>
            </select>
            <button
              type="submit"
              disabled={busy || selected?.my_role !== "owner"}
              data-testid="team-invite-submit"
              style={{
                padding: "0.45rem",
                borderRadius: 8,
                border: "1px solid rgba(52,211,153,0.45)",
                background: selected?.my_role === "owner" ? "rgba(16,185,129,0.25)" : "rgba(30,41,59,0.35)",
                color: "#d1fae5",
                fontWeight: 600,
                cursor: selected?.my_role === "owner" ? "pointer" : "not-allowed",
              }}
            >
              Add / update member
            </button>
          </form>
        </>
      ) : (
        <p style={{ margin: 0, fontSize: "0.72rem", opacity: 0.65 }}>No teams yet — create one above.</p>
      )}
    </section>
  );
}
