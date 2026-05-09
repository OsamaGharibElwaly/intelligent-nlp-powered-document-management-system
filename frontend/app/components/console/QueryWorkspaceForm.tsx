"use client";

import { FormEvent } from "react";

import ws from "./workspace.module.css";

type Props = {
  documentId: string;
  onDocumentIdChange: (v: string) => void;
  question: string;
  onQuestionChange: (v: string) => void;
  answerMode: "strict" | "flexible";
  onAnswerModeChange: (v: "strict" | "flexible") => void;
  answerLength: "short" | "medium" | "detailed";
  onAnswerLengthChange: (v: "short" | "medium" | "detailed") => void;
  topK: number;
  onTopKChange: (v: number) => void;
  onSubmit: (e: FormEvent) => void;
  canQuery: boolean;
  isQuerying: boolean;
  statusLine?: string;
};

const SUGGESTIONS = [
  "Summarize the key obligations mentioned in this document.",
  "What definitions does the document provide?",
  "List risks or warnings explicitly stated.",
  "Who are the parties and what roles do they have?",
];

function lengthFromSlider(v: number): "short" | "medium" | "detailed" {
  if (v <= 33) return "short";
  if (v <= 66) return "medium";
  return "detailed";
}

function sliderFromLength(l: "short" | "medium" | "detailed"): number {
  if (l === "short") return 0;
  if (l === "medium") return 50;
  return 100;
}

export function QueryWorkspaceForm({
  documentId,
  onDocumentIdChange,
  question,
  onQuestionChange,
  answerMode,
  onAnswerModeChange,
  answerLength,
  onAnswerLengthChange,
  topK,
  onTopKChange,
  onSubmit,
  canQuery,
  isQuerying,
  statusLine = "",
}: Props) {
  const lenSlider = sliderFromLength(answerLength);

  return (
    <form onSubmit={onSubmit} className={`${ws.glassElevated}`} style={{ padding: "1.15rem", display: "grid", gap: "1rem" }}>
      <div>
        <h2 style={{ margin: "0 0 0.35rem", fontSize: "1.05rem" }}>Query workspace</h2>
        <p style={{ margin: 0, fontSize: "0.82rem", opacity: 0.78 }}>Grounded answers · citations appear in the intelligence panel →</p>
      </div>
      <label style={{ fontSize: "0.82rem", display: "grid", gap: "0.35rem" }}>
        Document ID
        <input
          data-testid="document-id-input"
          value={documentId}
          onChange={(e) => onDocumentIdChange(e.target.value)}
          placeholder="Paste UUID or pick from Documents"
          className={ws.inputGlow}
          style={{
            padding: "0.65rem",
            borderRadius: 12,
            border: "1px solid rgba(51,65,85,0.85)",
            background: "rgba(15,23,42,0.85)",
            color: "#e5e7eb",
            fontFamily: "ui-monospace, monospace",
            fontSize: "0.82rem",
          }}
        />
      </label>
      <label style={{ fontSize: "0.82rem", display: "grid", gap: "0.35rem" }}>
        Question
        <textarea
          data-testid="question-input"
          value={question}
          onChange={(e) => onQuestionChange(e.target.value)}
          placeholder="Ask anything grounded in the selected document context…"
          rows={5}
          className={ws.inputGlow}
          style={{
            padding: "0.85rem",
            borderRadius: 14,
            border: "1px solid rgba(51,65,85,0.85)",
            background: "rgba(15,23,42,0.85)",
            color: "#e5e7eb",
            resize: "vertical",
            minHeight: 120,
            lineHeight: 1.45,
          }}
        />
      </label>
      <div>
        <p style={{ margin: "0 0 0.45rem", fontSize: "0.78rem", opacity: 0.75 }}>Try an example</p>
        <div style={{ display: "flex", flexWrap: "wrap", gap: "0.4rem" }}>
          {SUGGESTIONS.map((s) => (
            <button
              key={s}
              type="button"
              data-testid={`query-suggestion-${s.slice(0, 12).replace(/\s+/g, "-")}`}
              onClick={() => onQuestionChange(s)}
              style={{
                fontSize: "0.72rem",
                padding: "0.35rem 0.55rem",
                borderRadius: 999,
                border: "1px solid rgba(59,130,246,0.35)",
                background: "rgba(59,130,246,0.1)",
                color: "#bfdbfe",
                cursor: "pointer",
              }}
            >
              {s.length > 48 ? `${s.slice(0, 46)}…` : s}
            </button>
          ))}
        </div>
      </div>
      <div style={{ display: "flex", flexWrap: "wrap", gap: "1.25rem", alignItems: "center" }}>
        <div data-testid="answer-mode-select" style={{ display: "grid", gap: "0.35rem" }}>
          <span id="mode-toggle-label" style={{ fontSize: "0.78rem", opacity: 0.85 }}>
            Answer mode · Flex ↔ Strict
          </span>
          <button
            type="button"
            role="switch"
            aria-checked={answerMode === "strict"}
            aria-labelledby="mode-toggle-label"
            data-testid="answer-mode-toggle"
            className={`${ws.toggleTrack} ${answerMode === "strict" ? ws.toggleTrackOn : ""}`}
            onClick={() => onAnswerModeChange(answerMode === "strict" ? "flexible" : "strict")}
          >
            <span className={`${ws.toggleKnob} ${answerMode === "strict" ? ws.toggleKnobOn : ""}`} />
          </button>
          <span style={{ fontSize: "0.72rem", opacity: 0.7 }}>{answerMode === "strict" ? "Strict (verbatim)" : "Flexible synthesis"}</span>
        </div>
        <div data-testid="answer-length-select" style={{ flex: "1 1 180px", minWidth: 160 }}>
          <label htmlFor="answer-length-slider" style={{ fontSize: "0.78rem", opacity: 0.85 }}>
            Response length · {answerLength}
          </label>
          <input
            id="answer-length-slider"
            data-testid="answer-length-slider"
            type="range"
            min={0}
            max={100}
            step={50}
            value={lenSlider}
            onChange={(e) => onAnswerLengthChange(lengthFromSlider(Number(e.target.value)))}
            style={{ width: "100%", marginTop: "0.35rem" }}
          />
        </div>
        <div style={{ flex: "1 1 160px", minWidth: 140 }}>
          <label htmlFor="topk-slider" title="How many chunks to retrieve before answering (breadth vs focus)" style={{ fontSize: "0.78rem", opacity: 0.85 }}>
            Top-K chunks · {topK}
          </label>
          <input
            id="topk-slider"
            data-testid="topk-input"
            type="range"
            min={1}
            max={20}
            value={topK}
            onChange={(e) => onTopKChange(Math.max(1, Math.min(20, Number(e.target.value) || 1)))}
            style={{ width: "100%", marginTop: "0.35rem" }}
          />
        </div>
      </div>
      <button
        data-testid="query-button"
        type="submit"
        disabled={!canQuery}
        className={`${ws.askBtn} ${isQuerying ? ws.askBtnLoading : ""}`}
        style={{ justifySelf: "start" }}
      >
        {isQuerying ? "AI processing…" : "Ask AI"}
      </button>
      {statusLine ? (
        <p data-testid="query-status-line" style={{ margin: 0, fontSize: "0.78rem", opacity: 0.82, lineHeight: 1.45 }}>
          {statusLine}
        </p>
      ) : null}
    </form>
  );
}
