"use client";

import { FormEvent, useEffect, useMemo, useRef, useState } from "react";
import * as THREE from "three";

const backendUrl = process.env.NEXT_PUBLIC_BACKEND_URL ?? "http://localhost:8000";

type RetrievalItem = {
  chunk_id: string;
  text: string;
  score: number;
};

export default function Home() {
  const mountRef = useRef<HTMLDivElement | null>(null);
  const [file, setFile] = useState<File | null>(null);
  const [documentId, setDocumentId] = useState("");
  const [question, setQuestion] = useState("");
  const [topK, setTopK] = useState(3);
  const [answer, setAnswer] = useState("");
  const [chunks, setChunks] = useState<RetrievalItem[]>([]);
  const [isUploading, setIsUploading] = useState(false);
  const [isQuerying, setIsQuerying] = useState(false);
  const [error, setError] = useState("");

  const canUpload = useMemo(() => Boolean(file) && !isUploading, [file, isUploading]);
  const canQuery = useMemo(
    () => Boolean(documentId.trim()) && Boolean(question.trim()) && !isQuerying,
    [documentId, question, isQuerying],
  );

  useEffect(() => {
    if (!mountRef.current) {
      return;
    }

    const scene = new THREE.Scene();
    scene.fog = new THREE.Fog(0x020617, 10, 28);
    const camera = new THREE.PerspectiveCamera(70, window.innerWidth / window.innerHeight, 0.1, 1000);
    camera.position.set(0, 0.3, 9);

    const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true });
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
    renderer.setSize(window.innerWidth, window.innerHeight);
    mountRef.current.appendChild(renderer.domElement);

    const mainGeometry = new THREE.IcosahedronGeometry(2.1, 2);
    const mainMaterial = new THREE.MeshStandardMaterial({
      color: 0x4f46e5,
      wireframe: true,
      transparent: true,
      opacity: 0.35,
    });
    const mainMesh = new THREE.Mesh(mainGeometry, mainMaterial);
    scene.add(mainMesh);

    const ringGeometry = new THREE.TorusKnotGeometry(1.2, 0.25, 120, 24);
    const ringMaterial = new THREE.MeshStandardMaterial({
      color: 0x22d3ee,
      transparent: true,
      opacity: 0.28,
      metalness: 0.5,
      roughness: 0.3,
    });
    const ringMesh = new THREE.Mesh(ringGeometry, ringMaterial);
    ringMesh.position.set(3.7, -2.1, -0.8);
    scene.add(ringMesh);

    const starGeometry = new THREE.BufferGeometry();
    const starCount = 900;
    const starPositions = new Float32Array(starCount * 3);
    for (let i = 0; i < starCount * 3; i += 3) {
      starPositions[i] = (Math.random() - 0.5) * 38;
      starPositions[i + 1] = (Math.random() - 0.5) * 24;
      starPositions[i + 2] = -Math.random() * 30;
    }
    starGeometry.setAttribute("position", new THREE.BufferAttribute(starPositions, 3));
    const starMaterial = new THREE.PointsMaterial({ color: 0x93c5fd, size: 0.04, transparent: true, opacity: 0.75 });
    const stars = new THREE.Points(starGeometry, starMaterial);
    scene.add(stars);

    const pointLight = new THREE.PointLight(0xa5b4fc, 2.2);
    pointLight.position.set(4, 6, 8);
    const accentLight = new THREE.PointLight(0x22d3ee, 1.8);
    accentLight.position.set(-5, -2, 5);
    scene.add(pointLight);
    scene.add(accentLight);
    scene.add(new THREE.AmbientLight(0xffffff, 0.2));

    const pointer = { x: 0, y: 0 };

    let frameId = 0;
    const animate = () => {
      mainMesh.rotation.x += 0.0022;
      mainMesh.rotation.y += 0.0035;
      ringMesh.rotation.x += 0.0045;
      ringMesh.rotation.z += 0.0034;
      stars.rotation.y += 0.00035;

      camera.position.x += (pointer.x * 0.55 - camera.position.x) * 0.05;
      camera.position.y += (pointer.y * 0.45 + 0.3 - camera.position.y) * 0.05;
      camera.lookAt(0, 0, 0);

      renderer.render(scene, camera);
      frameId = requestAnimationFrame(animate);
    };
    animate();

    const onPointerMove = (event: MouseEvent) => {
      pointer.x = (event.clientX / window.innerWidth) * 2 - 1;
      pointer.y = -(event.clientY / window.innerHeight) * 2 + 1;
    };

    const onResize = () => {
      camera.aspect = window.innerWidth / window.innerHeight;
      camera.updateProjectionMatrix();
      renderer.setSize(window.innerWidth, window.innerHeight);
    };
    window.addEventListener("resize", onResize);
    window.addEventListener("mousemove", onPointerMove);

    return () => {
      cancelAnimationFrame(frameId);
      window.removeEventListener("resize", onResize);
      window.removeEventListener("mousemove", onPointerMove);
      mainGeometry.dispose();
      mainMaterial.dispose();
      ringGeometry.dispose();
      ringMaterial.dispose();
      starGeometry.dispose();
      starMaterial.dispose();
      renderer.dispose();
      if (mountRef.current?.contains(renderer.domElement)) {
        mountRef.current.removeChild(renderer.domElement);
      }
    };
  }, []);

  const handleUpload = async (event: FormEvent) => {
    event.preventDefault();
    if (!file) return;

    setIsUploading(true);
    setError("");
    try {
      const formData = new FormData();
      formData.append("file", file);
      const response = await fetch(`${backendUrl}/upload`, {
        method: "POST",
        body: formData,
      });
      const data = await response.json();
      if (!response.ok) throw new Error(data.detail ?? "Upload failed");
      setDocumentId(data.document_id);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Upload failed");
    } finally {
      setIsUploading(false);
    }
  };

  const handleQuery = async (event: FormEvent) => {
    event.preventDefault();
    if (!documentId.trim() || !question.trim()) return;

    setIsQuerying(true);
    setError("");
    try {
      const [answerResponse, retrieveResponse] = await Promise.all([
        fetch(`${backendUrl}/query`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ question, document_id: documentId.trim(), top_k: topK }),
        }),
        fetch(`${backendUrl}/retrieve`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ query: question, document_id: documentId.trim(), top_k: topK }),
        }),
      ]);
      const answerData = await answerResponse.json();
      const retrieveData = await retrieveResponse.json();
      if (!answerResponse.ok) throw new Error(answerData.detail ?? "Query failed");
      if (!retrieveResponse.ok) throw new Error(retrieveData.detail ?? "Retrieve failed");

      setAnswer(answerData.answer ?? "");
      setChunks(Array.isArray(retrieveData) ? retrieveData : []);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Query failed");
    } finally {
      setIsQuerying(false);
    }
  };

  return (
    <main style={{ minHeight: "100vh", position: "relative", overflow: "hidden", color: "#e5e7eb" }}>
      <div
        ref={mountRef}
        style={{ position: "fixed", inset: 0, zIndex: 0, background: "radial-gradient(circle at 20% 20%, #111827, #020617 60%)" }}
      />
      <div
        style={{
          position: "fixed",
          inset: 0,
          zIndex: 0,
          background:
            "linear-gradient(140deg, rgba(79,70,229,0.18) 0%, rgba(2,6,23,0.1) 42%, rgba(34,211,238,0.15) 100%)",
        }}
      />

      <section
        style={{
          position: "relative",
          zIndex: 1,
          maxWidth: 1120,
          margin: "0 auto",
          padding: "2rem 1rem 4rem",
          fontFamily: "Inter, Arial, sans-serif",
        }}
      >
        <header style={{ marginBottom: "1.6rem" }}>
          <h1 style={{ fontSize: "2.3rem", marginBottom: "0.55rem", letterSpacing: "-0.02em" }}>RAG Document Assistant</h1>
          <p style={{ marginBottom: 0, opacity: 0.92 }}>Upload {"->"} retrieve {"->"} grounded answer. Backend: {backendUrl}</p>
        </header>

        <div
          style={{
            display: "grid",
            gridTemplateColumns: "minmax(320px, 1fr) minmax(320px, 1fr)",
            gap: "1rem",
            marginBottom: "1rem",
          }}
        >
          <form
            onSubmit={handleUpload}
            style={{
              display: "grid",
              gap: "0.75rem",
              background: "rgba(15,23,42,0.7)",
              border: "1px solid rgba(148,163,184,0.25)",
              borderRadius: 16,
              padding: "1rem",
              backdropFilter: "blur(8px)",
            }}
          >
            <h2 style={{ margin: 0, fontSize: "1.05rem" }}>1) Upload Document</h2>
            <input
              data-testid="file-input"
              type="file"
              accept=".pdf,.docx,.txt"
              onChange={(e) => setFile(e.target.files?.[0] ?? null)}
              style={{
                background: "#0f172a",
                border: "1px solid #334155",
                padding: "0.75rem",
                borderRadius: 10,
                color: "#cbd5e1",
              }}
            />
            <button
              data-testid="upload-button"
              type="submit"
              disabled={!canUpload}
              style={{
                padding: "0.75rem 1rem",
                borderRadius: 10,
                border: "1px solid rgba(99,102,241,0.45)",
                background: "linear-gradient(130deg, #4f46e5, #6366f1)",
                color: "white",
                cursor: "pointer",
                fontWeight: 700,
              }}
            >
              {isUploading ? "Uploading..." : "Upload Document"}
            </button>
          </form>

          <form
            onSubmit={handleQuery}
            style={{
              display: "grid",
              gap: "0.75rem",
              background: "rgba(15,23,42,0.7)",
              border: "1px solid rgba(148,163,184,0.25)",
              borderRadius: 16,
              padding: "1rem",
              backdropFilter: "blur(8px)",
            }}
          >
            <h2 style={{ margin: 0, fontSize: "1.05rem" }}>2) Query Document</h2>
            <label style={{ display: "grid", gap: "0.35rem" }}>
              <span>Document ID</span>
              <input
                data-testid="document-id-input"
                value={documentId}
                onChange={(e) => setDocumentId(e.target.value)}
                placeholder="Auto-filled after upload"
                style={{
                  background: "#0f172a",
                  border: "1px solid #334155",
                  padding: "0.75rem",
                  borderRadius: 10,
                  color: "#e5e7eb",
                }}
              />
            </label>
            <textarea
              data-testid="question-input"
              value={question}
              onChange={(e) => setQuestion(e.target.value)}
              placeholder="Ask a grounded question"
              rows={3}
              style={{
                background: "#0f172a",
                border: "1px solid #334155",
                padding: "0.75rem",
                borderRadius: 10,
                color: "#e5e7eb",
                resize: "vertical",
              }}
            />
            <div style={{ display: "flex", alignItems: "center", gap: "0.7rem" }}>
              <label htmlFor="topk-field">Top-K</label>
              <input
                id="topk-field"
                data-testid="topk-input"
                type="number"
                min={1}
                max={20}
                value={topK}
                onChange={(e) => setTopK(Math.max(1, Math.min(20, Number(e.target.value) || 1)))}
                style={{ width: 90, background: "#0f172a", border: "1px solid #334155", padding: "0.55rem", borderRadius: 10, color: "#e5e7eb" }}
              />
              <button
                data-testid="query-button"
                type="submit"
                disabled={!canQuery}
                style={{
                  marginLeft: "auto",
                  padding: "0.75rem 1rem",
                  borderRadius: 10,
                  border: "1px solid rgba(34,211,238,0.45)",
                  background: "linear-gradient(130deg, #06b6d4, #22d3ee)",
                  color: "#082f49",
                  cursor: "pointer",
                  fontWeight: 800,
                }}
              >
                {isQuerying ? "Querying..." : "Get Answer"}
              </button>
            </div>
          </form>
        </div>

        {error && (
          <div
            style={{
              marginBottom: "1rem",
              color: "#fecaca",
              background: "rgba(127,29,29,0.35)",
              border: "1px solid rgba(248,113,113,0.45)",
              padding: "0.75rem",
              borderRadius: 12,
            }}
            data-testid="error-message"
          >
            {error}
          </div>
        )}

        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "1rem" }}>
          <div
            style={{
              background: "rgba(15, 23, 42, 0.8)",
              border: "1px solid rgba(148,163,184,0.25)",
              borderRadius: 16,
              padding: "1rem",
              backdropFilter: "blur(8px)",
            }}
          >
          <h2 style={{ marginTop: 0 }}>Answer</h2>
          <p data-testid="answer-output" style={{ marginBottom: 0 }}>
            {answer || "No answer yet."}
          </p>
          </div>

          <div
            style={{
              background: "rgba(15, 23, 42, 0.8)",
              border: "1px solid rgba(148,163,184,0.25)",
              borderRadius: 16,
              padding: "1rem",
              backdropFilter: "blur(8px)",
            }}
          >
            <h2 style={{ marginTop: 0 }}>Retrieved Chunks</h2>
            {chunks.length === 0 ? (
              <p data-testid="chunks-empty">No retrieved chunks yet.</p>
            ) : (
              <ul data-testid="chunks-list" style={{ margin: 0, paddingLeft: "1.25rem" }}>
                {chunks.map((chunk) => (
                  <li key={chunk.chunk_id} style={{ marginBottom: "0.65rem" }}>
                    <strong>{chunk.chunk_id}</strong> ({chunk.score.toFixed(4)}): {chunk.text}
                  </li>
                ))}
              </ul>
            )}
          </div>
        </div>
      </section>
    </main>
  );
}
