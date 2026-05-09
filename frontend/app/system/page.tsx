"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";

export default function SystemMonitoringRoutePage() {
  const router = useRouter();
  useEffect(() => {
    router.replace("/?panel=admin");
  }, [router]);
  return (
    <main
      style={{
        minHeight: "100vh",
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        background: "#020617",
        color: "#cbd5e1",
        fontFamily: "Inter, ui-sans-serif, system-ui, sans-serif",
      }}
      data-testid="system-route-redirect"
    >
      <p style={{ margin: 0, opacity: 0.85 }}>Opening system monitoring…</p>
    </main>
  );
}
