"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useCallback, useEffect, useState } from "react";

import type { ApiNotification } from "../components/layout/NotificationBell";
import { readStoredAuth } from "../lib/authStorage";
import { navigateFromNotificationLink } from "../lib/notificationNavigation";

const backendUrl = process.env.NEXT_PUBLIC_BACKEND_URL ?? "";

export default function NotificationsPage() {
  const router = useRouter();
  const [items, setItems] = useState<ApiNotification[]>([]);
  const [busy, setBusy] = useState(false);

  const refresh = useCallback(async () => {
    const a = readStoredAuth();
    if (!backendUrl || !a?.token) return;
    setBusy(true);
    try {
      const headers = { Authorization: `Bearer ${a.token}` };
      const res = await fetch(`${backendUrl}/notifications?limit=200`, { headers });
      const data = (await res.json().catch(() => [])) as ApiNotification[];
      if (res.ok && Array.isArray(data)) setItems(data);
    } finally {
      setBusy(false);
    }
  }, []);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  const markRead = async (id: string) => {
    const a = readStoredAuth();
    if (!backendUrl || !a?.token) return;
    await fetch(`${backendUrl}/notifications/${encodeURIComponent(id)}/read`, {
      method: "PATCH",
      headers: { Authorization: `Bearer ${a.token}` },
    });
    setItems((prev) => prev.map((x) => (x.notification_id === id ? { ...x, read: true } : x)));
  };

  const markAll = async () => {
    const a = readStoredAuth();
    if (!backendUrl || !a?.token) return;
    await fetch(`${backendUrl}/notifications/mark-all-read`, {
      method: "POST",
      headers: { Authorization: `Bearer ${a.token}` },
    });
    setItems((prev) => prev.map((x) => ({ ...x, read: true })));
  };

  const openRow = async (n: ApiNotification) => {
    await markRead(n.notification_id);
    navigateFromNotificationLink(router, n.link ?? {});
  };

  return (
    <main
      style={{
        minHeight: "calc(100vh - 3.35rem)",
        padding: "1.25rem 1rem 2rem",
        maxWidth: 720,
        margin: "0 auto",
        fontFamily: "Inter, ui-sans-serif, system-ui, sans-serif",
        color: "#e5e7eb",
        background: "linear-gradient(180deg,rgb(255, 255, 255),rgb(87, 134, 244))",
      }}
      data-testid="notifications-page"
    >
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", gap: "1rem", flexWrap: "wrap", marginBottom: "1rem" }}>
        <h1 style={{ margin: 0, fontSize: "1.35rem" }}>Notifications</h1>
        <div style={{ display: "flex", gap: "0.5rem", flexWrap: "wrap" }}>
          <button
            type="button"
            data-testid="notifications-mark-all-read"
            disabled={busy}
            onClick={() => void markAll()}
            style={{
              padding: "0.45rem 0.75rem",
              borderRadius: 10,
              border: "1px solid rgba(255, 255, 255, 0.75)",
              background: "#1e293b",
              color: "#e5e7eb",
              cursor: "pointer",
              fontWeight: 600,
            }}
          >
            Mark all read
          </button>
          <Link href="/dashboard" data-testid="notifications-back" style={{ padding: "0.45rem 0.75rem", borderRadius: 10, border: "1px solid rgba(99,102,241,0.45)", color: "#c7d2fe", fontWeight: 600, textDecoration: "none" }}>
            Workspace
          </Link>
        </div>
      </div>

      <ul style={{ listStyle: "none", margin: 0, padding: 0, display: "grid", gap: "0.65rem" }}>
        {items.map((n) => (
          <li
            key={n.notification_id}
            data-testid={`notifications-list-item-${n.notification_id}`}
            style={{
              padding: "0.85rem 1rem",
              borderRadius: 12,
              border: "1px solid rgba(179, 210, 253, 0.95)",
              background: n.read ? "rgba(89, 122, 198, 0.87)" : "rgba(81, 73, 227, 0.84)",
            }}
          >
            <div style={{ display: "flex", justifyContent: "space-between", gap: "0.75rem", alignItems: "flex-start", flexWrap: "wrap" }}>
              <div style={{ flex: "1 1 220px" }}>
                <div style={{ fontWeight: 700, marginBottom: "0.25rem" }}>{n.title}</div>
                {n.body ? <p style={{ margin: "0 0 0.35rem", opacity: 0.85, fontSize: "0.88rem", lineHeight: 1.45 }}>{n.body}</p> : null}
                <span style={{ fontSize: "0.72rem", opacity: 0.55 }}>{n.created_at}</span>
              </div>
              <div style={{ display: "flex", gap: "0.35rem", flexShrink: 0 }}>
                {!n.read ? (
                  <button
                    type="button"
                    data-testid={`notifications-mark-read-${n.notification_id}`}
                    onClick={() => void markRead(n.notification_id)}
                    style={{
                      padding: "0.35rem 0.55rem",
                      borderRadius: 8,
                      border: "1px solid rgb(176, 202, 238)",
                      background: "#0f172a",
                      color: "#e5e7eb",
                      cursor: "pointer",
                      fontSize: "0.72rem",
                    }}
                  >
                    Mark read
                  </button>
                ) : null}
                <button
                  type="button"
                  data-testid={`notifications-open-${n.notification_id}`}
                  onClick={() => void openRow(n)}
                  style={{
                    padding: "0.35rem 0.55rem",
                    borderRadius: 8,
                    border: "1px solid rgba(52, 211, 153, 0.9)",
                    background: "rgba(16, 185, 129, 0.87)",
                    color: "#a7f3d0",
                    cursor: "pointer",
                    fontSize: "0.72rem",
                    fontWeight: 600,
                  }}
                >
                  Open
                </button>
              </div>
            </div>
          </li>
        ))}
      </ul>

      {!busy && items.length === 0 ? (
        <p style={{ opacity: 0.75, marginTop: "1.5rem" }} data-testid="notifications-empty">
          You have no notifications yet. Activity from your team and AI queries will appear here.
        </p>
      ) : null}
    </main>
  );
}
