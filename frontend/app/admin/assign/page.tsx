"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useCallback, useEffect, useState } from "react";

import { AdminBootstrapPanel } from "../../components/admin/AdminBootstrapPanel";
import ux from "../../components/auth/authPages.module.css";
import type { ToastItem } from "../../components/console/ToastStack";
import { ToastStack } from "../../components/console/ToastStack";
import { clearStoredAuth, readStoredAuth } from "../../lib/authStorage";

const backendUrl = process.env.NEXT_PUBLIC_BACKEND_URL ?? "";

const showAdminBootstrapUi =
  process.env.NODE_ENV === "development" || process.env.NEXT_PUBLIC_ENABLE_ADMIN_BOOTSTRAP_UI === "true";

export default function AdminAssignPage() {
  const router = useRouter();
  const [gate, setGate] = useState<"loading" | "ok" | "denied">("loading");
  const [sessionEmail, setSessionEmail] = useState("");
  const [toasts, setToasts] = useState<ToastItem[]>([]);

  const authHeaders = (() => {
    const h: Record<string, string> = {};
    const a = readStoredAuth();
    if (a?.token) h.Authorization = `Bearer ${a.token}`;
    return h;
  })();

  const pushToast = useCallback((type: ToastItem["type"], message: string) => {
    const id = `${Date.now()}-${Math.random().toString(36).slice(2, 9)}`;
    setToasts((prev) => [...prev, { id, type, message }]);
    window.setTimeout(() => {
      setToasts((prev) => prev.filter((t) => t.id !== id));
    }, 4200);
  }, []);

  useEffect(() => {
    const a = readStoredAuth();
    if (!a?.token) {
      router.replace("/login");
      setGate("denied");
      return;
    }
    if (a.role !== "admin") {
      router.replace("/dashboard");
      setGate("denied");
      return;
    }
    setSessionEmail(a.email);
    setGate("ok");
  }, [router]);

  const handlePromotedSelfReauth = useCallback(() => {
    clearStoredAuth();
    pushToast("info", "Sign in again to refresh your session token with admin role.");
    router.replace("/login");
  }, [pushToast, router]);

  if (!showAdminBootstrapUi) {
    return (
      <main className={ux.page} data-testid="admin-assign-disabled">
        <div className={ux.card}>
          <h1 className={ux.title}>Admin promotion UI disabled</h1>
          <p className={ux.sub}>
            This bootstrap flow is available only in development or when{" "}
            <code style={{ opacity: 0.9 }}>NEXT_PUBLIC_ENABLE_ADMIN_BOOTSTRAP_UI</code> is enabled.
          </p>
          <Link href="/dashboard" data-testid="admin-assign-back-link" className={ux.footer} style={{ display: "block" }}>
            Back to dashboard
          </Link>
        </div>
      </main>
    );
  }

  if (gate !== "ok") {
    return (
      <main className={ux.page} data-testid="admin-assign-loading">
        <p style={{ margin: 0, opacity: 0.85 }}>{gate === "loading" ? "Checking access…" : "Redirecting…"}</p>
      </main>
    );
  }

  return (
    <main className={ux.page} style={{ alignItems: "flex-start", paddingTop: "2rem" }} data-testid="admin-assign-page">
      <ToastStack toasts={toasts} />
      <div style={{ width: "100%", maxWidth: 520 }}>
        <div style={{ marginBottom: "1rem" }}>
          <Link href="/dashboard" style={{ color: "#a5b4fc", fontSize: "0.86rem", fontWeight: 600 }} data-testid="admin-assign-nav-dashboard">
            ← Dashboard
          </Link>
        </div>
        <AdminBootstrapPanel
          backendUrl={backendUrl}
          authHeaders={authHeaders}
          sessionEmail={sessionEmail}
          pushToast={pushToast}
          onPromotedSelfReauth={handlePromotedSelfReauth}
        />
      </div>
    </main>
  );
}
