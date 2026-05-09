"use client";

import { FormEvent, Suspense, useCallback, useEffect, useMemo, useRef, useState } from "react";
import * as THREE from "three";
import Link from "next/link";
import { usePathname, useRouter, useSearchParams } from "next/navigation";

import { clearStoredAuth, readStoredAuth } from "./lib/authStorage";

import { AdminBootstrapPanel } from "./components/admin/AdminBootstrapPanel";
import { AdminCommandCenter } from "./components/admin/AdminCommandCenter";
import { DashboardOverview } from "./components/console/DashboardOverview";
import { IntelligencePanel, type AnswerFaultInfo, type QueryUiPhase } from "./components/console/IntelligencePanel";
import { QueryWorkspaceForm } from "./components/console/QueryWorkspaceForm";
import type { ToastItem } from "./components/console/ToastStack";
import { ToastStack } from "./components/console/ToastStack";
import { UploadDropzone } from "./components/console/UploadDropzone";
import ws from "./components/console/workspace.module.css";
import { WorkspaceSidebar, type WorkspaceTab } from "./components/console/WorkspaceSidebar";
import { CollaborationThreadPanel } from "./components/console/CollaborationThreadPanel";
import { TeamCollaborationPanel } from "./components/console/TeamCollaborationPanel";
import { DocumentCard } from "./components/storage/DocumentCard";
import { DocumentFilterPills } from "./components/storage/DocumentFilterPills";
import { DocumentGridSkeleton } from "./components/storage/DocumentGridSkeleton";
import storageUx from "./components/storage/documentStorage.module.css";
import { passesSelectedFilters } from "./components/storage/storageFilters";
import type { StorageFilterId } from "./components/storage/types";
import { fetchWithRetry } from "./lib/queryResilience";
import { documentMatchesWorkspaceScope, readWorkspaceScope, type WorkspaceScopeValue } from "./lib/workspaceScope";

const backendUrl = process.env.NEXT_PUBLIC_BACKEND_URL ?? "";

const showAdminBootstrapUi =
  process.env.NODE_ENV === "development" || process.env.NEXT_PUBLIC_ENABLE_ADMIN_BOOTSTRAP_UI === "true";

type SourceCitation = { chunk_id: string; document_id: string };

type ParagraphCitationBlock = { paragraph_index: number; citations: SourceCitation[] };

type AnswerConfidence = {
  score: number;
  formula_version: string;
  supporting_unique_chunks: number;
  support_component: number;
  relevance_component: number;
  agreement_component: number;
  relevance_mean_raw: number;
  max_retrieval_score_raw: number;
};

type EvidenceSpan = {
  paragraph_index: number;
  chunk_id: string;
  document_id: string;
  span_start: number;
  span_end: number;
  span_text: string;
};

type FeedbackSnapshotContext = {
  question: string;
  document_id: string;
  answer: string;
  confidence_score: number | null;
  retrieved_chunks: { chunk_id: string; relevance_score: number }[];
};

type RetrievalItem = {
  chunk_id: string;
  document_id: string;
  chunk_text: string;
  relevance_score: number;
  metadata?: Record<string, unknown>;
};

type TodoItem = {
  todo_id: string;
  title: string;
  description?: string | null;
  status: "pending" | "done";
  due_date?: string | null;
  completed_at?: string | null;
};

type ActivityEntry = {
  activity_id: string;
  document_id: string;
  activity_type: string;
  timestamp: string;
  user_id: string;
  details: Record<string, unknown>;
};

type ManagedDocument = {
  document_id: string;
  owner_id: string;
  workspace_id?: string | null;
  collection_id: string;
  filename: string;
  file_size?: number;
  storage_path?: string;
  active_version?: number;
  is_deleted?: boolean;
  metadata_schema_version?: number;
  tags?: string[];
  metadata?: Record<string, string>;
  versions?: Array<{
    version: number;
    filename: string;
    file_size: number;
    storage_path: string;
    index_document_id: string;
    index_status: string;
  }>;
  read_status?: "unread" | "reading" | "completed";
  completion_date?: string | null;
  last_read_at?: string | null;
  reading_progress?: number;
  priority?: "low" | "medium" | "high";
  due_date?: string | null;
  pinned?: boolean;
  archived?: boolean;
  ai_usage_count?: number;
  todos?: TodoItem[];
  storage_schema_version?: number;
};

function WorkspaceLoadingFallback() {
  return (
    <main
      style={{
        minHeight: "100vh",
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        background: "#020617",
        color: "#e5e7eb",
        fontFamily: "Inter, ui-sans-serif, system-ui, sans-serif",
      }}
      data-testid="workspace-loading-fallback"
    >
      <p style={{ margin: 0, opacity: 0.85 }}>Loading workspace…</p>
    </main>
  );
}

function RagWorkspace() {
  const mountRef = useRef<HTMLDivElement | null>(null);
  const router = useRouter();
  const pathname = usePathname();
  const searchParams = useSearchParams();
  const [activePanel, setActivePanel] = useState<WorkspaceTab>("dashboard");
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);
  const [toasts, setToasts] = useState<ToastItem[]>([]);
  const [uploadPct, setUploadPct] = useState(0);
  const [lastUploadId, setLastUploadId] = useState<string | null>(null);
  const [backendHealthy, setBackendHealthy] = useState<boolean | null>(null);
  const [feedbackSent, setFeedbackSent] = useState(false);
  const [feedbackChoice, setFeedbackChoice] = useState<"positive" | "negative" | null>(null);
  const [feedbackNegativeComment, setFeedbackNegativeComment] = useState("");
  const [queryUiPhase, setQueryUiPhase] = useState<QueryUiPhase>("idle");
  const [retrieveIntelFault, setRetrieveIntelFault] = useState<string | null>(null);
  const [answerFaultInfo, setAnswerFaultInfo] = useState<AnswerFaultInfo | null>(null);
  const [email, setEmail] = useState("");
  const [token, setToken] = useState("");
  const [role, setRole] = useState("");
  const [file, setFile] = useState<File | null>(null);
  const [collectionId, setCollectionId] = useState("default");
  const [documentId, setDocumentId] = useState("");
  const [question, setQuestion] = useState("");
  const [topK, setTopK] = useState(3);
  const [answer, setAnswer] = useState("");
  const [answerCitations, setAnswerCitations] = useState<ParagraphCitationBlock[]>([]);
  const [answerConfidence, setAnswerConfidence] = useState<AnswerConfidence | null>(null);
  const [evidenceSpans, setEvidenceSpans] = useState<EvidenceSpan[]>([]);
  const [feedbackSnapshot, setFeedbackSnapshot] = useState<FeedbackSnapshotContext | null>(null);
  const [feedbackBusy, setFeedbackBusy] = useState(false);
  const [answerMode, setAnswerMode] = useState<"strict" | "flexible">("flexible");
  const [answerLength, setAnswerLength] = useState<"short" | "medium" | "detailed">("medium");
  const [chunks, setChunks] = useState<RetrievalItem[]>([]);
  const [documents, setDocuments] = useState<ManagedDocument[]>([]);
  const [workspaceScope, setWorkspaceScope] = useState<WorkspaceScopeValue>("");
  const [collaborationWorkspaces, setCollaborationWorkspaces] = useState<
    Array<{ workspace_id: string; name: string; my_role?: string }>
  >([]);
  const [uploadWorkspaceId, setUploadWorkspaceId] = useState("");
  const [persistThread, setPersistThread] = useState(true);
  const [activeThreadId, setActiveThreadId] = useState("");
  const [threadRefreshNonce, setThreadRefreshNonce] = useState(0);
  const [isLoadingDocs, setIsLoadingDocs] = useState(false);
  const [isUploading, setIsUploading] = useState(false);
  const [isQuerying, setIsQuerying] = useState(false);
  const [docSearch, setDocSearch] = useState("");
  const [collectionFilter, setCollectionFilter] = useState("all");
  const [sortBy, setSortBy] = useState<"filename" | "collection" | "size">("filename");
  const [selectedStorageFilters, setSelectedStorageFilters] = useState<Set<StorageFilterId>>(() => new Set());
  const [storageDetailId, setStorageDetailId] = useState<string | null>(null);
  const [storageDetailBusy, setStorageDetailBusy] = useState(false);
  const [activityEntries, setActivityEntries] = useState<ActivityEntry[]>([]);
  const [activityTypeFilter, setActivityTypeFilter] = useState("");
  const [activityLoading, setActivityLoading] = useState(false);
  const [detailProgress, setDetailProgress] = useState(0);
  const [detailReadStatus, setDetailReadStatus] = useState<"unread" | "reading" | "completed">("unread");
  const [detailPriority, setDetailPriority] = useState<"low" | "medium" | "high">("medium");
  const [detailDueDate, setDetailDueDate] = useState("");
  const [detailPinned, setDetailPinned] = useState(false);
  const [detailArchived, setDetailArchived] = useState(false);
  const [newTodoTitle, setNewTodoTitle] = useState("");
  const [error, setError] = useState("");

  const navigatePanel = useCallback(
    (tab: WorkspaceTab) => {
      setActivePanel(tab);
      if (tab === "dashboard") {
        router.replace("/dashboard", { scroll: false });
        return;
      }
      if (tab === "documents") {
        router.replace("/documents", { scroll: false });
        return;
      }
      if (tab === "query") {
        router.replace("/query", { scroll: false });
        return;
      }
      if (tab === "admin") {
        router.replace("/admin", { scroll: false });
        return;
      }
      const qs = `?panel=${encodeURIComponent(tab)}`;
      router.replace(`/${qs}`, { scroll: false });
    },
    [router],
  );

  useEffect(() => {
    if (pathname === "/documents") {
      setActivePanel("documents");
      return;
    }
    if (pathname === "/query") {
      setActivePanel("query");
      return;
    }
    if (pathname === "/dashboard") {
      setActivePanel("dashboard");
      return;
    }

    const raw = searchParams.get("panel");
    const aliases: Record<string, WorkspaceTab> = {
      dashboard: "dashboard",
      admin: "admin",
      system: "admin",
      monitoring: "admin",
      documents: "documents",
      query: "query",
      settings: "settings",
    };
    if (!raw) {
      if (pathname === "/") setActivePanel("dashboard");
      return;
    }
    const tab = aliases[raw];
    if (tab) setActivePanel(tab);
  }, [pathname, searchParams]);

  const panelFromUrl = searchParams.get("panel");
  useEffect(() => {
    const doc = searchParams.get("document")?.trim();
    const tid = searchParams.get("thread")?.trim();
    if (doc) {
      setDocumentId(doc);
      if (panelFromUrl === "documents") setStorageDetailId(doc);
    }
    if (tid) setActiveThreadId(tid);
  }, [searchParams, panelFromUrl]);

  const canEditDocuments = role === "admin" || role === "user";
  const canUpload = useMemo(
    () => Boolean(file) && !isUploading && Boolean(token) && canEditDocuments,
    [file, isUploading, token, canEditDocuments],
  );
  const canQuery = useMemo(
    () => Boolean(documentId.trim()) && Boolean(question.trim()) && !isQuerying && Boolean(token),
    [documentId, question, isQuerying, token],
  );
  const queryStatusLine = useMemo(() => {
    if (queryUiPhase === "thinking") return "Thinking… contacting retrieval and synthesis.";
    if (queryUiPhase === "retrying") return "Retrying with backoff…";
    if (isQuerying) return "Working…";
    return "";
  }, [isQuerying, queryUiPhase]);
  const filteredDocuments = useMemo(
    () => documents.filter((d) => documentMatchesWorkspaceScope(d, workspaceScope)),
    [documents, workspaceScope],
  );

  const workspaceUploadOptions = useMemo(
    () =>
      collaborationWorkspaces.filter((w) => w.my_role === "owner" || w.my_role === "editor"),
    [collaborationWorkspaces],
  );

  const collectionOptions = useMemo(() => {
    const values = new Set<string>();
    for (const doc of filteredDocuments) {
      values.add(doc.collection_id);
    }
    return ["all", ...Array.from(values).sort((a, b) => a.localeCompare(b))];
  }, [filteredDocuments]);
  const getEffectiveFileSize = (doc: ManagedDocument) => {
    if (typeof doc.file_size === "number" && Number.isFinite(doc.file_size)) return doc.file_size;
    const activeVersion = doc.active_version ?? 1;
    const fromActive = doc.versions?.find((version) => version.version === activeVersion)?.file_size;
    if (typeof fromActive === "number" && Number.isFinite(fromActive)) return fromActive;
    const fromFirst = doc.versions?.[0]?.file_size;
    if (typeof fromFirst === "number" && Number.isFinite(fromFirst)) return fromFirst;
    return 0;
  };

  const adminStorageBytes = useMemo(
    () => documents.reduce((sum, doc) => sum + getEffectiveFileSize(doc), 0),
    [documents],
  );

  const visibleDocuments = useMemo(() => {
    const keyword = docSearch.trim().toLowerCase();
    const bySearch = filteredDocuments.filter((doc) => {
      if (!keyword) return true;
      return (
        doc.filename.toLowerCase().includes(keyword) ||
        doc.document_id.toLowerCase().includes(keyword) ||
        doc.collection_id.toLowerCase().includes(keyword)
      );
    });
    const byCollection =
      collectionFilter === "all" ? bySearch : bySearch.filter((doc) => doc.collection_id === collectionFilter);
    const byStorage = byCollection.filter((doc) => passesSelectedFilters(doc, selectedStorageFilters));
    return [...byStorage].sort((a, b) => {
      if (sortBy === "size") return getEffectiveFileSize(b) - getEffectiveFileSize(a);
      if (sortBy === "collection") return a.collection_id.localeCompare(b.collection_id);
      return a.filename.localeCompare(b.filename);
    });
  }, [filteredDocuments, docSearch, collectionFilter, sortBy, selectedStorageFilters]);

  const storageGridAnimKey = useMemo(() => {
    const pillPart = [...selectedStorageFilters].sort().join(",");
    return `${pillPart}|${docSearch}|${collectionFilter}|${sortBy}`;
  }, [selectedStorageFilters, docSearch, collectionFilter, sortBy]);

  const toggleStorageFilter = useCallback((id: StorageFilterId) => {
    setSelectedStorageFilters((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }, []);

  const storageDetailDoc = useMemo(
    () => (storageDetailId ? documents.find((d) => d.document_id === storageDetailId) : undefined),
    [documents, storageDetailId],
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

  const pushToast = useCallback((type: ToastItem["type"], message: string) => {
    const id = `${Date.now()}-${Math.random().toString(36).slice(2, 9)}`;
    setToasts((prev) => [...prev, { id, type, message }]);
    window.setTimeout(() => {
      setToasts((prev) => prev.filter((t) => t.id !== id));
    }, 4200);
  }, []);

  const handleBootstrapSelfReauth = useCallback(() => {
    clearStoredAuth();
    setToken("");
    setRole("");
  }, []);

  useEffect(() => {
    const a = readStoredAuth();
    if (a) {
      setToken(a.token);
      setRole(a.role);
      setEmail(a.email);
    }
  }, []);

  useEffect(() => {
    const onAuth = () => {
      const a = readStoredAuth();
      if (a) {
        setToken(a.token);
        setRole(a.role);
        setEmail(a.email);
      } else {
        setToken("");
        setRole("");
      }
    };
    window.addEventListener("storage", onAuth);
    window.addEventListener("rag-auth-changed", onAuth);
    return () => {
      window.removeEventListener("storage", onAuth);
      window.removeEventListener("rag-auth-changed", onAuth);
    };
  }, []);

  useEffect(() => {
    setWorkspaceScope(readWorkspaceScope());
    const onScope = () => setWorkspaceScope(readWorkspaceScope());
    window.addEventListener("rag-workspace-scope-changed", onScope);
    return () => window.removeEventListener("rag-workspace-scope-changed", onScope);
  }, []);

  useEffect(() => {
    if (!backendUrl) {
      setBackendHealthy(null);
      return;
    }
    let cancelled = false;
    void fetch(`${backendUrl}/health`)
      .then((r) => {
        if (!cancelled) setBackendHealthy(r.ok);
      })
      .catch(() => {
        if (!cancelled) setBackendHealthy(false);
      });
    return () => {
      cancelled = true;
    };
  }, [backendUrl]);

  const authHeaders = useMemo<Record<string, string>>(() => {
    const headers: Record<string, string> = {};
    if (token) {
      headers.Authorization = `Bearer ${token}`;
    }
    return headers;
  }, [token]);

  useEffect(() => {
    if (!token || !backendUrl) {
      setCollaborationWorkspaces([]);
      return;
    }
    let cancelled = false;
    void fetch(`${backendUrl}/collaboration/workspaces`, { headers: authHeaders })
      .then((r) => r.json())
      .then((data: unknown) => {
        if (cancelled || !Array.isArray(data)) return;
        setCollaborationWorkspaces(
          data.map((row: { workspace_id?: string; name?: string; my_role?: string }) => ({
            workspace_id: String(row.workspace_id ?? ""),
            name: String(row.name ?? "Workspace"),
            my_role: typeof row.my_role === "string" ? row.my_role : undefined,
          })),
        );
      })
      .catch(() => {
        if (!cancelled) setCollaborationWorkspaces([]);
      });
    return () => {
      cancelled = true;
    };
  }, [token, backendUrl, authHeaders]);

  const loadDocuments = useCallback(async () => {
    if (!token || !backendUrl) return;
    setIsLoadingDocs(true);
    try {
      const response = await fetch(`${backendUrl}/documents?include_archived=true`, { headers: authHeaders });
      const data = await response.json();
      if (!response.ok) throw new Error(data.detail ?? "Failed to load documents");
      setDocuments(Array.isArray(data) ? data : []);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load documents");
    } finally {
      setIsLoadingDocs(false);
    }
  }, [token, backendUrl, authHeaders]);

  const fetchActivityTimeline = useCallback(
    async (documentId: string) => {
      if (!token || !backendUrl) return;
      setActivityLoading(true);
      try {
        const params = new URLSearchParams();
        if (activityTypeFilter.trim()) params.set("activity_type", activityTypeFilter.trim());
        const qs = params.toString();
        const response = await fetch(`${backendUrl}/documents/${documentId}/activity${qs ? `?${qs}` : ""}`, {
          headers: authHeaders,
        });
        const data = await response.json();
        if (!response.ok) throw new Error(data.detail ?? "Failed to load activity");
        setActivityEntries(Array.isArray(data) ? data : []);
      } catch (err) {
        setError(err instanceof Error ? err.message : "Failed to load activity");
      } finally {
        setActivityLoading(false);
      }
    },
    [token, backendUrl, authHeaders, activityTypeFilter],
  );

  const patchDocumentLifecycle = async (documentId: string, body: Record<string, unknown>) => {
    if (!canEditDocuments) return;
    setStorageDetailBusy(true);
    setError("");
    try {
      const response = await fetch(`${backendUrl}/documents/${documentId}/state`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json", ...authHeaders },
        body: JSON.stringify(body),
      });
      const data = await response.json();
      if (!response.ok) throw new Error(data.detail ?? "Update failed");
      setDocuments((prev) => prev.map((d) => (d.document_id === documentId ? { ...d, ...data } : d)));
      await loadDocuments();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Update failed");
    } finally {
      setStorageDetailBusy(false);
    }
  };

  const saveReadProgress = async (documentId: string) => {
    setStorageDetailBusy(true);
    setError("");
    try {
      const response = await fetch(`${backendUrl}/documents/${documentId}/read-progress`, {
        method: "POST",
        headers: { "Content-Type": "application/json", ...authHeaders },
        body: JSON.stringify({ reading_progress: detailProgress }),
      });
      const data = await response.json();
      if (!response.ok) throw new Error(data.detail ?? "Progress save failed");
      setDocuments((prev) => prev.map((d) => (d.document_id === documentId ? { ...d, ...data } : d)));
      await loadDocuments();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Progress save failed");
    } finally {
      setStorageDetailBusy(false);
    }
  };

  const createTodo = async (documentId: string, titleOverride?: string) => {
    const rawTitle = (titleOverride ?? newTodoTitle).trim();
    if (!canEditDocuments || !rawTitle) return;
    setStorageDetailBusy(true);
    setError("");
    try {
      const response = await fetch(`${backendUrl}/documents/${documentId}/todos`, {
        method: "POST",
        headers: { "Content-Type": "application/json", ...authHeaders },
        body: JSON.stringify({ title: rawTitle, status: "pending" }),
      });
      const data = await response.json();
      if (!response.ok) throw new Error(data.detail ?? "Todo create failed");
      setDocuments((prev) => prev.map((d) => (d.document_id === documentId ? { ...d, ...data } : d)));
      setNewTodoTitle("");
      await loadDocuments();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Todo create failed");
    } finally {
      setStorageDetailBusy(false);
    }
  };

  const quickCreateTodoFromCard = async (documentId: string) => {
    if (!canEditDocuments) return;
    const title = typeof window !== "undefined" ? window.prompt("Todo title") : null;
    if (!title?.trim()) return;
    await createTodo(documentId, title.trim());
  };

  const quickToggleReadFromCard = async (doc: ManagedDocument) => {
    if (!canEditDocuments) return;
    const rs = doc.read_status ?? "unread";
    const next = rs === "unread" ? "completed" : "unread";
    await patchDocumentLifecycle(doc.document_id, { read_status: next });
  };

  const quickArchiveFromCard = async (doc: ManagedDocument) => {
    if (!canEditDocuments || doc.archived) return;
    await patchDocumentLifecycle(doc.document_id, { archived: true });
  };

  const quickPinToggleFromCard = async (doc: ManagedDocument) => {
    if (!canEditDocuments) return;
    await patchDocumentLifecycle(doc.document_id, { pinned: !doc.pinned });
  };

  const patchTodo = async (documentId: string, todoId: string, patch: { status?: "pending" | "done" }) => {
    if (!canEditDocuments) return;
    setStorageDetailBusy(true);
    setError("");
    try {
      const response = await fetch(`${backendUrl}/documents/${documentId}/todos/${todoId}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json", ...authHeaders },
        body: JSON.stringify(patch),
      });
      const data = await response.json();
      if (!response.ok) throw new Error(data.detail ?? "Todo update failed");
      setDocuments((prev) => prev.map((d) => (d.document_id === documentId ? { ...d, ...data } : d)));
      await loadDocuments();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Todo update failed");
    } finally {
      setStorageDetailBusy(false);
    }
  };

  const removeTodo = async (documentId: string, todoId: string) => {
    if (!canEditDocuments) return;
    setStorageDetailBusy(true);
    setError("");
    try {
      const response = await fetch(`${backendUrl}/documents/${documentId}/todos/${todoId}`, {
        method: "DELETE",
        headers: authHeaders,
      });
      const data = await response.json();
      if (!response.ok) throw new Error(data.detail ?? "Todo delete failed");
      setDocuments((prev) => prev.map((d) => (d.document_id === documentId ? { ...d, ...data } : d)));
      await loadDocuments();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Todo delete failed");
    } finally {
      setStorageDetailBusy(false);
    }
  };

  useEffect(() => {
    if (token && (activePanel === "documents" || activePanel === "admin")) {
      void loadDocuments();
    }
  }, [token, activePanel, loadDocuments]);

  useEffect(() => {
    if (!storageDetailId) return;
    const doc = documents.find((d) => d.document_id === storageDetailId);
    if (doc) {
      setDetailProgress(Math.min(100, Math.max(0, Number(doc.reading_progress ?? 0))));
      setDetailReadStatus(doc.read_status ?? "unread");
      setDetailPriority(doc.priority ?? "medium");
      setDetailDueDate(doc.due_date ?? "");
      setDetailPinned(Boolean(doc.pinned));
      setDetailArchived(Boolean(doc.archived));
    }
  }, [storageDetailId, documents]);

  useEffect(() => {
    if (!storageDetailId) {
      setActivityEntries([]);
      return;
    }
    void fetchActivityTimeline(storageDetailId);
  }, [storageDetailId, fetchActivityTimeline]);

  const formatFileSize = (size: number) => {
    if (size < 1024) return `${size} B`;
    if (size < 1024 * 1024) return `${(size / 1024).toFixed(1)} KB`;
    return `${(size / (1024 * 1024)).toFixed(2)} MB`;
  };

  const handleUpload = async (event: FormEvent) => {
    event.preventDefault();
    if (!file || !token || !canEditDocuments) return;
    if (!backendUrl) {
      setError("NEXT_PUBLIC_BACKEND_URL is not configured.");
      return;
    }

    setIsUploading(true);
    setUploadPct(6);
    setError("");
    const progressTimer = window.setInterval(() => {
      setUploadPct((p) => Math.min(p + 14, 92));
    }, 170);
    try {
      const formData = new FormData();
      formData.append("file", file);
      formData.append("collection_id", collectionId.trim() || "default");
      if (uploadWorkspaceId.trim()) formData.append("workspace_id", uploadWorkspaceId.trim());
      const response = await fetch(`${backendUrl}/upload`, {
        method: "POST",
        headers: authHeaders,
        body: formData,
      });
      const data = await response.json();
      if (!response.ok) throw new Error(data.detail ?? "Upload failed");
      setDocumentId(data.document_id);
      setLastUploadId(String(data.document_id ?? ""));
      await loadDocuments();
      pushToast("success", `Indexed · document ${String(data.document_id ?? "").slice(0, 8)}…`);
    } catch (err) {
      const msg = err instanceof Error ? err.message : "Upload failed";
      setError(msg);
      pushToast("error", msg);
    } finally {
      window.clearInterval(progressTimer);
      setUploadPct(100);
      window.setTimeout(() => setUploadPct(0), 650);
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
    setQueryUiPhase("thinking");
    setRetrieveIntelFault(null);
    setAnswerFaultInfo(null);
    setFeedbackSnapshot(null);
    setFeedbackSent(false);
    setFeedbackChoice(null);
    setFeedbackNegativeComment("");
    setError("");
    try {
      const payloadAnswer = JSON.stringify({
        question,
        document_id: documentId.trim(),
        top_k: topK,
        answer_mode: answerMode,
        answer_length: answerLength,
        persist_thread: persistThread,
        ...(persistThread && activeThreadId.trim() ? { thread_id: activeThreadId.trim() } : {}),
      });
      const payloadRetrieve = JSON.stringify({ query: question, document_id: documentId.trim(), top_k: topK });
      const sharedRetryOpts = {
        retries: 2,
        onRetry: () => setQueryUiPhase("retrying"),
      };

      const retrieveExec = async (): Promise<RetrievalItem[]> => {
        const res = await fetchWithRetry(
          `${backendUrl}/retrieve`,
          {
            method: "POST",
            headers: { "Content-Type": "application/json", ...authHeaders },
            body: payloadRetrieve,
          },
          { ...sharedRetryOpts, timeoutMs: 75_000 },
        );
        const data = (await res.json()) as unknown;
        if (!res.ok) {
          const detail = typeof data === "object" && data && "detail" in data ? (data as { detail?: unknown }).detail : undefined;
          throw new Error(typeof detail === "string" ? detail : "Retrieve failed");
        }
        return Array.isArray(data) ? (data as RetrievalItem[]) : [];
      };

      const queryExec = async (): Promise<Record<string, unknown>> => {
        const res = await fetchWithRetry(
          `${backendUrl}/query`,
          {
            method: "POST",
            headers: { "Content-Type": "application/json", ...authHeaders },
            body: payloadAnswer,
          },
          { ...sharedRetryOpts, timeoutMs: 95_000 },
        );
        const data = (await res.json()) as Record<string, unknown>;
        if (!res.ok) {
          const detail = data.detail;
          throw new Error(typeof detail === "string" ? detail : "Query failed");
        }
        return data;
      };

      const [rSettled, qSettled] = await Promise.allSettled([retrieveExec(), queryExec()]);

      let retrieveFaultMsg: string | null = null;
      let retrieveList: RetrievalItem[] = [];
      if (rSettled.status === "fulfilled") {
        retrieveList = rSettled.value;
      } else {
        const msg = rSettled.reason instanceof Error ? rSettled.reason.message : "Retrieve failed";
        retrieveFaultMsg =
          msg.includes("Abort") || msg.toLowerCase().includes("aborted")
            ? "Retrieval timed out — try again shortly."
            : `Retrieval unavailable (${msg}).`;
        setRetrieveIntelFault(retrieveFaultMsg);
      }

      const answerData =
        qSettled.status === "fulfilled"
          ? (qSettled.value as Record<string, unknown>)
          : (null as Record<string, unknown> | null);

      setChunks(retrieveList);

      if (answerData) {
        setAnswer(typeof answerData.answer === "string" ? answerData.answer : "");
        setAnswerCitations(Array.isArray(answerData.citations) ? (answerData.citations as ParagraphCitationBlock[]) : []);
        setAnswerConfidence(
          answerData.confidence && typeof answerData.confidence === "object"
            ? (answerData.confidence as AnswerConfidence)
            : null,
        );
        setEvidenceSpans(Array.isArray(answerData.evidence_spans) ? (answerData.evidence_spans as EvidenceSpan[]) : []);

        const degraded = Boolean(answerData.degraded);
        const retrievalDeg = Boolean(answerData.retrieval_degraded);
        if (degraded || retrievalDeg) {
          setAnswerFaultInfo({
            degraded,
            degradedReason: typeof answerData.degraded_reason === "string" ? answerData.degraded_reason : null,
            retrievalDegraded: retrievalDeg,
            llmAttempts: typeof answerData.llm_attempts === "number" ? answerData.llm_attempts : null,
          });
        } else {
          setAnswerFaultInfo(null);
        }

        const confScore =
          answerData.confidence && typeof (answerData.confidence as AnswerConfidence).score === "number"
            ? (answerData.confidence as AnswerConfidence).score
            : null;
        setFeedbackSnapshot({
          question,
          document_id: documentId.trim(),
          answer: typeof answerData.answer === "string" ? answerData.answer : "",
          confidence_score: confScore,
          retrieved_chunks: retrieveList.map((c) => ({
            chunk_id: c.chunk_id,
            relevance_score: c.relevance_score,
          })),
        });

        if (persistThread && typeof answerData.thread_id === "string" && answerData.thread_id.trim()) {
          setActiveThreadId(answerData.thread_id.trim());
          setThreadRefreshNonce((n) => n + 1);
        }

        setError("");
      } else {
        const qMsg = qSettled.status === "rejected" && qSettled.reason instanceof Error ? qSettled.reason.message : "Query failed";
        setAnswerFaultInfo(null);
        setAnswerCitations([]);
        setAnswerConfidence(null);
        setEvidenceSpans([]);
        setFeedbackSnapshot(null);
        setAnswer(
          retrieveList.length > 0
            ? "AI synthesis temporarily unavailable — review retrieved excerpts on the right while we reconnect."
            : `Could not reach AI services (${qMsg}). Check network or retry.`,
        );
        setError(retrieveList.length > 0 ? "AI synthesis failed — excerpts still visible." : `AI workspace degraded — ${qMsg}`);
        pushToast("error", retrieveList.length > 0 ? "AI temporarily unavailable — excerpts retained." : "Unable to complete AI request.");
      }

      if (answerData && retrieveFaultMsg) {
        pushToast("error", "Retrieval preview incomplete — answer may still reflect grounded synthesis.");
      }
    } catch (err) {
      const msg = err instanceof Error ? err.message : "Query failed";
      setAnswerFaultInfo(null);
      setError(msg);
      pushToast("error", msg);
    } finally {
      setQueryUiPhase("idle");
      setIsQuerying(false);
    }
  };

  const submitFeedback = async (sentiment: "positive" | "negative") => {
    if (!feedbackSnapshot || !token || !backendUrl) return;
    setFeedbackBusy(true);
    setError("");
    try {
      const response = await fetch(`${backendUrl}/feedback`, {
        method: "POST",
        headers: { "Content-Type": "application/json", ...authHeaders },
        body: JSON.stringify({
          sentiment,
          query: feedbackSnapshot.question,
          document_id: feedbackSnapshot.document_id,
          answer: feedbackSnapshot.answer,
          confidence_score: feedbackSnapshot.confidence_score ?? undefined,
          retrieved_chunks: feedbackSnapshot.retrieved_chunks,
        }),
      });
      const data = await response.json();
      if (!response.ok) throw new Error(typeof data.detail === "string" ? data.detail : "Feedback failed");
      setFeedbackSent(true);
      setFeedbackChoice(sentiment);
      pushToast(
        "success",
        sentiment === "negative" && feedbackNegativeComment.trim()
          ? "Feedback recorded (note kept in this session only)."
          : "Thanks — feedback recorded.",
      );
    } catch (err) {
      const msg = err instanceof Error ? err.message : "Feedback failed";
      setError(msg);
      pushToast("error", msg);
    } finally {
      setFeedbackBusy(false);
    }
  };

  const intelligenceDoc = useMemo(() => {
    const id = documentId.trim();
    if (!id) return { meta: null as { id: string; collection_id?: string } | null, title: null as string | null };
    const doc = documents.find((d) => d.document_id === id);
    return {
      meta: { id, collection_id: doc?.collection_id },
      title: doc?.filename ?? null,
    };
  }, [documentId, documents]);

  const chunkHits = useMemo(
    () =>
      chunks.map((c) => ({
        chunk_id: c.chunk_id,
        document_id: c.document_id,
        score: c.relevance_score,
        content: c.chunk_text,
        metadata: c.metadata,
      })),
    [chunks],
  );

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

      <ToastStack toasts={toasts} />
      <div
        className={`${ws.shell} ${sidebarCollapsed ? ws.shellCollapsed : ""} ${activePanel === "admin" ? ws.shellAdmin : ""}`}
      >
        <WorkspaceSidebar
          collapsed={sidebarCollapsed}
          onToggleCollapsed={() => setSidebarCollapsed((c) => !c)}
          active={activePanel}
          onNavigate={navigatePanel}
          backendUrl={backendUrl}
          showAdminNav={role === "admin"}
        >
          {token && backendUrl ? (
            <TeamCollaborationPanel backendUrl={backendUrl} authHeaders={authHeaders} pushToast={pushToast} />
          ) : null}
          {token ? (
            <div style={{ display: "grid", gap: "0.45rem", width: "100%", fontSize: "0.78rem" }}>
              <span style={{ opacity: 0.88, wordBreak: "break-all" }} data-testid="workspace-session-email" title={email}>
                {email ? `${email} · ${role || "user"}` : `Signed in · ${role || "user"}`}
              </span>
              <button
                type="button"
                data-testid="workspace-logout-button"
                onClick={() => {
                  clearStoredAuth();
                  setToken("");
                  setRole("");
                }}
                style={{
                  padding: "0.55rem",
                  borderRadius: 10,
                  border: "1px solid rgba(148,163,184,0.35)",
                  background: "rgba(30,41,59,0.55)",
                  color: "#e5e7eb",
                  fontWeight: 700,
                  cursor: "pointer",
                  fontSize: "0.82rem",
                }}
              >
                Log out
              </button>
            </div>
          ) : (
            <div style={{ display: "grid", gap: "0.4rem", width: "100%" }}>
              <Link
                href="/login"
                data-testid="workspace-link-login"
                style={{
                  padding: "0.55rem",
                  borderRadius: 10,
                  border: "1px solid rgba(99,102,241,0.45)",
                  background: "#4f46e5",
                  color: "white",
                  fontWeight: 700,
                  textAlign: "center",
                  textDecoration: "none",
                  fontSize: "0.82rem",
                }}
              >
                Sign in
              </Link>
              <Link
                href="/register"
                data-testid="workspace-link-register"
                style={{
                  padding: "0.55rem",
                  borderRadius: 10,
                  border: "1px solid rgba(34,211,238,0.45)",
                  background: "rgba(6,182,212,0.25)",
                  color: "#cffafe",
                  fontWeight: 700,
                  textAlign: "center",
                  textDecoration: "none",
                  fontSize: "0.82rem",
                }}
              >
                Create account
              </Link>
            </div>
          )}
        </WorkspaceSidebar>

        <div className={ws.centerMain}>
          <header style={{ marginBottom: "0.65rem" }}>
            <h1 style={{ fontSize: "clamp(1.35rem, 2.5vw, 2rem)", margin: "0 0 0.35rem", letterSpacing: "-0.02em" }}>
              {activePanel === "admin" ? "Admin Center" : "RAG workspace"}
            </h1>
            <p style={{ margin: 0, opacity: 0.88, fontSize: "0.88rem" }}>
              {activePanel === "admin"
                ? "System monitoring · observability · error intelligence · live audit trail"
                : "Documents · grounded retrieval · transparent answers"}
            </p>
          </header>

          {error ? (
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
          ) : null}

          <div key={activePanel} className={ws.centerStage}>
            {activePanel === "dashboard" ? (
              <DashboardOverview documentCount={filteredDocuments.length} lastUploadId={lastUploadId} backendHealthy={backendHealthy} />
            ) : null}

            {activePanel === "admin" ? (
              role === "admin" ? (
                <AdminCommandCenter
                  backendUrl={backendUrl}
                  authHeaders={authHeaders}
                  documentCount={documents.length}
                  totalStorageBytes={adminStorageBytes}
                  onRefreshDocuments={loadDocuments}
                  isLoadingDocs={isLoadingDocs}
                />
              ) : (
                <section
                  className={`${ws.glassElevated}`}
                  style={{ padding: "1.35rem", maxWidth: "42rem" }}
                  data-testid="admin-center-access-gate"
                >
                  <h2 style={{ margin: "0 0 0.45rem", fontSize: "1.08rem" }}>Admin Center · restricted</h2>
                  <p style={{ margin: "0 0 0.75rem", opacity: 0.86, lineHeight: 1.5 }}>
                    System monitoring (metrics, observability charts, audit feed, and error intelligence) requires an administrator role.
                    {token ? ` Your role is “${role || "unknown"}”.` : " Sign in to continue."}
                  </p>
                  <p style={{ margin: 0, fontSize: "0.82rem", opacity: 0.68 }}>
                    Tip: open this tab after signing in as an admin user, or visit{" "}
                    <code style={{ opacity: 0.95 }}>/admin</code> once redirected from routing.
                  </p>
                </section>
              )
            ) : null}

            {activePanel === "documents" ? (
              <>
                <UploadDropzone
                  collectionId={collectionId}
                  onCollectionChange={setCollectionId}
                  uploadWorkspaceId={uploadWorkspaceId}
                  onUploadWorkspaceChange={setUploadWorkspaceId}
                  workspaceUploadOptions={workspaceUploadOptions}
                  file={file}
                  onFileChange={setFile}
                  onSubmit={handleUpload}
                  canUpload={canUpload}
                  isUploading={isUploading}
                  uploadProgress={uploadPct}
                />
                <section className={`${ws.glassElevated}`} style={{ padding: "1rem", backdropFilter: "blur(8px)" }}>
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", gap: "0.75rem", flexWrap: "wrap" }}>
                  <div>
                    <h2 style={{ marginTop: 0, marginBottom: "0.25rem" }}>Document library</h2>
                    <p style={{ margin: 0, fontSize: "0.82rem", opacity: 0.78 }}>Card grid · hover actions · semantic states</p>
                  </div>
                  <button data-testid="refresh-documents-button" onClick={loadDocuments} style={{ padding: "0.45rem 0.7rem", borderRadius: 10, border: "1px solid rgba(148,163,184,0.25)", background: "#0f172a", color: "#e5e7eb", cursor: "pointer" }}>
                    {isLoadingDocs ? "Refreshing..." : "Refresh"}
                  </button>
                </div>
                <DocumentFilterPills documents={filteredDocuments} selected={selectedStorageFilters} onToggle={toggleStorageFilter} />
                <div style={{ display: "grid", gridTemplateColumns: "1fr 160px 160px", gap: "0.6rem", marginBottom: "0.55rem" }}>
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
                {isLoadingDocs && filteredDocuments.length === 0 ? <DocumentGridSkeleton /> : null}
                {!isLoadingDocs && documents.length === 0 ? <p data-testid="documents-empty">No documents indexed yet.</p> : null}
                {!isLoadingDocs && documents.length > 0 && filteredDocuments.length === 0 ? (
                  <p data-testid="documents-scope-empty" style={{ opacity: 0.85 }}>
                    No documents in the selected workspace scope — switch Library filter in the top bar or upload into this team.
                  </p>
                ) : null}
                {!isLoadingDocs && filteredDocuments.length > 0 && visibleDocuments.length === 0 ? (
                  <p data-testid="documents-filter-empty" style={{ opacity: 0.85 }}>
                    No documents match the current filters and search.
                  </p>
                ) : null}
                {filteredDocuments.length > 0 && visibleDocuments.length > 0 ? (
                  <div
                    key={storageGridAnimKey}
                    data-testid="documents-list"
                    className={`${storageUx.grid} ${storageUx.gridFade}`}
                    style={{ marginTop: "0.25rem" }}
                  >
                    {visibleDocuments.map((doc) => (
                      <DocumentCard
                        key={doc.document_id}
                        doc={doc}
                        selectedQueryId={documentId}
                        formatFileSize={formatFileSize}
                        fileSize={getEffectiveFileSize(doc)}
                        canEdit={canEditDocuments}
                        busy={storageDetailBusy}
                        onOpenQuery={() => {
                          setDocumentId(doc.document_id);
                          navigatePanel("query");
                        }}
                        onManage={() => setStorageDetailId(doc.document_id)}
                        onToggleRead={() => void quickToggleReadFromCard(doc)}
                        onQuickTodo={() => void quickCreateTodoFromCard(doc.document_id)}
                        onArchive={() => void quickArchiveFromCard(doc)}
                        onPinToggle={() => void quickPinToggleFromCard(doc)}
                      />
                    ))}
                  </div>
                ) : null}
                {storageDetailId && (
                  <div
                    data-testid="document-storage-detail-panel"
                    style={{
                      marginTop: "1rem",
                      padding: "1rem",
                      borderRadius: 14,
                      border: "1px solid rgba(167,139,250,0.35)",
                      background: "rgba(30,27,75,0.35)",
                    }}
                  >
                    <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", gap: "0.75rem", flexWrap: "wrap" }}>
                      <h3 style={{ margin: 0 }}>Document productivity</h3>
                      <button
                        data-testid="document-storage-detail-close"
                        type="button"
                        onClick={() => setStorageDetailId(null)}
                        style={{ padding: "0.4rem 0.65rem", borderRadius: 8, border: "1px solid rgba(148,163,184,0.35)", background: "#0f172a", color: "#e5e7eb", cursor: "pointer" }}
                      >
                        Close
                      </button>
                    </div>
                    {!storageDetailDoc ? (
                      <p data-testid="document-storage-detail-missing">Document not in the current list. Change filters or refresh.</p>
                    ) : (
                      <>
                        <p style={{ opacity: 0.88, fontSize: "0.9rem", marginBottom: "0.75rem" }}>
                          <strong>{storageDetailDoc.filename}</strong> · AI usage count: {storageDetailDoc.ai_usage_count ?? 0}
                          {storageDetailDoc.last_read_at ? ` · Last read: ${storageDetailDoc.last_read_at}` : ""}
                          {storageDetailDoc.due_date ? ` · Due: ${storageDetailDoc.due_date}` : ""}
                        </p>
                        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(260px, 1fr))", gap: "1rem" }}>
                          <div style={{ border: "1px solid rgba(148,163,184,0.25)", borderRadius: 12, padding: "0.75rem", background: "rgba(15,23,42,0.55)" }}>
                            <h4 style={{ marginTop: 0 }}>Reading</h4>
                            <label style={{ display: "grid", gap: "0.35rem", fontSize: "0.88rem" }}>
                              Progress ({detailProgress}%)
                              <input
                                data-testid="document-storage-progress-slider"
                                type="range"
                                min={0}
                                max={100}
                                value={detailProgress}
                                onChange={(e) => setDetailProgress(Number(e.target.value))}
                              />
                            </label>
                            <button
                              data-testid="document-storage-save-progress-button"
                              type="button"
                              disabled={storageDetailBusy || !storageDetailId}
                              onClick={() => storageDetailId && void saveReadProgress(storageDetailId)}
                              style={{
                                marginTop: "0.55rem",
                                padding: "0.45rem 0.65rem",
                                borderRadius: 8,
                                border: "1px solid rgba(52,211,153,0.45)",
                                background: "rgba(16,185,129,0.2)",
                                color: "#d1fae5",
                                cursor: storageDetailBusy ? "wait" : "pointer",
                              }}
                            >
                              Save progress
                            </button>
                            {canEditDocuments ? (
                              <>
                                <hr style={{ borderColor: "rgba(148,163,184,0.25)", margin: "0.85rem 0" }} />
                                <div style={{ display: "grid", gap: "0.45rem", fontSize: "0.88rem" }}>
                                  <label>
                                    Read status{" "}
                                    <select
                                      data-testid="document-storage-read-status-select"
                                      value={detailReadStatus}
                                      onChange={(e) => setDetailReadStatus(e.target.value as typeof detailReadStatus)}
                                      style={{ marginLeft: 6, background: "#0f172a", border: "1px solid #334155", color: "#e5e7eb", borderRadius: 8, padding: "0.25rem" }}
                                    >
                                      <option value="unread">unread</option>
                                      <option value="reading">reading</option>
                                      <option value="completed">completed</option>
                                    </select>
                                  </label>
                                  <label>
                                    Priority{" "}
                                    <select
                                      data-testid="document-storage-priority-select"
                                      value={detailPriority}
                                      onChange={(e) => setDetailPriority(e.target.value as typeof detailPriority)}
                                      style={{ marginLeft: 6, background: "#0f172a", border: "1px solid #334155", color: "#e5e7eb", borderRadius: 8, padding: "0.25rem" }}
                                    >
                                      <option value="low">low</option>
                                      <option value="medium">medium</option>
                                      <option value="high">high</option>
                                    </select>
                                  </label>
                                  <label style={{ display: "grid", gap: "0.25rem" }}>
                                    Due date (YYYY-MM-DD)
                                    <input
                                      data-testid="document-storage-due-date-input"
                                      value={detailDueDate}
                                      onChange={(e) => setDetailDueDate(e.target.value)}
                                      placeholder="optional"
                                      style={{ background: "#0f172a", border: "1px solid #334155", color: "#e5e7eb", borderRadius: 8, padding: "0.35rem" }}
                                    />
                                  </label>
                                  <label style={{ display: "flex", alignItems: "center", gap: "0.35rem", cursor: "pointer" }}>
                                    <input data-testid="document-storage-pinned-checkbox" type="checkbox" checked={detailPinned} onChange={(e) => setDetailPinned(e.target.checked)} />
                                    Pinned
                                  </label>
                                  <label style={{ display: "flex", alignItems: "center", gap: "0.35rem", cursor: "pointer" }}>
                                    <input data-testid="document-storage-archived-checkbox" type="checkbox" checked={detailArchived} onChange={(e) => setDetailArchived(e.target.checked)} />
                                    Archived
                                  </label>
                                  <button
                                    data-testid="document-storage-save-lifecycle-button"
                                    type="button"
                                    disabled={storageDetailBusy || !storageDetailId}
                                    onClick={() =>
                                      storageDetailId &&
                                      void patchDocumentLifecycle(storageDetailId, {
                                        read_status: detailReadStatus,
                                        priority: detailPriority,
                                        due_date: detailDueDate.trim() || "",
                                        pinned: detailPinned,
                                        archived: detailArchived,
                                      })
                                    }
                                    style={{
                                      marginTop: "0.35rem",
                                      padding: "0.45rem 0.65rem",
                                      borderRadius: 8,
                                      border: "1px solid rgba(99,102,241,0.45)",
                                      background: "rgba(79,70,229,0.25)",
                                      color: "#e0e7ff",
                                      cursor: storageDetailBusy ? "wait" : "pointer",
                                    }}
                                  >
                                    Save lifecycle
                                  </button>
                                </div>
                              </>
                            ) : (
                              <p style={{ fontSize: "0.85rem", opacity: 0.85 }}>Lifecycle editing requires user or admin role.</p>
                            )}
                          </div>
                          <div style={{ border: "1px solid rgba(148,163,184,0.25)", borderRadius: 12, padding: "0.75rem", background: "rgba(15,23,42,0.55)" }}>
                            <h4 style={{ marginTop: 0 }}>Todos</h4>
                            {!canEditDocuments ? (
                              <p style={{ fontSize: "0.85rem", opacity: 0.85 }}>Todo edits require user or admin.</p>
                            ) : (
                              <div style={{ display: "flex", gap: "0.45rem", marginBottom: "0.65rem", flexWrap: "wrap" }}>
                                <input
                                  data-testid="document-storage-new-todo-input"
                                  value={newTodoTitle}
                                  onChange={(e) => setNewTodoTitle(e.target.value)}
                                  placeholder="New todo title"
                                  style={{ flex: "1 1 140px", background: "#0f172a", border: "1px solid #334155", color: "#e5e7eb", borderRadius: 8, padding: "0.35rem" }}
                                />
                                <button
                                  data-testid="document-storage-add-todo-button"
                                  type="button"
                                  disabled={storageDetailBusy}
                                  onClick={() => storageDetailId && void createTodo(storageDetailId)}
                                  style={{
                                    padding: "0.35rem 0.55rem",
                                    borderRadius: 8,
                                    border: "1px solid rgba(94,234,212,0.45)",
                                    background: "rgba(45,212,191,0.15)",
                                    color: "#ccfbf1",
                                    cursor: "pointer",
                                  }}
                                >
                                  Add
                                </button>
                              </div>
                            )}
                            <ul data-testid="document-storage-todo-list" style={{ margin: 0, paddingLeft: "1.1rem", fontSize: "0.88rem" }}>
                              {(storageDetailDoc.todos ?? []).map((t) => (
                                <li key={t.todo_id} style={{ marginBottom: "0.45rem" }}>
                                  <span style={{ textDecoration: t.status === "done" ? "line-through" : undefined }}>{t.title}</span>{" "}
                                  <span style={{ opacity: 0.75 }}>({t.status})</span>
                                  {canEditDocuments ? (
                                    <>
                                      <button
                                        data-testid={`document-storage-todo-toggle-${t.todo_id}`}
                                        type="button"
                                        disabled={storageDetailBusy}
                                        onClick={() =>
                                          storageDetailId &&
                                          void patchTodo(storageDetailId, t.todo_id, {
                                            status: t.status === "done" ? "pending" : "done",
                                          })
                                        }
                                        style={{ marginLeft: 8, fontSize: "0.75rem", cursor: "pointer" }}
                                      >
                                        Toggle
                                      </button>
                                      <button
                                        data-testid={`document-storage-todo-delete-${t.todo_id}`}
                                        type="button"
                                        disabled={storageDetailBusy}
                                        onClick={() => storageDetailId && void removeTodo(storageDetailId, t.todo_id)}
                                        style={{ marginLeft: 6, fontSize: "0.75rem", cursor: "pointer" }}
                                      >
                                        Delete
                                      </button>
                                    </>
                                  ) : null}
                                </li>
                              ))}
                            </ul>
                          </div>
                          <div style={{ border: "1px solid rgba(148,163,184,0.25)", borderRadius: 12, padding: "0.75rem", background: "rgba(15,23,42,0.55)", gridColumn: "1 / -1" }}>
                            <div style={{ display: "flex", flexWrap: "wrap", gap: "0.65rem", alignItems: "center", marginBottom: "0.55rem" }}>
                              <h4 style={{ margin: 0, flex: "1 1 auto" }}>Activity timeline</h4>
                              <select
                                data-testid="document-storage-activity-filter-select"
                                value={activityTypeFilter}
                                onChange={(e) => setActivityTypeFilter(e.target.value)}
                                style={{ background: "#0f172a", border: "1px solid #334155", color: "#e5e7eb", borderRadius: 8, padding: "0.35rem" }}
                              >
                                <option value="">All types</option>
                                <option value="uploaded">uploaded</option>
                                <option value="opened_read">opened_read</option>
                                <option value="marked_completed">marked_completed</option>
                                <option value="annotated">annotated</option>
                                <option value="reindexed">reindexed</option>
                                <option value="archived">archived</option>
                                <option value="ai_answer_used">ai_answer_used</option>
                              </select>
                              <button
                                data-testid="document-storage-activity-refresh-button"
                                type="button"
                                onClick={() => storageDetailId && void fetchActivityTimeline(storageDetailId)}
                                style={{ padding: "0.35rem 0.55rem", borderRadius: 8, border: "1px solid rgba(148,163,184,0.35)", background: "#0f172a", color: "#e5e7eb", cursor: "pointer" }}
                              >
                                {activityLoading ? "Loading…" : "Refresh activity"}
                              </button>
                            </div>
                            <ul data-testid="document-storage-activity-list" style={{ margin: 0, paddingLeft: "1.05rem", fontSize: "0.82rem", maxHeight: 240, overflowY: "auto" }}>
                              {activityEntries.map((a) => (
                                <li key={a.activity_id} style={{ marginBottom: "0.35rem" }}>
                                  <strong>{a.activity_type}</strong> · {a.timestamp}
                                  {Object.keys(a.details ?? {}).length ? ` · ${JSON.stringify(a.details)}` : ""}
                                </li>
                              ))}
                            </ul>
                          </div>
                        </div>
                      </>
                    )}
                  </div>
                )}
              </section>
              </>
            ) : null}

            {activePanel === "query" ? (
              <QueryWorkspaceForm
                documentId={documentId}
                onDocumentIdChange={setDocumentId}
                question={question}
                onQuestionChange={setQuestion}
                answerMode={answerMode}
                onAnswerModeChange={setAnswerMode}
                answerLength={answerLength}
                onAnswerLengthChange={setAnswerLength}
                topK={topK}
                onTopKChange={setTopK}
                onSubmit={handleQuery}
                canQuery={canQuery}
                isQuerying={isQuerying}
                statusLine={queryStatusLine}
                persistThread={persistThread}
                onPersistThreadChange={setPersistThread}
              />
            ) : null}

            {activePanel === "settings" ? (
              <div className={ws.glassElevated} style={{ padding: "1.15rem", display: "grid", gap: "0.85rem" }}>
                <h2 style={{ margin: 0, fontSize: "1.05rem" }}>Workspace settings</h2>
                <p style={{ margin: 0, opacity: 0.85, fontSize: "0.88rem" }}>Role: {role || "—"}</p>
                <p style={{ margin: 0, opacity: 0.75, fontSize: "0.82rem", wordBreak: "break-all" }}>{backendUrl || "No backend URL configured"}</p>
                {token && showAdminBootstrapUi ? (
                  <AdminBootstrapPanel
                    backendUrl={backendUrl}
                    authHeaders={authHeaders}
                    sessionEmail={email}
                    pushToast={pushToast}
                    onPromotedSelfReauth={handleBootstrapSelfReauth}
                  />
                ) : null}
              </div>
            ) : null}
          </div>
        </div>

        {activePanel !== "admin" ? (
          <IntelligencePanel
            selectedDocTitle={intelligenceDoc.title}
            selectedDocMeta={intelligenceDoc.meta}
            chunks={chunkHits}
            answer={answer}
            confidence={answerConfidence?.score ?? null}
            feedbackChoice={feedbackChoice}
            feedbackSent={feedbackSent}
            feedbackBusy={feedbackBusy}
            feedbackNegativeComment={feedbackNegativeComment}
            onFeedbackNegativeCommentChange={setFeedbackNegativeComment}
            onFeedbackPositive={() => void submitFeedback("positive")}
            onFeedbackNegativeIntent={() => setFeedbackChoice("negative")}
            onFeedbackNegativeSubmit={() => void submitFeedback("negative")}
            loadingChunks={isQuerying}
            feedbackAvailable={Boolean(feedbackSnapshot)}
            evidenceSpans={evidenceSpans}
            answerCitations={answerCitations}
            queryPhase={queryUiPhase}
            retrieveFaultNotice={retrieveIntelFault}
            answerFault={answerFaultInfo}
            collaborationSlot={
              token && backendUrl ? (
                <CollaborationThreadPanel
                  backendUrl={backendUrl}
                  authHeaders={authHeaders}
                  documentId={documentId}
                  activeThreadId={activeThreadId}
                  onSelectThread={setActiveThreadId}
                  pushToast={pushToast}
                  refreshNonce={threadRefreshNonce}
                />
              ) : null
            }
          />
        ) : null}
      </div>

    </main>
  );
}

export default function Page() {
  return (
    <Suspense fallback={<WorkspaceLoadingFallback />}>
      <RagWorkspace />
    </Suspense>
  );
}
