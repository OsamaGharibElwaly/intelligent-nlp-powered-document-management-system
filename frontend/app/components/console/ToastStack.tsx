"use client";

import ws from "./workspace.module.css";

export type ToastItem = { id: string; type: "success" | "error" | "info"; message: string };

type Props = { toasts: ToastItem[] };

export function ToastStack({ toasts }: Props) {
  return (
    <div className={ws.toastHost} aria-live="polite">
      {toasts.map((t) => (
        <div
          key={t.id}
          data-testid={`toast-${t.type}-${t.id}`}
          className={t.type === "success" ? ws.toastSuccess : t.type === "error" ? ws.toastError : ws.toastInfo}
          role="status"
        >
          {t.message}
        </div>
      ))}
    </div>
  );
}
