"use client";

import ws from "./workspace.module.css";

export type WorkspaceTab = "dashboard" | "admin" | "documents" | "query" | "settings";

type Props = {
  collapsed: boolean;
  onToggleCollapsed: () => void;
  active: WorkspaceTab;
  onNavigate: (tab: WorkspaceTab) => void;
  backendUrl: string;
  showAdminNav?: boolean;
  children: React.ReactNode;
};

const ADMIN_NAV_ITEM = {
  tab: "admin" as const,
  label: "Admin Center",
  icon: "◫",
  testId: "nav-admin",
};

const NAV_PUBLIC: { tab: WorkspaceTab; label: string; icon: string; testId: string }[] = [
  { tab: "dashboard", label: "Dashboard", icon: "◆", testId: "nav-dashboard" },
  { tab: "documents", label: "Documents", icon: "▤", testId: "nav-documents" },
  { tab: "query", label: "Query", icon: "✦", testId: "nav-query" },
  { tab: "settings", label: "Settings", icon: "⚙", testId: "nav-settings" },
];

function navItems(showAdminNav: boolean) {
  if (!showAdminNav) return NAV_PUBLIC;
  const [dash, ...rest] = NAV_PUBLIC;
  return [dash, ADMIN_NAV_ITEM, ...rest];
}

export function WorkspaceSidebar({
  collapsed,
  onToggleCollapsed,
  active,
  onNavigate,
  backendUrl,
  showAdminNav = false,
  children,
}: Props) {
  return (
    <aside
      className={`${ws.sidebar} ${collapsed ? ws.sidebarCollapsedInner : ""}`}
      data-testid="workspace-sidebar"
    >
      <button
        type="button"
        className={ws.collapseToggle}
        onClick={onToggleCollapsed}
        title={collapsed ? "Expand sidebar" : "Collapse sidebar"}
        data-testid="sidebar-collapse-toggle"
        aria-expanded={!collapsed}
      >
        {collapsed ? "»" : "«"}
      </button>
      {!collapsed && (
        <div style={{ marginBottom: "0.25rem" }}>
          <h2 style={{ margin: "0 0 0.2rem", fontSize: "1.05rem", letterSpacing: "-0.02em" }}>AI Workspace</h2>
          <p style={{ margin: 0, fontSize: "0.72rem", opacity: 0.72, wordBreak: "break-all" }} title={backendUrl}>
            {backendUrl || "No API URL"}
          </p>
        </div>
      )}
      {children}
      <nav style={{ display: "flex", flexDirection: "column", gap: "0.35rem", marginTop: "0.35rem", flex: 1 }}>
        {navItems(showAdminNav).map((item) => (
          <button
            key={item.tab}
            type="button"
            data-testid={item.testId}
            className={`${ws.navBtn} ${active === item.tab ? ws.navBtnActive : ""}`}
            onClick={() => onNavigate(item.tab)}
            title={item.tab === "admin" ? `${item.label} · System monitoring` : item.label}
          >
            <span className={ws.navIcon} aria-hidden>
              {item.icon}
            </span>
            {!collapsed ? <span>{item.label}</span> : null}
          </button>
        ))}
      </nav>
    </aside>
  );
}
