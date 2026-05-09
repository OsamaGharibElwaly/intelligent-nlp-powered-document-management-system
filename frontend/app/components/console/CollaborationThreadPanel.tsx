"use client";

import { FormEvent, useCallback, useEffect, useState } from "react";

import ws from "./workspace.module.css";

type ThreadRow = {
  thread_id: string;
  question: string;
  answer?: string;
  updated_at?: string;
  discussion?: Array<{ message_id: string; user_id: string; body: string; created_at?: string }>;
};

type CommentRow = {
  comment_id: string;
  user_id: string;
  body: string;
  thread_id?: string | null;
  created_at?: string;
};

type Props = {
  backendUrl: string;
  authHeaders: Record<string, string>;
  documentId: string;
  activeThreadId: string;
  onSelectThread: (id: string) => void;
  pushToast: (type: "success" | "error" | "info", message: string) => void;
  refreshNonce?: number;
};

export function CollaborationThreadPanel({
  backendUrl,
  authHeaders,
  documentId,
  activeThreadId,
  onSelectThread,
  pushToast,
  refreshNonce = 0,
}: Props) {
  const [threads, setThreads] = useState<ThreadRow[]>([]);
  const [threadDetail, setThreadDetail] = useState<ThreadRow | null>(null);
  const [comments, setComments] = useState<CommentRow[]>([]);
  const [discussionBody, setDiscussionBody] = useState("");
  const [commentBody, setCommentBody] = useState("");
  const [busy, setBusy] = useState(false);

  const refreshThreads = useCallback(async () => {
    if (!backendUrl || !authHeaders.Authorization || !documentId.trim()) return;
    const res = await fetch(`${backendUrl}/collaboration/threads?document_id=${encodeURIComponent(documentId.trim())}`, {
      headers: authHeaders,
    });
    const data = (await res.json().catch(() => [])) as ThreadRow[];
    if (res.ok) setThreads(Array.isArray(data) ? data : []);
  }, [backendUrl, authHeaders, documentId]);

  const refreshDetail = useCallback(async () => {
    if (!backendUrl || !authHeaders.Authorization || !activeThreadId.trim()) {
      setThreadDetail(null);
      return;
    }
    const res = await fetch(`${backendUrl}/collaboration/threads/${encodeURIComponent(activeThreadId.trim())}`, {
      headers: authHeaders,
    });
    const data = (await res.json().catch(() => null)) as ThreadRow | null;
    if (res.ok && data) setThreadDetail(data);
  }, [backendUrl, authHeaders, activeThreadId]);

  const refreshComments = useCallback(async () => {
    if (!backendUrl || !authHeaders.Authorization) return;
    const qp = activeThreadId.trim()
      ? `thread_id=${encodeURIComponent(activeThreadId.trim())}`
      : `document_id=${encodeURIComponent(documentId.trim())}`;
    const res = await fetch(`${backendUrl}/collaboration/comments?${qp}`, { headers: authHeaders });
    const data = (await res.json().catch(() => [])) as CommentRow[];
    if (res.ok) setComments(Array.isArray(data) ? data : []);
  }, [backendUrl, authHeaders, documentId, activeThreadId]);

  useEffect(() => {
    void refreshThreads();
  }, [refreshThreads, refreshNonce]);

  useEffect(() => {
    void refreshDetail();
  }, [refreshDetail]);

  useEffect(() => {
    void refreshComments();
  }, [refreshComments]);

  const postDiscussion = async (e: FormEvent) => {
    e.preventDefault();
    if (!activeThreadId.trim() || !discussionBody.trim()) return;
    setBusy(true);
    try {
      const res = await fetch(`${backendUrl}/collaboration/threads/${encodeURIComponent(activeThreadId.trim())}/discussion`, {
        method: "POST",
        headers: { "Content-Type": "application/json", ...authHeaders },
        body: JSON.stringify({ body: discussionBody.trim() }),
      });
      const err = (await res.json().catch(() => ({}))) as { detail?: string };
      if (!res.ok) throw new Error(typeof err.detail === "string" ? err.detail : "Message failed");
      pushToast("success", "Posted to thread");
      setDiscussionBody("");
      await refreshDetail();
    } catch (ex) {
      pushToast("error", ex instanceof Error ? ex.message : "Message failed");
    } finally {
      setBusy(false);
    }
  };

  const postComment = async (e: FormEvent) => {
    e.preventDefault();
    if (!documentId.trim() || !commentBody.trim()) return;
    setBusy(true);
    try {
      const res = await fetch(`${backendUrl}/collaboration/comments`, {
        method: "POST",
        headers: { "Content-Type": "application/json", ...authHeaders },
        body: JSON.stringify({
          document_id: documentId.trim(),
          thread_id: activeThreadId.trim() || null,
          answer_anchor: "main",
          body: commentBody.trim(),
        }),
      });
      const err = (await res.json().catch(() => ({}))) as { detail?: string };
      if (!res.ok) throw new Error(typeof err.detail === "string" ? err.detail : "Comment failed");
      pushToast("success", "Comment saved");
      setCommentBody("");
      await refreshComments();
    } catch (ex) {
      pushToast("error", ex instanceof Error ? ex.message : "Comment failed");
    } finally {
      setBusy(false);
    }
  };

  return (
    <section style={{ display: "grid", gap: "0.65rem", fontSize: "0.78rem" }} data-testid="collaboration-thread-panel">
      <div>
        <h4 style={{ margin: "0 0 0.35rem", fontSize: "0.78rem", textTransform: "uppercase", letterSpacing: "0.06em", opacity: 0.65 }}>
          Query threads
        </h4>
        <div style={{ display: "flex", flexWrap: "wrap", gap: "0.35rem", alignItems: "center" }}>
          <button
            type="button"
            data-testid="collab-refresh-threads"
            onClick={() => void refreshThreads()}
            style={{ padding: "0.35rem 0.55rem", borderRadius: 8, border: "1px solid rgba(148,163,184,0.25)", background: "#0f172a", color: "#e5e7eb", cursor: "pointer" }}
          >
            Refresh
          </button>
          <select
            value={activeThreadId}
            onChange={(e) => onSelectThread(e.target.value)}
            data-testid="collab-thread-select"
            className={ws.inputGlow}
            style={{ flex: "1 1 180px", padding: "0.4rem", borderRadius: 8, border: "1px solid #334155", background: "#0f172a", color: "#e5e7eb" }}
          >
            <option value="">New thread (next query)</option>
            {threads.map((t) => (
              <option key={t.thread_id} value={t.thread_id}>
                {(t.question ?? "").slice(0, 52)}
                {(t.question?.length ?? 0) > 52 ? "…" : ""}
              </option>
            ))}
          </select>
        </div>
      </div>

      {threadDetail && activeThreadId ? (
        <div className={ws.glassElevated} style={{ padding: "0.65rem", borderRadius: 12, maxHeight: 200, overflowY: "auto" }}>
          <p style={{ margin: "0 0 0.35rem", opacity: 0.75 }}>Discussion</p>
          <ul style={{ margin: 0, paddingLeft: "1rem" }}>
            {(threadDetail.discussion ?? []).map((m) => (
              <li key={m.message_id} style={{ marginBottom: "0.35rem" }}>
                <strong>{m.user_id}</strong> · {m.body}
              </li>
            ))}
          </ul>
          <form onSubmit={(ev) => void postDiscussion(ev)} style={{ marginTop: "0.55rem", display: "grid", gap: "0.35rem" }}>
            <textarea
              value={discussionBody}
              onChange={(e) => setDiscussionBody(e.target.value)}
              data-testid="collab-discussion-input"
              placeholder="Follow-up note for the team…"
              rows={2}
              className={ws.inputGlow}
              style={{ padding: "0.45rem", borderRadius: 8, border: "1px solid #334155", background: "#0f172a", color: "#e5e7eb" }}
            />
            <button type="submit" disabled={busy} data-testid="collab-discussion-submit" className={ws.askBtn} style={{ padding: "0.45rem", fontSize: "0.78rem" }}>
              Post message
            </button>
          </form>
        </div>
      ) : null}

      <div className={ws.glassElevated} style={{ padding: "0.65rem", borderRadius: 12 }}>
        <p style={{ margin: "0 0 0.35rem", opacity: 0.75 }}>Comments on answer</p>
        <ul style={{ margin: "0 0 0.45rem", paddingLeft: "1rem", maxHeight: 140, overflowY: "auto" }} data-testid="collab-comments-list">
          {comments.map((c) => (
            <li key={c.comment_id} style={{ marginBottom: "0.35rem" }}>
              <strong>{c.user_id}</strong> · {c.body}
            </li>
          ))}
        </ul>
        <form onSubmit={(ev) => void postComment(ev)} style={{ display: "grid", gap: "0.35rem" }}>
          <textarea
            value={commentBody}
            onChange={(e) => setCommentBody(e.target.value)}
            data-testid="collab-comment-input"
            placeholder="Annotate this answer…"
            rows={2}
            className={ws.inputGlow}
            style={{ padding: "0.45rem", borderRadius: 8, border: "1px solid #334155", background: "#0f172a", color: "#e5e7eb" }}
          />
          <button type="submit" disabled={busy} data-testid="collab-comment-submit" className={ws.askBtn} style={{ padding: "0.45rem", fontSize: "0.78rem" }}>
            Add comment
          </button>
        </form>
      </div>
    </section>
  );
}
