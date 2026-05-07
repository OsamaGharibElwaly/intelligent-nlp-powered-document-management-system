"use client";

import { FormEvent, useEffect, useMemo, useRef, useState } from "react";
import * as THREE from "three";

const backendUrl = process.env.NEXT_PUBLIC_BACKEND_URL ?? "";

type RetrievalItem = {
  chunk_id: string;
  text: string;
  score: number;
};

type ManagedDocument = {
  document_id: string;
  owner_id: string;
  collection_id: string;
  filename: string;
  file_size?: number;
  storage_path: string;
  active_version?: number;
  versions?: Array<{
    version: number;
    filename: string;
    file_size: number;
    storage_path: string;
    index_document_id: string;
    index_status: string;
  }>;
};

export default function Home() {
  const mountRef = useRef<HTMLDivElement | null>(null);
  const [activePanel, setActivePanel] = useState<"dashboard" | "documents" | "query">("dashboard");
  const [email, setEmail] = useState("user@local.dev");
  const [password, setPassword] = useState("user123");
  const [token, setToken] = useState("");
  const [role, setRole] = useState("");
  const [file, setFile] = useState<File | null>(null);
  const [collectionId, setCollectionId] = useState("default");
  const [documentId, setDocumentId] = useState("");
  const [question, setQuestion] = useState("");
  const [topK, setTopK] = useState(3);
  const [answer, setAnswer] = useState("");
  const [chunks, setChunks] = useState<RetrievalItem[]>([]);
  const [documents, setDocuments] = useState<ManagedDocument[]>([]);
  const [isLoggingIn, setIsLoggingIn] = useState(false);
  const [isRegistering, setIsRegistering] = useState(false);
  const [isLoadingDocs, setIsLoadingDocs] = useState(false);
  const [isUploading, setIsUploading] = useState(false);
  const [isQuerying, setIsQuerying] = useState(false);
  const [docSearch, setDocSearch] = useState("");
  const [collectionFilter, setCollectionFilter] = useState("all");
  const [sortBy, setSortBy] = useState<"filename" | "collection" | "size">("filename");
  const [error, setError] = useState("");

  const canUpload = useMemo(() => Boolean(file) && !isUploading && Boolean(token), [file, isUploading, token]);
  const canQuery = useMemo(
    () => Boolean(documentId.trim()) && Boolean(question.trim()) && !isQuerying && Boolean(token),
    [documentId, question, isQuerying, token],
  );
  const collectionOptions = useMemo(() => {
    const values = new Set<string>();
    for (const doc of documents) {
      values.add(doc.collection_id);
    }
    return ["all", ...Array.from(values).sort((a, b) => a.localeCompare(b))];
  }, [documents]);
  const getEffectiveFileSize = (doc: ManagedDocument) => {
    if (typeof doc.file_size === "number" && Number.isFinite(doc.file_size)) return doc.file_size;
    const activeVersion = doc.active_version ?? 1;
    const fromActive = doc.versions?.find((version) => version.version === activeVersion)?.file_size;
    if (typeof fromActive === "number" && Number.isFinite(fromActive)) return fromActive;
    const fromFirst = doc.versions?.[0]?.file_size;
    if (typeof fromFirst === "number" && Number.isFinite(fromFirst)) return fromFirst;
    return 0;
  };

  const visibleDocuments = useMemo(() => {
    const keyword = docSearch.trim().toLowerCase();
    const bySearch = documents.filter((doc) => {
      if (!keyword) return true;
      return (
        doc.filename.toLowerCase().includes(keyword) ||
        doc.document_id.toLowerCase().includes(keyword) ||
        doc.collection_id.toLowerCase().includes(keyword)
      );
    });
    const byCollection =
      collectionFilter === "all" ? bySearch : bySearch.filter((doc) => doc.collection_id === collectionFilter);
    return [...byCollection].sort((a, b) => {
      if (sortBy === "size") return getEffectiveFileSize(b) - getEffectiveFileSize(a);
      if (sortBy === "collection") return a.collection_id.localeCompare(b.collection_id);
      return a.filename.localeCompare(b.filename);
    });
  }, [documents, docSearch, collectionFilter, sortBy]);

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

  const authHeaders = useMemo<Record<string, string>>(() => {
    const headers: Record<string, string> = {};
    if (token) {
      headers.Authorization = `Bearer ${token}`;
    }
    return headers;
  }, [token]);

  const loadDocuments = async () => {
    if (!token) return;
    setIsLoadingDocs(true);
    try {
      const response = await fetch(`${backendUrl}/documents`, { headers: authHeaders });
      const data = await response.json();
      if (!response.ok) throw new Error(data.detail ?? "Failed to load documents");
      setDocuments(Array.isArray(data) ? data : []);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load documents");
    } finally {
      setIsLoadingDocs(false);
    }
  };

  const formatFileSize = (size: number) => {
    if (size < 1024) return `${size} B`;
    if (size < 1024 * 1024) return `${(size / 1024).toFixed(1)} KB`;
    return `${(size / (1024 * 1024)).toFixed(2)} MB`;
  };

  const handleLogin = async (event: FormEvent) => {
    event.preventDefault();
    if (!backendUrl) {
      setError("NEXT_PUBLIC_BACKEND_URL is not configured.");
      return;
    }
    setIsLoggingIn(true);
    setError("");
    try {
      const response = await fetch(`${backendUrl}/auth/login`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email, password }),
      });
      const data = await response.json();
      if (!response.ok) throw new Error(data.detail ?? "Login failed");
      setToken(data.access_token ?? "");
      setRole(data.role ?? "");
      setActivePanel("documents");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Login failed");
    } finally {
      setIsLoggingIn(false);
    }
  };

  const handleRegister = async () => {
    if (!backendUrl) {
      setError("NEXT_PUBLIC_BACKEND_URL is not configured.");
      return;
    }
    setIsRegistering(true);
    setError("");
    try {
      const response = await fetch(`${backendUrl}/auth/register`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email, password }),
      });
      const data = await response.json();
      if (!response.ok) throw new Error(data.detail ?? "Register failed");
      setToken(data.access_token ?? "");
      setRole(data.role ?? "");
      setActivePanel("documents");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Register failed");
    } finally {
      setIsRegistering(false);
    }
  };

  const handleUpload = async (event: FormEvent) => {
    event.preventDefault();
    if (!file || !token) return;
    if (!backendUrl) {
      setError("NEXT_PUBLIC_BACKEND_URL is not configured.");
      return;
    }

    setIsUploading(true);
    setError("");
    try {
      const formData = new FormData();
      formData.append("file", file);
      formData.append("collection_id", collectionId.trim() || "default");
      const response = await fetch(`${backendUrl}/upload`, {
        method: "POST",
        headers: authHeaders,
        body: formData,
      });
      const data = await response.json();
      if (!response.ok) throw new Error(data.detail ?? "Upload failed");
      setDocumentId(data.document_id);
      await loadDocuments();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Upload failed");
    } finally {
      setIsUploading(false);
    }
  };

  const handleQuery = async (event: FormEvent) => {
    event.preventDefault();
    if (!documentId.trim() || !question.trim() || !token) return;
    if (!backendUrl) {
      setError("NEXT_PUBLIC_BACKEND_URL is not configured.");
      return;
    }

    setIsQuerying(true);
    setError("");
    try {
      const [answerResponse, retrieveResponse] = await Promise.all([
        fetch(`${backendUrl}/query`, {
          method: "POST",
          headers: { "Content-Type": "application/json", ...authHeaders },
          body: JSON.stringify({ question, document_id: documentId.trim(), top_k: topK }),
        }),
        fetch(`${backendUrl}/retrieve`, {
          method: "POST",
          headers: { "Content-Type": "application/json", ...authHeaders },
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
          maxWidth: 1280,
          margin: "0 auto",
          padding: "2rem 1rem 4rem",
          fontFamily: "Inter, Arial, sans-serif",
        }}
      >
        <div style={{ display: "grid", gridTemplateColumns: "270px 1fr", gap: "1rem" }}>
          <aside
            style={{
              background: "rgba(15,23,42,0.72)",
              border: "1px solid rgba(148,163,184,0.25)",
              borderRadius: 16,
              padding: "1rem",
              backdropFilter: "blur(8px)",
              height: "fit-content",
            }}
          >
            <h2 style={{ marginTop: 0, fontSize: "1.15rem" }}>Management Console</h2>
            <p style={{ opacity: 0.8, marginTop: 0 }}>Backend: {backendUrl}</p>
            <form onSubmit={handleLogin} style={{ display: "grid", gap: "0.5rem", marginBottom: "1rem" }}>
              <input data-testid="email-input" value={email} onChange={(e) => setEmail(e.target.value)} placeholder="email" style={{ padding: "0.55rem", borderRadius: 10, border: "1px solid #334155", background: "#0f172a", color: "#e5e7eb" }} />
              <input data-testid="password-input" type="password" value={password} onChange={(e) => setPassword(e.target.value)} placeholder="password" style={{ padding: "0.55rem", borderRadius: 10, border: "1px solid #334155", background: "#0f172a", color: "#e5e7eb" }} />
              <button data-testid="login-button" type="submit" style={{ padding: "0.6rem", borderRadius: 10, border: "1px solid rgba(99,102,241,0.45)", background: "#4f46e5", color: "white", fontWeight: 700 }}>
                {isLoggingIn ? "Signing in..." : token ? `Logged (${role})` : "Sign In"}
              </button>
              <button
                data-testid="register-button"
                type="button"
                onClick={handleRegister}
                disabled={isRegistering || isLoggingIn}
                style={{ padding: "0.6rem", borderRadius: 10, border: "1px solid rgba(34,211,238,0.45)", background: "rgba(6,182,212,0.25)", color: "#cffafe", fontWeight: 700, cursor: "pointer" }}
              >
                {isRegistering ? "Registering..." : "Register"}
              </button>
            </form>

            <nav style={{ display: "grid", gap: "0.45rem" }}>
              {[
                { key: "dashboard", label: "Dashboard" },
                { key: "documents", label: "Document Storage" },
                { key: "query", label: "Query Workspace" },
              ].map((item) => (
                <button
                  key={item.key}
                  data-testid={`nav-${item.key}`}
                  onClick={() => setActivePanel(item.key as "dashboard" | "documents" | "query")}
                  style={{
                    textAlign: "left",
                    padding: "0.6rem 0.7rem",
                    borderRadius: 10,
                    border: "1px solid rgba(148,163,184,0.25)",
                    background: activePanel === item.key ? "rgba(34,211,238,0.2)" : "rgba(15,23,42,0.45)",
                    color: "#e5e7eb",
                    cursor: "pointer",
                  }}
                >
                  {item.label}
                </button>
              ))}
            </nav>
          </aside>

          <div>
            <header style={{ marginBottom: "1rem" }}>
              <h1 style={{ fontSize: "2.1rem", marginBottom: "0.4rem", letterSpacing: "-0.02em" }}>RAG Document Management System</h1>
              <p style={{ marginBottom: 0, opacity: 0.92 }}>
                Upload {"->"} ownership storage {"->"} retrieval {"->"} grounded answer
              </p>
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
              data-testid="collection-id-input"
              value={collectionId}
              onChange={(e) => setCollectionId(e.target.value)}
              placeholder="collection id (folder)"
              style={{ background: "#0f172a", border: "1px solid #334155", padding: "0.75rem", borderRadius: 10, color: "#cbd5e1" }}
            />
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
            {activePanel === "documents" && (
              <section style={{ background: "rgba(15, 23, 42, 0.8)", border: "1px solid rgba(148,163,184,0.25)", borderRadius: 16, padding: "1rem", backdropFilter: "blur(8px)" }}>
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", gap: "0.75rem", flexWrap: "wrap" }}>
                  <h2 style={{ marginTop: 0 }}>Owned Documents</h2>
                  <button data-testid="refresh-documents-button" onClick={loadDocuments} style={{ padding: "0.45rem 0.7rem", borderRadius: 10, border: "1px solid rgba(148,163,184,0.25)", background: "#0f172a", color: "#e5e7eb", cursor: "pointer" }}>
                    {isLoadingDocs ? "Refreshing..." : "Refresh"}
                  </button>
                </div>
                <div style={{ display: "grid", gridTemplateColumns: "1fr 180px 180px", gap: "0.6rem", marginBottom: "0.85rem" }}>
                  <input
                    data-testid="documents-search-input"
                    value={docSearch}
                    onChange={(e) => setDocSearch(e.target.value)}
                    placeholder="Search by file, id, collection"
                    style={{ background: "#0f172a", border: "1px solid #334155", padding: "0.6rem", borderRadius: 10, color: "#e5e7eb" }}
                  />
                  <select
                    data-testid="documents-collection-filter"
                    value={collectionFilter}
                    onChange={(e) => setCollectionFilter(e.target.value)}
                    style={{ background: "#0f172a", border: "1px solid #334155", padding: "0.6rem", borderRadius: 10, color: "#e5e7eb" }}
                  >
                    {collectionOptions.map((option) => (
                      <option key={option} value={option}>
                        {option === "all" ? "All Collections" : option}
                      </option>
                    ))}
                  </select>
                  <select
                    data-testid="documents-sort-select"
                    value={sortBy}
                    onChange={(e) => setSortBy(e.target.value as "filename" | "collection" | "size")}
                    style={{ background: "#0f172a", border: "1px solid #334155", padding: "0.6rem", borderRadius: 10, color: "#e5e7eb" }}
                  >
                    <option value="filename">Sort: Filename</option>
                    <option value="collection">Sort: Collection</option>
                    <option value="size">Sort: File Size</option>
                  </select>
                </div>
                {documents.length === 0 ? (
                  <p data-testid="documents-empty">No documents indexed yet.</p>
                ) : (
                  <div data-testid="documents-list" style={{ overflowX: "auto", border: "1px solid rgba(148,163,184,0.25)", borderRadius: 12 }}>
                    <table style={{ width: "100%", borderCollapse: "collapse", minWidth: 860 }}>
                      <thead>
                        <tr style={{ background: "rgba(30,41,59,0.75)" }}>
                          <th style={{ textAlign: "left", padding: "0.6rem", borderBottom: "1px solid rgba(148,163,184,0.25)" }}>File</th>
                          <th style={{ textAlign: "left", padding: "0.6rem", borderBottom: "1px solid rgba(148,163,184,0.25)" }}>Collection</th>
                          <th style={{ textAlign: "left", padding: "0.6rem", borderBottom: "1px solid rgba(148,163,184,0.25)" }}>Document ID</th>
                          <th style={{ textAlign: "right", padding: "0.6rem", borderBottom: "1px solid rgba(148,163,184,0.25)" }}>Size</th>
                          <th style={{ textAlign: "center", padding: "0.6rem", borderBottom: "1px solid rgba(148,163,184,0.25)" }}>Actions</th>
                        </tr>
                      </thead>
                      <tbody>
                        {visibleDocuments.map((doc) => (
                          <tr key={doc.document_id} style={{ background: documentId === doc.document_id ? "rgba(79,70,229,0.18)" : "transparent" }}>
                            <td style={{ padding: "0.6rem", borderBottom: "1px solid rgba(51,65,85,0.55)" }}>📄 {doc.filename}</td>
                            <td style={{ padding: "0.6rem", borderBottom: "1px solid rgba(51,65,85,0.55)" }}>🗂️ {doc.collection_id}</td>
                            <td style={{ padding: "0.6rem", borderBottom: "1px solid rgba(51,65,85,0.55)", fontFamily: "monospace", fontSize: "0.84rem" }}>{doc.document_id}</td>
                            <td style={{ padding: "0.6rem", borderBottom: "1px solid rgba(51,65,85,0.55)", textAlign: "right" }}>{formatFileSize(getEffectiveFileSize(doc))}</td>
                            <td style={{ padding: "0.6rem", borderBottom: "1px solid rgba(51,65,85,0.55)", textAlign: "center", display: "flex", gap: "0.4rem", justifyContent: "center" }}>
                              <button
                                data-testid={`select-document-${doc.document_id}`}
                                onClick={() => {
                                  setDocumentId(doc.document_id);
                                  setActivePanel("query");
                                }}
                                style={{ padding: "0.35rem 0.5rem", borderRadius: 8, border: "1px solid rgba(34,211,238,0.45)", background: "rgba(6,182,212,0.2)", color: "#e0f2fe", cursor: "pointer" }}
                              >
                                🔎 Use
                              </button>
                              <button
                                data-testid={`copy-document-id-${doc.document_id}`}
                                onClick={async () => {
                                  try {
                                    await navigator.clipboard.writeText(doc.document_id);
                                  } catch {
                                    setError("Clipboard copy failed.");
                                  }
                                }}
                                style={{ padding: "0.35rem 0.5rem", borderRadius: 8, border: "1px solid rgba(148,163,184,0.35)", background: "rgba(15,23,42,0.5)", color: "#e5e7eb", cursor: "pointer" }}
                              >
                                📋 Copy ID
                              </button>
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                )}
              </section>
            )}

            {activePanel !== "documents" && (
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
            )}
          </div>
        </div>
      </section>
    </main>
  );
}
