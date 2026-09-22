import { NavLink, Outlet, useLocation } from "react-router-dom";
import Logo from "./Logo.jsx";
import { ConnectionDot, DemoBadge, Icon, OfflineBanner } from "./ui.jsx";
import { useChrono } from "../hooks/useChrono.js";

const NAV = [
  { to: "/overview", label: "Overview", icon: "grid" },
  { to: "/instances", label: "Instances", icon: "box" },
  { to: "/checkpoints", label: "Checkpoints", icon: "bookmark" },
  { to: "/migrations", label: "Migrations", icon: "swap" },
  { to: "/monitoring", label: "Monitoring", icon: "pulse" },
  { to: "/simulate", label: "Simulate", icon: "zap" },
];

// Deterministic active-state: exact match per item, except Overview which owns
// its /overview/* children (Timeline). Never relies on NavLink's deferred
// isActive, so the highlighted item always reflects the current route.
export function useActiveNav() {
  const { pathname } = useLocation();
  return (to) => (to === "/overview" ? pathname === "/overview" || pathname.startsWith("/overview/") : pathname === to);
}

function navClass(active) {
  return `flex items-center gap-3 rounded-sm px-3 py-2 text-sm transition-colors ${
    active ? "bg-elevated text-primary" : "text-muted hover:bg-surface hover:text-primary"
  } lg:px-3 justify-center lg:justify-start`;
}

function Sidebar() {
  const isActive = useActiveNav();
  return (
    <aside className="fixed inset-y-0 left-0 z-20 hidden w-20 flex-col border-r border-border-mid/30 bg-base/90 backdrop-blur sm:flex lg:w-60">
      <div className="flex h-16 items-center px-4 lg:px-5">
        <Logo compact={true} />
      </div>
      <nav className="flex flex-1 flex-col gap-1 px-2.5 py-3 lg:px-3" aria-label="Primary">
        {NAV.map((item) => (
          <NavLink
            key={item.to}
            to={item.to}
            aria-current={isActive(item.to) ? "page" : undefined}
            className={navClass(isActive(item.to))}
          >
            <Icon name={item.icon} className="h-4 w-4 shrink-0" />
            <span className="hidden lg:inline">{item.label}</span>
          </NavLink>
        ))}
      </nav>
      <div className="mb-3 px-2.5 lg:px-3">
        <NavLink to="/settings" aria-current={isActive("/settings") ? "page" : undefined} className={navClass(isActive("/settings"))}>
          <Icon name="settings" className="h-4 w-4 shrink-0" />
          <span className="hidden lg:inline">Settings</span>
        </NavLink>
      </div>
    </aside>
  );
}

function MobileBar() {
  const items = [...NAV, { to: "/settings", label: "Settings", icon: "settings" }];
  const isActive = useActiveNav();
  return (
    <nav
      className="fixed inset-x-0 bottom-0 z-20 grid grid-cols-7 border-t border-border-mid/30 bg-base/95 backdrop-blur sm:hidden"
      aria-label="Primary"
    >
      {items.map((item) => (
        <NavLink
          key={item.to}
          to={item.to}
          aria-current={isActive(item.to) ? "page" : undefined}
          className={isActive(item.to) ? "text-primary" : "text-muted"}
        >
          <span className="flex flex-col items-center gap-0.5 py-2 text-[10px]">
            <Icon name={item.icon} className="h-4 w-4" />
            {item.label}
          </span>
        </NavLink>
      ))}
    </nav>
  );
}

function TopBar() {
  const { status, connected, demo, refresh } = useChrono();
  return (
    <header className="sticky top-0 z-10 flex h-16 items-center justify-between gap-4 border-b border-border-mid/30 bg-base/80 px-4 backdrop-blur sm:px-6">
      <div className="lg:hidden">
        <Logo />
      </div>
      <div className="hidden items-center gap-1.5 text-sm text-muted lg:flex">
        <span className="num">{status?.region || "ap-south-1"}</span>
        <span className="text-border-mid/60">·</span>
        <span className="num truncate">{status?.run_id || "run-local-dev"}</span>
      </div>
      <div className="flex items-center gap-3">
        {demo && <DemoBadge />}
        <button
          type="button"
          onClick={refresh}
          className="grid h-8 w-8 place-items-center rounded-sm text-muted transition-colors hover:bg-surface hover:text-primary"
          aria-label="Refresh now"
        >
          <Icon name="refresh" className="h-4 w-4" />
        </button>
        <ConnectionDot connected={connected} />
      </div>
    </header>
  );
}

export function AppLayout() {
  const { connected } = useChrono();
  return (
    <div className="min-h-screen bg-base">
      <Sidebar />
      <MobileBar />
      <div className="flex min-h-screen flex-col bg-base sm:pl-20 lg:pl-60">
        <TopBar />
        {!connected && <OfflineBanner />}
        <main className="mx-auto w-full max-w-6xl flex-1 px-4 pt-6 pb-24 sm:px-6 sm:pb-8 lg:px-8">
          <Outlet />
        </main>
      </div>
    </div>
  );
}

export function PageHead({ title, sub, aside }) {
  return (
    <div className="mb-6 flex flex-wrap items-start justify-between gap-4">
      <div className="min-w-0">
        <h1 className="text-2xl font-semibold tracking-tight text-primary">{title}</h1>
        {sub ? <p className="mt-1 text-sm text-muted">{sub}</p> : null}
      </div>
      {aside ? <div className="shrink-0">{aside}</div> : null}
    </div>
  );
}