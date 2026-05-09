"use client";

import { FormEvent, useState } from "react";

import ws from "../console/workspace.module.css";
import type { ToastItem } from "../console/ToastStack";

type Props = {
  backendUrl: string;
  authHeaders: Record<string, string>;
  sessionEmail: string;
  pushToast: (type: ToastItem["type"], message: string) => void;
  onPromotedSelfReauth: () => void;
};

export function AdminBootstrapPanel({ backendUrl, authHeaders, sessionEmail, pushToast, onPromotedSelfReauth }: Props) {
  const [secretCode, setSecretCode] = useState("");
  const [confirmSecretCode, setConfirmSecretCode] = useState("");
  const [targetEmail, setTargetEmail] = useState("");
  const [clientError, setClientError] = useState("");
  const [busy, setBusy] = useState(false);

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    setClientError("");
    if (!backendUrl) {
      setClientError("Backend URL is not configured.");
      return;
    }
    if (!authHeaders.Authorization) {
      setClientError("Sign in first.");
      return;
    }
    if (secretCode !== confirmSecretCode) {
      setClientError("Secret code and confirmation must match.");
      return;
    }

    setBusy(true);
    try {
      const res = await fetch(`${backendUrl}/admin/bootstrap/promote`, {
        method: "POST",
        headers: { "Content-Type": "application/json", ...authHeaders },
        body: JSON.stringify({
          secretCode,
          confirmSecretCode,
          targetEmail: targetEmail.trim(),
        }),
      });
      const data = (await res.json().catch(() => ({}))) as { detail?: unknown; message?: string; email?: string; role?: string };
      if (!res.ok) {
        const detail = typeof data.detail === "string" ? data.detail : "Promotion failed";
        setClientError(detail);
        pushToast("error", detail);
        return;
      }
      pushToast("success", "User promoted to admin");
      setSecretCode("");
      setConfirmSecretCode("");
      const promotedEmail = typeof data.email === "string" ? data.email.toLowerCase() : "";
      if (promotedEmail && promotedEmail === sessionEmail.trim().toLowerCase()) {
        pushToast("info", "Sign in again to refresh your session token with admin role.");
        onPromotedSelfReauth();
      }
      setTargetEmail("");
    } catch {
      const msg = "Network error — could not reach bootstrap endpoint.";
      setClientError(msg);
      pushToast("error", msg);
    } finally {
      setBusy(false);
    }
  };

  return (
    <section
      className={ws.glassElevated}
      style={{ padding: "1.05rem", display: "grid", gap: "0.65rem", borderStyle: "dashed", borderColor: "rgba(251,191,36,0.35)" }}
      data-testid="admin-bootstrap-panel"
    >
      <h3 style={{ margin: 0, fontSize: "0.98rem" }}>Development · Admin bootstrap</h3>
      <p style={{ margin: 0, fontSize: "0.78rem", opacity: 0.75, lineHeight: 1.45 }}>
        Promote any existing account to <strong>admin</strong> using the server-side <code>ADMIN_BOOTSTRAP_SECRET</code> only. Disable this UI in
        production via build env. Secrets are validated on the backend only.
      </p>
      {clientError ? (
        <div
          role="alert"
          style={{ margin: 0, padding: "0.45rem 0.55rem", borderRadius: 8, background: "rgba(127,29,29,0.35)", border: "1px solid rgba(248,113,113,0.4)", fontSize: "0.82rem" }}
          data-testid="admin-bootstrap-client-error"
        >
          {clientError}
        </div>
      ) : null}
      <form onSubmit={(ev) => void submit(ev)} style={{ display: "grid", gap: "0.55rem" }}>
        <label style={{ display: "grid", gap: "0.25rem", fontSize: "0.78rem" }}>
          Secret code
          <input
            data-testid="admin-bootstrap-secret"
            type="password"
            autoComplete="off"
            value={secretCode}
            onChange={(e) => setSecretCode(e.target.value)}
            className={ws.inputGlow}
            style={{ padding: "0.5rem", borderRadius: 10, border: "1px solid #334155", background: "#0f172a", color: "#e5e7eb" }}
          />
        </label>
        <label style={{ display: "grid", gap: "0.25rem", fontSize: "0.78rem" }}>
          Confirm secret code
          <input
            data-testid="admin-bootstrap-confirm"
            type="password"
            autoComplete="off"
            value={confirmSecretCode}
            onChange={(e) => setConfirmSecretCode(e.target.value)}
            className={ws.inputGlow}
            style={{ padding: "0.5rem", borderRadius: 10, border: "1px solid #334155", background: "#0f172a", color: "#e5e7eb" }}
          />
        </label>
        <label style={{ display: "grid", gap: "0.25rem", fontSize: "0.78rem" }}>
          Target email
          <input
            data-testid="admin-bootstrap-target-email"
            type="email"
            required
            value={targetEmail}
            onChange={(e) => setTargetEmail(e.target.value)}
            placeholder="user@example.com"
            className={ws.inputGlow}
            style={{ padding: "0.5rem", borderRadius: 10, border: "1px solid #334155", background: "#0f172a", color: "#e5e7eb" }}
          />
        </label>
        <button
          type="submit"
          data-testid="admin-bootstrap-submit"
          disabled={busy}
          style={{
            padding: "0.55rem",
            borderRadius: 10,
            border: "1px solid rgba(251,191,36,0.45)",
            background: busy ? "rgba(120,53,15,0.25)" : "rgba(180,83,9,0.35)",
            color: "#fef3c7",
            fontWeight: 700,
            cursor: busy ? "wait" : "pointer",
          }}
        >
          {busy ? "Promoting…" : "Promote to Admin"}
        </button>
      </form>
    </section>
  );
}
