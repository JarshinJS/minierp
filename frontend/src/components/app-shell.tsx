"use client";

import clsx from "clsx";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect, useRef, useState, type ReactNode } from "react";
import { useQuery } from "@tanstack/react-query";
import { api, unwrap } from "@/lib/api/client";
import { lastAccountBlockCode, useLogout, useMe, type CurrentUser } from "@/lib/auth";
import { Bell, ChevronDown, Layers, LogOut, Menu, X } from "@/lib/icons";
import { itemPrefix, visibleNav, type NavLink } from "@/lib/nav";
import { Spinner } from "./ui";

/** Link that uses client-side navigation for Next.js pages and a full load for Django pages. */
function SmartLink({ link, className, children, onClick }: {
  link: NavLink; className?: string; children: ReactNode; onClick?: () => void;
}) {
  return link.next
    ? <Link href={link.href} className={className} onClick={onClick}>{children}</Link>
    : <a href={link.href} className={className}>{children}</a>;
}

function initials(name: string) {
  const parts = name.split(/\s+/).filter(Boolean);
  if (!parts.length) return "?";
  return (parts.length === 1 ? parts[0]!.slice(0, 2) : parts[0]![0]! + parts.at(-1)![0]!).toUpperCase();
}

function Sidebar({ user, onNavigate }: { user: CurrentUser; onNavigate?: () => void }) {
  const pathname = usePathname();
  const sections = visibleNav(user.modules, user.role);
  return (
    <nav className="flex h-full flex-col bg-navy-900">
      <div className="flex h-16 shrink-0 items-center gap-3 border-b border-white/5 px-5">
        <span className="flex h-8 w-8 items-center justify-center rounded-lg bg-brand-600 text-white"><Layers className="h-4.5 w-4.5" /></span>
        <div className="leading-tight">
          <p className="text-sm font-semibold text-white">MiniERP</p>
          <p className="text-2xs text-slate-400">Shiv Furniture Works</p>
        </div>
      </div>
      <div className="scrollbar-thin flex-1 overflow-y-auto px-3 pb-6">
        {sections.map((section) => (
          <div key={section.title}>
            <p className="nav-section">{section.title}</p>
            <ul className="space-y-0.5">
              {section.items.map((item) => {
                const active = pathname.startsWith(itemPrefix(item));
                const Icon = item.icon;
                return (
                  <li key={item.module}>
                    <SmartLink link={item} onClick={onNavigate} className={clsx("nav-item", active && "nav-item-active")}>
                      <Icon /> <span className="truncate">{item.label}</span>
                    </SmartLink>
                    {active && item.children && item.children.length > 0 && (
                      <ul className="mt-0.5 space-y-0.5">
                        {item.children.map((child) => (
                          <li key={child.href}>
                            <SmartLink link={child} onClick={onNavigate}
                              className={clsx("nav-sub", pathname.startsWith(child.href) && "nav-sub-active")}>
                              {child.label}
                            </SmartLink>
                          </li>
                        ))}
                      </ul>
                    )}
                  </li>
                );
              })}
            </ul>
          </div>
        ))}
      </div>
    </nav>
  );
}

function useClickOutside(open: boolean, close: () => void) {
  const ref = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (!open) return;
    const onDown = (e: MouseEvent) => ref.current && !ref.current.contains(e.target as Node) && close();
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && close();
    document.addEventListener("mousedown", onDown);
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("mousedown", onDown);
      document.removeEventListener("keydown", onKey);
    };
  }, [open, close]);
  return ref;
}

const ALERT_LINKS: Record<string, string> = {
  low_stock: "/inventory/?stock=low_stock",
  pending_deliveries: "/delivery/",
  delayed_manufacturing: "/manufacturing/orders/",
  pending_procurement: "/procurement/trigger-dashboard/",
};
const TONE_DOT: Record<string, string> = { amber: "bg-amber-500", blue: "bg-sky-500", red: "bg-red-500" };

function AlertsMenu() {
  const [open, setOpen] = useState(false);
  const ref = useClickOutside(open, () => setOpen(false));
  const { data } = useQuery({
    queryKey: ["dashboard", "alerts"],
    queryFn: () => unwrap(api.GET("/api/dashboard/alerts/")),
    refetchInterval: 60_000,
  });
  const total = data?.total ?? 0;
  return (
    <div className="relative" ref={ref}>
      {/* Name comes from content ("Alerts 4"), so it always includes the visible count. */}
      <button className="btn btn-ghost btn-icon relative" onClick={() => setOpen((o) => !o)} aria-expanded={open}>
        <Bell aria-hidden="true" />
        <span className="sr-only">Alerts</span>
        {total > 0 && (
          <span className="absolute top-1 right-1 flex h-4 min-w-4 items-center justify-center rounded-full bg-red-600 px-1 text-[10px] font-semibold text-white">
            {total > 99 ? "99+" : total}
          </span>
        )}
      </button>
      {open && (
        <div className="dropdown-menu right-0 w-72">
          <p className="px-2.5 py-2 text-xs font-semibold text-slate-500">Operational alerts</p>
          {!data?.items.length && <p className="px-2.5 pb-3 text-sm text-slate-500">All clear. Nothing needs attention.</p>}
          {data?.items.map((item) => {
            const content = (
              <>
                <span className={clsx("h-2 w-2 shrink-0 rounded-full", TONE_DOT[item.tone] ?? "bg-slate-400")} />
                <span className="flex-1">{item.label}</span>
                <span className="font-semibold tabular-nums">{item.count}</span>
              </>
            );
            const href = ALERT_LINKS[item.key];
            return item.can_open && href
              ? <a key={item.key} href={href} className="dropdown-item">{content}</a>
              : <div key={item.key} className="dropdown-item cursor-default hover:bg-transparent">{content}</div>;
          })}
        </div>
      )}
    </div>
  );
}

function UserMenu({ user }: { user: CurrentUser }) {
  const [open, setOpen] = useState(false);
  const ref = useClickOutside(open, () => setOpen(false));
  const logout = useLogout();
  return (
    <div className="relative" ref={ref}>
      <button className="flex items-center gap-2.5 rounded-lg px-2 py-1.5 hover:bg-slate-100" onClick={() => setOpen((o) => !o)} aria-expanded={open}>
        <span className="flex h-8 w-8 items-center justify-center rounded-full bg-brand-100 text-xs font-semibold text-brand-700">
          {initials(user.full_name)}
        </span>
        <span className="hidden text-left leading-tight sm:block">
          <span className="block text-sm font-medium text-slate-900">{user.full_name}</span>
          <span className="block text-xs text-slate-500">{user.role_display}</span>
        </span>
        <ChevronDown className="hidden h-4 w-4 text-slate-400 sm:block" />
      </button>
      {open && (
        <div className="dropdown-menu right-0">
          <div className="px-2.5 py-2">
            <p className="truncate text-sm font-medium text-slate-900">{user.full_name}</p>
            <p className="truncate text-xs text-slate-500">{user.email}</p>
          </div>
          <div className="my-1 h-px bg-slate-100" />
          <button className="dropdown-item" onClick={() => logout.mutate()} disabled={logout.isPending}>
            <LogOut /> Sign out
          </button>
        </div>
      )}
    </div>
  );
}

export function AppShell({ children }: { children: ReactNode }) {
  const { data: user, isPending, error } = useMe();
  const router = useRouter();
  const pathname = usePathname();
  const [drawer, setDrawer] = useState(false);

  useEffect(() => {
    if (!isPending && user === null) {
      // A session ended because the account is pending/suspended/... → say why.
      const status = lastAccountBlockCode();
      // Keep the query string too, so filtered deep links (e.g. ?tab=ledger) survive login.
      const here = `${pathname}${window.location.search}`;
      router.replace(`/login/?next=${encodeURIComponent(here)}${status ? `&status=${status}` : ""}`);
    }
  }, [isPending, user, router, pathname]);

  if (error) {
    return <div className="p-8"><p className="text-sm text-red-700">Could not reach the server. Please refresh the page.</p></div>;
  }
  if (!user) {
    return <div className="flex min-h-screen items-center justify-center text-brand-600"><Spinner className="h-6 w-6" /></div>;
  }

  return (
    <div className="min-h-screen">
      {/* Desktop sidebar */}
      <aside className="fixed inset-y-0 left-0 z-40 hidden w-64 lg:block"><Sidebar user={user} /></aside>
      {/* Mobile drawer */}
      {drawer && (
        <div className="fixed inset-0 z-50 lg:hidden">
          <div className="absolute inset-0 bg-slate-900/50" onClick={() => setDrawer(false)} />
          <aside className="absolute inset-y-0 left-0 w-72 max-w-[85vw]">
            <button className="absolute top-4 right-3 z-10 rounded-md p-1 text-slate-400 hover:text-white" onClick={() => setDrawer(false)} aria-label="Close menu">
              <X className="h-5 w-5" />
            </button>
            <Sidebar user={user} onNavigate={() => setDrawer(false)} />
          </aside>
        </div>
      )}
      <div className="lg:pl-64">
        <header className="sticky top-0 z-30 flex h-16 items-center gap-3 border-b border-slate-200 bg-white/90 px-4 backdrop-blur sm:px-6">
          <button className="btn btn-ghost btn-icon lg:hidden" onClick={() => setDrawer(true)} aria-label="Open menu"><Menu /></button>
          <div className="flex-1" />
          <AlertsMenu />
          <UserMenu user={user} />
        </header>
        <main className="mx-auto max-w-7xl px-4 py-6 sm:px-6 lg:px-8">{children}</main>
      </div>
    </div>
  );
}
