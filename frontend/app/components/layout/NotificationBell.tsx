"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useCallback, useEffect, useRef, useState } from "react";

import { readStoredAuth } from "../../lib/authStorage";
import { navigateFromNotificationLink, type NotificationLinkPayload } from "../../lib/notificationNavigation";

const backendUrl = process.env.NEXT_PUBLIC_BACKEND_URL ?? "";

export type ApiNotification = {
  notification_id: string;
  title: string;
  body: string;
  type: string;
  read: boolean;
  created_at: string;
  link: NotificationLinkPayload;
};

export function NotificationBell() {
  const router = useRouter();
  const [open, setOpen] = useState(false);
  const [items, setItems] = useState<ApiNotification[]>([]);
  const [unread, setUnread] = useState(0);
  const wrapRef = useRef<HTMLDivElement>(null);

  const fetchUnreadCount = useCallback(async () => {
    const auth = readStoredAuth();
    if (!backendUrl || !auth?.token) return;
    const res = await fetch(`${backendUrl}/notifications/unread-count`, {
      headers: { Authorization: `Bearer ${auth.token}` },
    });
    const data = (await res.json().catch(() => ({}))) as { unread?: number };
    if (res.ok && typeof data.unread === "number") setUnread(data.unread);
  }, []);

  const fetchList = useCallback(async () => {
    const auth = readStoredAuth();
    if (!backendUrl || !auth?.token) return;
    const res = await fetch(`${backendUrl}/notifications?limit=25`, {
      headers: { Authorization: `Bearer ${auth.token}` },
    });
    const data = (await res.json().catch(() => [])) as ApiNotification[];
    if (res.ok && Array.isArray(data)) setItems(data);
  }, []);

  useEffect(() => {
    void fetchUnreadCount();
    const t = window.setInterval(() => void fetchUnreadCount(), 25000);
    const onVis = () => {
      if (document.visibilityState === "visible") void fetchUnreadCount();
    };
    document.addEventListener("visibilitychange", onVis);
    return () => {
      window.clearInterval(t);
      document.removeEventListener("visibilitychange", onVis);
    };
  }, [fetchUnreadCount]);

  useEffect(() => {
    if (!open) return;
    void fetchList();
    void fetchUnreadCount();
  }, [open, fetchList, fetchUnreadCount]);

  useEffect(() => {
    if (!open) return;
    const onDoc = (e: MouseEvent) => {
      if (!wrapRef.current?.contains(e.target as Node)) setOpen(false);
    };
    document.addEventListener("mousedown", onDoc);
    return () => document.removeEventListener("mousedown", onDoc);
  }, [open]);

  const markRead = async (id: string) => {
    const auth = readStoredAuth();
    if (!backendUrl || !auth?.token) return;
    await fetch(`${backendUrl}/notifications/${encodeURIComponent(id)}/read`, {
      method: "PATCH",
      headers: { Authorization: `Bearer ${auth.token}` },
    });
    setItems((prev) => prev.map((x) => (x.notification_id === id ? { ...x, read: true } : x)));
    void fetchUnreadCount();
  };

  const openAndNavigate = async (n: ApiNotification) => {
    await markRead(n.notification_id);
    navigateFromNotificationLink(router, n.link ?? {});
    setOpen(false);
  };

  return (
    <div ref={wrapRef} style={{ position: "relative" }} data-testid="notification-bell-root">
      <button
        type="button"
        data-testid="notification-bell-toggle"
        aria-expanded={open}
        onClick={() => setOpen((o) => !o)}
        title="Notifications"
        style={{
          position: "relative",
          padding: "0.35rem 0.55rem",
          borderRadius: 10,
          border: "1px solid rgba(148,163,184,0.28)",
          background: "#0f172a",
          color: "#e5e7eb",
          cursor: "pointer",
          fontSize: "1rem",
          lineHeight: 1,
        }}
      >
        🔔
        {unread > 0 ? (
          <span
            data-testid="notification-bell-badge"
            style={{
              position: "absolute",
              top: -4,
              right: -4,
              minWidth: 18,
              height: 18,
              padding: "0 4px",
              borderRadius: 999,
              background: "#ef4444",
              color: "white",
              fontSize: "0.68rem",
              fontWeight: 800,
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
            }}
          >
            {unread > 99 ? "99+" : unread}
          </span>
        ) : null}
      </button>

      {open ? (
        <div
          data-testid="notification-dropdown"
          style={{
            position: "absolute",
            right: 0,
            top: "calc(100% + 6px)",
            width: 340,
            maxHeight: 420,
            overflowY: "auto",
            background: "rgba(15,23,42,0.98)",
            border: "1px solid rgba(148,163,184,0.25)",
            borderRadius: 12,
            boxShadow: "0 16px 48px rgba(0,0,0,0.45)",
            zIndex: 80,
            padding: "0.5rem 0",
          }}
        >
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", padding: "0.35rem 0.75rem 0.55rem", borderBottom: "1px solid rgba(148,163,184,0.12)" }}>
            <span style={{ fontSize: "0.78rem", fontWeight: 700 }}>Notifications</span>
            <Link href="/notifications" data-testid="notification-view-all" style={{ fontSize: "0.72rem", color: "#a5b4fc", fontWeight: 600 }} onClick={() => setOpen(false)}>
              View all
            </Link>
          </div>
          {items.length === 0 ? (
            <p style={{ margin: "0.75rem", fontSize: "0.78rem", opacity: 0.7 }}>No notifications yet.</p>
          ) : (
            <ul style={{ listStyle: "none", margin: 0, padding: 0 }}>
              {items.map((n) => (
                <li key={n.notification_id}>
                  <button
                    type="button"
                    data-testid={`notification-row-${n.notification_id}`}
                    onClick={() => void openAndNavigate(n)}
                    style={{
                      width: "100%",
                      textAlign: "left",
                      padding: "0.55rem 0.75rem",
                      border: "none",
                      borderBottom: "1px solid rgba(148,163,184,0.08)",
                      background: n.read ? "transparent" : "rgba(79,70,229,0.12)",
                      cursor: "pointer",
                      color: "#e5e7eb",
                      fontSize: "0.76rem",
                      lineHeight: 1.35,
                    }}
                  >
                    <div style={{ fontWeight: 700, marginBottom: "0.15rem" }}>{n.title}</div>
                    {n.body ? <div style={{ opacity: 0.82 }}>{n.body}</div> : null}
                    <div style={{ marginTop: "0.25rem", opacity: 0.55, fontSize: "0.68rem" }}>{n.type}</div>
                  </button>
                </li>
              ))}
            </ul>
          )}
        </div>
      ) : null}
    </div>
  );
}
