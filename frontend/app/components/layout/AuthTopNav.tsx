"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useCallback, useEffect, useState } from "react";

import { clearStoredAuth, readStoredAuth } from "../../lib/authStorage";
import { readWorkspaceScope, writeWorkspaceScope, type WorkspaceScopeValue } from "../../lib/workspaceScope";
import { NotificationBell } from "./NotificationBell";

const backendUrl = process.env.NEXT_PUBLIC_BACKEND_URL ?? "";
const backendConfigured = Boolean(backendUrl);

const showAdminBootstrapUi =
  process.env.NODE_ENV === "development" || process.env.NEXT_PUBLIC_ENABLE_ADMIN_BOOTSTRAP_UI === "true";

export function AuthTopNav() {
  const pathname = usePathname();
  const router = useRouter();
  const [loggedIn, setLoggedIn] = useState(false);
  const [isAdmin, setIsAdmin] = useState(false);
  const [scope, setScope] = useState<WorkspaceScopeValue>("");
  const [workspaces, setWorkspaces] = useState<Array<{ workspace_id: string; name: string }>>([]);

  const refresh = useCallback(() => {
    const a = readStoredAuth();
    setLoggedIn(Boolean(a?.token));
    setIsAdmin(a?.role === "admin");
  }, []);

  useEffect(() => {
    refresh();
    setScope(readWorkspaceScope());
    const onStorage = () => refresh();
    window.addEventListener("storage", onStorage);
    window.addEventListener("rag-auth-changed", onStorage);
    const onScope = () => setScope(readWorkspaceScope());
    window.addEventListener("rag-workspace-scope-changed", onScope);
    return () => {
      window.removeEventListener("storage", onStorage);
      window.removeEventListener("rag-auth-changed", onStorage);
      window.removeEventListener("rag-workspace-scope-changed", onScope);
    };
  }, [refresh]);

  useEffect(() => {
    if (!loggedIn || !backendUrl) {
      setWorkspaces([]);
      return;
    }
    const a = readStoredAuth();
    if (!a?.token) {
      setWorkspaces([]);
      return;
    }
    let cancelled = false;
    const loadWorkspaces = () => {
      const auth = readStoredAuth();
      if (!auth?.token) return;
      void fetch(`${backendUrl}/collaboration/workspaces`, {
        headers: { Authorization: `Bearer ${auth.token}` },
      })
        .then((r) => r.json())
        .then((data) => {
          if (cancelled || !Array.isArray(data)) return;
          setWorkspaces(
            data
              .map((row: { workspace_id?: string; name?: string }) => ({
                workspace_id: String(row.workspace_id ?? ""),
                name: String(row.name ?? "Workspace"),
              }))
              .filter((w) => w.workspace_id),
          );
        })
        .catch(() => {
          if (!cancelled) setWorkspaces([]);
        });
    };
    loadWorkspaces();
    const onWs = () => loadWorkspaces();
    window.addEventListener("rag-workspaces-changed", onWs);
    return () => {
      cancelled = true;
      window.removeEventListener("rag-workspaces-changed", onWs);
    };
  }, [loggedIn, backendUrl]);

  const logout = () => {
    clearStoredAuth();
    refresh();
    router.push("/login");
    router.refresh();
  };

  const navBtn = (active: boolean) =>
    ({
      padding: "0.35rem 0.65rem",
      borderRadius: 8,
      border: `1px solid ${active ? "rgba(129,140,248,0.55)" : "rgba(148,163,184,0.22)"}`,
      background: active ? "rgba(79,70,229,0.22)" : "rgba(15,23,42,0.55)",
      color: "#e5e7eb",
      fontSize: "0.82rem",
      fontWeight: 600,
      textDecoration: "none",
      whiteSpace: "nowrap",
    }) as const;

  return (
    <header
      style={{
        position: "fixed",
        top: 0,
        left: 0,
        right: 0,
        zIndex: 50,
        display: "flex",
        alignItems: "center",
        justifyContent: "space-between",
        gap: "0.75rem",
        flexWrap: "wrap",
        padding: "0.5rem 1rem",
        background: "rgba(15,23,42,0.92)",
        borderBottom: "1px solid rgba(148,163,184,0.18)",
        backdropFilter: "blur(12px)",
        fontFamily: "Inter, ui-sans-serif, system-ui, sans-serif",
      }}
      data-testid="auth-top-nav"
    >
      <div style={{ display: "flex", alignItems: "center", gap: "0.6rem", flexWrap: "wrap" }}>
        <Link href="/" style={{ fontWeight: 700, color: "#f8fafc", textDecoration: "none", fontSize: "0.92rem" }} data-testid="nav-brand">
          RAG Workspace
        </Link>
        {!backendConfigured ? (
          <span style={{ fontSize: "0.72rem", color: "#fbbf24", opacity: 0.95 }} data-testid="nav-backend-warning">
            API URL missing
          </span>
        ) : null}
      </div>

      <nav style={{ display: "flex", alignItems: "center", gap: "0.45rem", flexWrap: "wrap" }}>
        {!loggedIn ? (
          <>
            <Link href="/login" style={navBtn(pathname === "/login")} data-testid="nav-link-login">
              Login
            </Link>
            <Link href="/register" style={navBtn(pathname === "/register")} data-testid="nav-link-register">
              Register
            </Link>
          </>
        ) : (
          <>
            {backendConfigured ? (
              <label style={{ display: "flex", alignItems: "center", gap: "0.35rem", fontSize: "0.76rem", color: "#cbd5e1" }}>
                <span style={{ opacity: 0.75 }}>Library</span>
                <select
                  value={scope}
                  data-testid="nav-workspace-scope-select"
                  onChange={(e) => {
                    const v = e.target.value as WorkspaceScopeValue;
                    writeWorkspaceScope(v);
                    setScope(v);
                  }}
                  style={{
                    padding: "0.28rem 0.45rem",
                    borderRadius: 8,
                    border: "1px solid rgba(148,163,184,0.28)",
                    background: "#0f172a",
                    color: "#e5e7eb",
                    fontSize: "0.76rem",
                    maxWidth: 200,
                  }}
                >
                  <option value="">All documents</option>
                  <option value="personal">Personal only</option>
                  {workspaces.map((w) => (
                    <option key={w.workspace_id} value={w.workspace_id}>
                      Team · {w.name}
                    </option>
                  ))}
                </select>
              </label>
            ) : null}
            {backendConfigured ? <NotificationBell /> : null}
            <Link href="/dashboard" style={navBtn(pathname === "/dashboard" || pathname === "/")} data-testid="nav-link-dashboard">
              Dashboard
            </Link>
            <Link href="/documents" style={navBtn(pathname === "/documents")} data-testid="nav-link-documents">
              Documents
            </Link>
            <Link href="/query" style={navBtn(pathname === "/query")} data-testid="nav-link-query">
              Query
            </Link>
            {isAdmin ? (
              <>
                <Link href="/admin" style={navBtn(pathname === "/admin")} data-testid="nav-link-admin-center">
                  Admin Center
                </Link>
                {showAdminBootstrapUi ? (
                  <Link href="/admin/assign" style={navBtn(pathname === "/admin/assign")} data-testid="nav-link-admin-assign">
                    Promote admin
                  </Link>
                ) : null}
              </>
            ) : null}
            <button
              type="button"
              onClick={logout}
              style={{
                ...navBtn(false),
                cursor: "pointer",
                fontFamily: "inherit",
              }}
              data-testid="nav-button-logout"
            >
              Log out
            </button>
          </>
        )}
      </nav>
    </header>
  );
}
