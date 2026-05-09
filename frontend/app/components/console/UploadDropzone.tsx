"use client";

import { FormEvent, useCallback, useState } from "react";

import ws from "./workspace.module.css";

type Props = {
  collectionId: string;
  onCollectionChange: (v: string) => void;
  file: File | null;
  onFileChange: (f: File | null) => void;
  onSubmit: (e: FormEvent) => void;
  canUpload: boolean;
  isUploading: boolean;
  uploadProgress: number;
};

export function UploadDropzone({
  collectionId,
  onCollectionChange,
  file,
  onFileChange,
  onSubmit,
  canUpload,
  isUploading,
  uploadProgress,
}: Props) {
  const [dragging, setDragging] = useState(false);

  const onDrop = useCallback(
    (e: React.DragEvent) => {
      e.preventDefault();
      setDragging(false);
      const f = e.dataTransfer.files?.[0];
      if (f) onFileChange(f);
    },
    [onFileChange],
  );

  return (
    <form onSubmit={onSubmit} className={`${ws.glassElevated}`} style={{ padding: "1.15rem", display: "grid", gap: "1rem" }}>
      <div>
        <h2 style={{ margin: "0 0 0.35rem", fontSize: "1.05rem" }}>Upload document</h2>
        <p style={{ margin: 0, fontSize: "0.82rem", opacity: 0.78 }}>Drag & drop or browse · indexed for RAG automatically</p>
      </div>
      <label style={{ fontSize: "0.82rem", display: "grid", gap: "0.35rem" }}>
        Collection
        <input
          data-testid="collection-id-input"
          value={collectionId}
          onChange={(e) => onCollectionChange(e.target.value)}
          className={ws.inputGlow}
          style={{
            padding: "0.65rem",
            borderRadius: 12,
            border: "1px solid rgba(51,65,85,0.85)",
            background: "rgba(15,23,42,0.85)",
            color: "#e5e7eb",
          }}
        />
      </label>
      <div
        role="button"
        tabIndex={0}
        data-testid="upload-dropzone"
        className={`${ws.dropZone} ${dragging ? ws.dropZoneDragging : ""}`}
        onDragEnter={(e) => {
          e.preventDefault();
          setDragging(true);
        }}
        onDragOver={(e) => {
          e.preventDefault();
          setDragging(true);
        }}
        onDragLeave={() => setDragging(false)}
        onDrop={onDrop}
        onKeyDown={(e) => {
          if (e.key === "Enter" || e.key === " ") {
            e.preventDefault();
            document.getElementById("file-input-hidden")?.click();
          }
        }}
        onClick={() => document.getElementById("file-input-hidden")?.click()}
      >
        <input
          id="file-input-hidden"
          data-testid="file-input"
          type="file"
          accept=".pdf,.docx,.txt"
          style={{ display: "none" }}
          onChange={(e) => onFileChange(e.target.files?.[0] ?? null)}
        />
        <p style={{ margin: "0 0 0.35rem", fontSize: "1rem" }}>Drop file here</p>
        <p style={{ margin: 0, fontSize: "0.8rem", opacity: 0.75 }}>PDF, DOCX, TXT · max size enforced by server</p>
      </div>
      {file ? (
        <div
          data-testid="upload-file-preview"
          style={{
            padding: "0.65rem 0.85rem",
            borderRadius: 12,
            border: "1px solid rgba(74,222,128,0.35)",
            background: "rgba(22,101,52,0.18)",
            fontSize: "0.85rem",
          }}
        >
          Selected: <strong>{file.name}</strong> · {(file.size / 1024).toFixed(1)} KB
        </div>
      ) : (
        <p style={{ margin: 0, fontSize: "0.8rem", opacity: 0.65 }} data-testid="upload-empty-hint">
          No file selected yet.
        </p>
      )}
      {isUploading ? (
        <div style={{ height: 8, borderRadius: 999, background: "rgba(51,65,85,0.85)", overflow: "hidden" }} aria-busy="true">
          <div
            style={{
              height: "100%",
              width: `${uploadProgress}%`,
              borderRadius: 999,
              background: "linear-gradient(90deg,#4f46e5,#22d3ee)",
              transition: "width 160ms ease-out",
            }}
          />
        </div>
      ) : null}
      <button
        data-testid="upload-button"
        type="submit"
        disabled={!canUpload}
        className={ws.askBtn}
        style={{ justifySelf: "start", opacity: canUpload ? 1 : 0.45 }}
      >
        {isUploading ? "Uploading…" : "Upload & index"}
      </button>
    </form>
  );
}
