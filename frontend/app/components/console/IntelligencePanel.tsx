"use client";

import { useMemo, useState } from "react";

import ws from "./workspace.module.css";

export type ChunkHit = {
  chunk_id?: string;
  document_id?: string;
  score?: number;
  content?: string;
  metadata?: Record<string, unknown>;
};

export type QueryUiPhase = "idle" | "thinking" | "retrying";

export type AnswerFaultInfo = {
  degraded: boolean;
  degradedReason: string | null;
  retrievalDegraded: boolean;
  llmAttempts: number | null;
};

type Props = {
  selectedDocTitle?: string | null;
  selectedDocMeta?: { id?: string; collection_id?: string } | null;
  chunks: ChunkHit[];
  answer: string;
  confidence?: number | null;
  queryPhase?: QueryUiPhase;
  retrieveFaultNotice?: string | null;
  answerFault?: AnswerFaultInfo | null;
  feedbackChoice: "positive" | "negative" | null;
  feedbackSent: boolean;
  feedbackBusy?: boolean;
  feedbackNegativeComment: string;
  onFeedbackNegativeCommentChange: (v: string) => void;
  onFeedbackPositive: () => void;
  onFeedbackNegativeIntent: () => void;
  onFeedbackNegativeSubmit: () => void;
  loadingChunks?: boolean;
  feedbackAvailable?: boolean;
  evidenceSpans?: Array<{
    paragraph_index: number;
    chunk_id: string;
    document_id: string;
    span_start: number;
    span_end: number;
    span_text: string;
  }>;
  answerCitations?: Array<{ paragraph_index: number; citations: Array<{ chunk_id: string; document_id: string }> }>;
};

function confidenceTone(score: number | undefined | null): string {
  if (score == null || Number.isNaN(score)) return ws.confBadgeNeutral;
  if (score >= 0.75) return ws.confBadgeOk;
  if (score >= 0.45) return ws.confBadgeWarn;
  return ws.confBadgeBad;
}

function humanizeFaultReason(reason: string | null | undefined): string {
  if (!reason) return "";
  if (reason === "llm_unavailable") return "AI synthesis temporarily unavailable — showing retrieval-grounded excerpt instead.";
  if (reason === "llm_response_invalid") return "AI returned unexpected structured output — excerpt fallback applied.";
  return reason.replace(/_/g, " ");
}

function chunkScoreBar(score: number | undefined): number {
  if (score == null || Number.isNaN(score)) return 0;
  const n = Math.min(1, Math.max(0, score > 1 ? 1 / (1 + Math.exp(-score / 4)) : score));
  return Math.round(n * 100);
}

export function IntelligencePanel({
  selectedDocTitle,
  selectedDocMeta,
  chunks,
  answer,
  confidence,
  feedbackChoice,
  feedbackSent,
  feedbackBusy,
  feedbackNegativeComment,
  onFeedbackNegativeCommentChange,
  onFeedbackPositive,
  onFeedbackNegativeIntent,
  onFeedbackNegativeSubmit,
  loadingChunks,
  feedbackAvailable = true,
  evidenceSpans = [],
  answerCitations = [],
  queryPhase = "idle",
  retrieveFaultNotice = null,
  answerFault = null,
}: Props) {
  const [answerExpanded, setAnswerExpanded] = useState(true);
  const answerParagraphs = useMemo(() => answer.split(/\n+/).filter(Boolean), [answer]);

  return (
    <div className={`${ws.intelPanel}`} data-testid="intelligence-panel">
      <div style={{ padding: "1rem", borderBottom: "1px solid rgba(148,163,184,0.12)", flexShrink: 0 }}>
        <h3 style={{ margin: "0 0 0.35rem", fontSize: "0.95rem", letterSpacing: "-0.02em" }}>Context</h3>
        <p style={{ margin: 0, fontSize: "0.76rem", opacity: 0.72 }}>Live retrieval · answer · confidence · feedback</p>
      </div>
      <div className={ws.intelScroll}>
        <section style={{ padding: "0.85rem 1rem", borderBottom: "1px solid rgba(148,163,184,0.08)" }}>
          <h4 style={{ margin: "0 0 0.45rem", fontSize: "0.78rem", textTransform: "uppercase", letterSpacing: "0.06em", opacity: 0.65 }}>
            Document
          </h4>
          {selectedDocMeta?.id ? (
            <div style={{ fontSize: "0.82rem", lineHeight: 1.45 }}>
              <div data-testid="intel-doc-title">{selectedDocTitle || "Untitled"}</div>
              <div style={{ opacity: 0.68, fontFamily: "ui-monospace, monospace", fontSize: "0.72rem", marginTop: "0.25rem", wordBreak: "break-all" }}>
                {selectedDocMeta.id}
              </div>
              {selectedDocMeta.collection_id ? (
                <div style={{ opacity: 0.55, fontSize: "0.72rem", marginTop: "0.2rem" }}>Collection · {selectedDocMeta.collection_id}</div>
              ) : null}
            </div>
          ) : (
            <div data-testid="intel-empty-doc" style={{ fontSize: "0.82rem", opacity: 0.65 }}>
              Select a document or paste an ID to attach metadata here.
            </div>
          )}
        </section>

        <section style={{ padding: "0.85rem 1rem", borderBottom: "1px solid rgba(148,163,184,0.08)" }}>
          {retrieveFaultNotice ? (
            <div className={ws.faultBannerError} data-testid="intel-retrieve-fault">
              {retrieveFaultNotice}
            </div>
          ) : null}
          {loadingChunks || queryPhase !== "idle" ? (
            <div className={ws.thinkingStrip} data-testid="intel-query-phase">
              <span className={ws.thinkingDot} aria-hidden />
              <span>{queryPhase === "retrying" ? "Retrying request…" : "AI processing pipeline…"}</span>
            </div>
          ) : null}
          {answerFault?.retrievalDegraded ? (
            <div className={ws.faultBanner} data-testid="intel-retrieval-degraded">
              Embedding step unavailable — results used keyword-only ranking for this request.
            </div>
          ) : null}
          {answerFault?.degraded ? (
            <div className={ws.faultBanner} data-testid="intel-answer-degraded">
              {humanizeFaultReason(answerFault.degradedReason)}
              {answerFault.llmAttempts != null ? ` (${answerFault.llmAttempts} LLM attempts)` : ""}
            </div>
          ) : null}
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", gap: "0.5rem" }}>
            <h4 style={{ margin: 0, fontSize: "0.78rem", textTransform: "uppercase", letterSpacing: "0.06em", opacity: 0.65 }}>Answer</h4>
            <button
              type="button"
              data-testid="intel-answer-toggle"
              onClick={() => setAnswerExpanded((e) => !e)}
              style={{
                fontSize: "0.72rem",
                padding: "0.25rem 0.45rem",
                borderRadius: 8,
                border: "1px solid rgba(148,163,184,0.25)",
                background: "transparent",
                color: "#cbd5e1",
                cursor: "pointer",
              }}
            >
              {answerExpanded ? "Collapse" : "Expand"}
            </button>
          </div>
          {confidence != null ? (
            <div style={{ marginTop: "0.45rem", display: "flex", alignItems: "center", gap: "0.45rem", flexWrap: "wrap" }}>
              <span className={`${ws.confBadge} ${confidenceTone(confidence)}`} data-testid="confidence-score">
                Confidence {(confidence * 100).toFixed(0)}%
              </span>
            </div>
          ) : (
            <p style={{ margin: "0.45rem 0 0", fontSize: "0.76rem", opacity: 0.55 }} data-testid="confidence-empty">
              Run a query to compute confidence.
            </p>
          )}
          {answerExpanded ? (
            answerParagraphs.length ? (
              <div data-testid="intel-answer" style={{ marginTop: "0.65rem", fontSize: "0.88rem", lineHeight: 1.55 }}>
                <div data-testid="answer-output">
                  {answerParagraphs.map((p, i) => (
                    <p key={`${i}-${p.slice(0, 12)}`} className={`${ws.answerFade}`} style={{ animationDelay: `${Math.min(i, 8) * 70}ms`, margin: "0 0 0.65rem" }}>
                      {p}
                    </p>
                  ))}
                </div>
                {evidenceSpans.length > 0 ? (
                  <ul data-testid="evidence-spans-list" style={{ marginTop: "0.75rem", paddingLeft: "1.1rem", fontSize: "0.78rem", opacity: 0.92 }}>
                    {evidenceSpans.map((ev, i) => (
                      <li key={`${ev.chunk_id}-${ev.span_start}-${i}`} style={{ marginBottom: "0.35rem" }}>
                        <strong>P{ev.paragraph_index + 1}</strong> ·{" "}
                        <mark style={{ background: "rgba(250,204,21,0.18)", color: "#fef9c3", padding: "0 2px", borderRadius: 4 }}>{ev.span_text}</mark>
                      </li>
                    ))}
                  </ul>
                ) : null}
                {answerCitations.length > 0 ? (
                  <ul data-testid="answer-citations" style={{ marginTop: "0.55rem", paddingLeft: "1.1rem", fontSize: "0.78rem", opacity: 0.9 }}>
                    {answerCitations.map((block) => (
                      <li key={`p-${block.paragraph_index}`} style={{ marginBottom: "0.35rem" }}>
                        Paragraph {block.paragraph_index + 1}: {block.citations.map((c) => `${c.chunk_id}`).join(", ")}
                      </li>
                    ))}
                  </ul>
                ) : null}
              </div>
            ) : (
              <p data-testid="intel-answer-empty" style={{ margin: "0.65rem 0 0", fontSize: "0.82rem", opacity: 0.58 }}>
                Your grounded answer will stream here after you Ask AI.
              </p>
            )
          ) : null}
        </section>

        <section style={{ padding: "0.85rem 1rem", borderBottom: "1px solid rgba(148,163,184,0.08)" }}>
          <h4 style={{ margin: "0 0 0.55rem", fontSize: "0.78rem", textTransform: "uppercase", letterSpacing: "0.06em", opacity: 0.65 }}>
            Retrieved chunks
          </h4>
          {loadingChunks ? (
            <div data-testid="chunks-skeleton" style={{ display: "grid", gap: "0.55rem" }}>
              {[0, 1, 2].map((i) => (
                <div key={i} className={ws.skeletonLine} style={{ height: 52 }} />
              ))}
            </div>
          ) : chunks.length === 0 ? (
            <p data-testid="chunks-empty" style={{ margin: 0, fontSize: "0.82rem", opacity: 0.58 }}>
              {retrieveFaultNotice
                ? "Could not load chunks — fix retrieval errors above or retry."
                : "Chunk evidence shows here after retrieval — hover cards for full text."}
            </p>
          ) : (
            <ul data-testid="chunks-list" style={{ listStyle: "none", margin: 0, padding: 0, display: "grid", gap: "0.55rem" }}>
              {chunks.map((c, idx) => (
                <ChunkCard key={c.chunk_id ?? `${idx}`} chunk={c} idx={idx} />
              ))}
            </ul>
          )}
        </section>

        <section style={{ padding: "0.85rem 1rem 1.25rem" }}>
          <h4 style={{ margin: "0 0 0.55rem", fontSize: "0.78rem", textTransform: "uppercase", letterSpacing: "0.06em", opacity: 0.65 }}>
            Feedback
          </h4>
          <div style={{ display: "flex", gap: "0.55rem", flexWrap: "wrap", alignItems: "center" }}>
            <button
              type="button"
              data-testid="feedback-positive-button"
              className={`${ws.feedbackBtn} ${feedbackChoice === "positive" ? ws.feedbackBtnActivePos : ""}`}
              onClick={() => onFeedbackPositive()}
              disabled={feedbackSent || feedbackBusy || !feedbackAvailable}
            >
              👍 Helpful
            </button>
            <button
              type="button"
              data-testid="feedback-negative-button"
              className={`${ws.feedbackBtn} ${feedbackChoice === "negative" ? ws.feedbackBtnActiveNeg : ""}`}
              onClick={() => onFeedbackNegativeIntent()}
              disabled={feedbackSent || feedbackBusy || !feedbackAvailable}
            >
              👎 Not helpful
            </button>
          </div>
          {feedbackChoice === "negative" && !feedbackSent ? (
            <>
              <label style={{ display: "grid", gap: "0.35rem", marginTop: "0.65rem", fontSize: "0.78rem" }}>
                Optional note
                <textarea
                  data-testid="feedback-negative-comment"
                  value={feedbackNegativeComment}
                  onChange={(e) => onFeedbackNegativeCommentChange(e.target.value)}
                  rows={2}
                  className={ws.inputGlow}
                  style={{
                    padding: "0.55rem",
                    borderRadius: 10,
                    border: "1px solid rgba(51,65,85,0.85)",
                    background: "rgba(15,23,42,0.85)",
                    color: "#e5e7eb",
                    resize: "vertical",
                  }}
                />
              </label>
              <button
                type="button"
                data-testid="feedback-negative-submit"
                className={ws.askBtn}
                style={{ marginTop: "0.55rem", padding: "0.55rem 1rem", fontSize: "0.82rem" }}
                disabled={feedbackBusy || !feedbackAvailable}
                onClick={() => onFeedbackNegativeSubmit()}
              >
                {feedbackBusy ? "Sending…" : "Send feedback"}
              </button>
            </>
          ) : null}
          {feedbackSent ? (
            <p data-testid="feedback-sent" style={{ margin: "0.55rem 0 0", fontSize: "0.78rem", color: "#86efac" }}>
              Thanks — feedback recorded.
            </p>
          ) : null}
        </section>
      </div>
    </div>
  );
}

function ChunkCard({ chunk, idx }: { chunk: ChunkHit; idx: number }) {
  const [open, setOpen] = useState(false);
  const preview = (chunk.content ?? "").slice(0, 220);
  const rest = (chunk.content ?? "").slice(220);
  const bar = chunkScoreBar(chunk.score);

  return (
    <li>
      <button
        type="button"
        data-testid={`chunk-card-${idx}`}
        className={ws.chunkCard}
        onClick={() => setOpen((o) => !o)}
        aria-expanded={open}
      >
        <div style={{ display: "flex", justifyContent: "space-between", gap: "0.45rem", alignItems: "baseline", flexWrap: "wrap" }}>
          <span style={{ fontSize: "0.72rem", opacity: 0.72 }} title={chunk.document_id}>
            Source · {(chunk.document_id ?? "—").slice(0, 14)}
            {(chunk.document_id?.length ?? 0) > 14 ? "…" : ""}
          </span>
          <span style={{ fontSize: "0.72rem", fontVariantNumeric: "tabular-nums" }}>
            {chunk.score != null ? `score ${chunk.score.toFixed(3)}` : "score —"}
          </span>
        </div>
        <div style={{ marginTop: "0.45rem", height: 6, borderRadius: 999, background: "rgba(51,65,85,0.85)", overflow: "hidden" }} aria-hidden>
          <div style={{ height: "100%", width: `${bar}%`, borderRadius: 999, background: "linear-gradient(90deg,#22c55e,#a3e635)" }} />
        </div>
        <p style={{ margin: "0.55rem 0 0", fontSize: "0.82rem", lineHeight: 1.45, textAlign: "left", whiteSpace: "pre-wrap" }}>
          <mark style={{ background: "rgba(250,204,21,0.22)", color: "#fef9c3", padding: "0 2px", borderRadius: 4 }}>{preview}</mark>
          {!open && rest ? "…" : null}
          {open && rest ? rest : null}
        </p>
        <span style={{ display: "block", marginTop: "0.35rem", fontSize: "0.68rem", opacity: 0.55 }}>
          {open ? "Click to collapse" : "Click to expand · hover for elevation"}
        </span>
      </button>
    </li>
  );
}
