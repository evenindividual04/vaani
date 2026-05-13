"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useCallStore } from "@/store/callStore";
import { useCallWebSocket } from "@/hooks/useCallWebSocket";
import { Activity, Clock, BarChart2, FileText, CheckSquare } from "lucide-react";

// ── Logo ──────────────────────────────────────────────────────────────────────

function VaaniLogo() {
  return (
    <div className="flex items-center gap-2.5">
      <div className="relative w-8 h-8 flex-shrink-0">
        <svg viewBox="0 0 32 32" fill="none" xmlns="http://www.w3.org/2000/svg" className="w-8 h-8">
          <rect width="32" height="32" rx="6" fill="#1C1C1C" />
          <rect width="32" height="32" rx="6" stroke="#3E3E3E" strokeWidth="1" />
          {/* Minimalist bars */}
          <rect x="8"  y="14" width="2" height="4"  rx="1" fill="#A1A1AA"/>
          <rect x="12" y="10" width="2" height="12" rx="1" fill="#FAFAFA"/>
          <rect x="16" y="6"  width="2" height="20" rx="1" fill="#FAFAFA"/>
          <rect x="20" y="10" width="2" height="12" rx="1" fill="#FAFAFA"/>
          <rect x="24" y="14" width="2" height="4"  rx="1" fill="#A1A1AA"/>
        </svg>
      </div>
      <div>
        <div className="text-[13px] font-semibold tracking-tight text-[#FAFAFA]" style={{ fontFamily: "Inter, sans-serif" }}>
          Vaani
        </div>
        <div className="text-[9px] tracking-widest text-[#71717A] uppercase font-mono">FNOL OPS</div>
      </div>
    </div>
  );
}

// ── Nav Item ──────────────────────────────────────────────────────────────────

interface NavItemProps {
  href: string;
  label: string;
  icon: React.ReactNode;
  badge?: number | null;
  isActive: boolean;
}

function NavItem({ href, label, icon, badge, isActive }: NavItemProps) {
  return (
    <Link
      href={href}
      className={`relative flex items-center gap-3 px-3 py-2 rounded-md text-sm transition-all duration-150 ${
        isActive ? "bg-[#1C1C1C] text-[#FAFAFA]" : "text-[#A1A1AA] hover:bg-[#161616] hover:text-[#FAFAFA]"
      }`}
    >
      {/* Active left bar */}
      {isActive && (
        <div className="absolute left-0 top-1/2 -translate-y-1/2 w-[2px] h-4 bg-[#FAFAFA] rounded-r-full" />
      )}

      <span className="opacity-80">
        {icon}
      </span>

      <span className="font-medium text-[13px] flex-1">
        {label}
      </span>

      {badge != null && badge > 0 && (
        <span className="text-[10px] font-mono font-medium px-1.5 py-0.5 rounded bg-[#2A2A2A] text-[#FAFAFA] min-w-[20px] text-center">
          {badge}
        </span>
      )}
    </Link>
  );
}

// ── Sidebar ───────────────────────────────────────────────────────────────────

export function Sidebar() {
  const pathname = usePathname();
  const { isConnected } = useCallWebSocket();
  const liveCalls = useCallStore((s) => s.liveCalls);
  const liveCount = Object.keys(liveCalls).length;

  const navItems = [
    { href: "/",        label: "Live Calls",   icon: <Activity size={16} />, badge: liveCount },
    { href: "/calls",   label: "Call History", icon: <Clock size={16} /> },
    { href: "/metrics", label: "Metrics",      icon: <BarChart2 size={16} /> },
    { href: "/prompts", label: "Prompts",       icon: <FileText size={16} /> },
    { href: "/eval",    label: "Eval Suite",   icon: <CheckSquare size={16} /> },
  ];

  return (
    <aside
      className="flex flex-col shrink-0 bg-[#0A0A0A] border-r border-[#2A2A2A]"
      style={{ width: 220 }}
    >
      {/* Logo */}
      <div className="px-4 py-5 border-b border-[#2A2A2A]">
        <VaaniLogo />
      </div>

      {/* Nav */}
      <nav className="flex-1 px-3 py-4 space-y-1 overflow-y-auto">
        <div className="text-[10px] font-medium text-[#52525B] mb-2 px-1">
          Menu
        </div>
        {navItems.map((item) => (
          <NavItem
            key={item.href}
            href={item.href}
            label={item.label}
            icon={item.icon}
            badge={item.badge}
            isActive={
              item.href === "/"
                ? pathname === "/"
                : pathname.startsWith(item.href)
            }
          />
        ))}
      </nav>

      {/* Footer */}
      <div className="px-4 py-3 space-y-2.5 border-t border-[#2A2A2A]">
        {/* Connection status */}
        <div className="flex items-center gap-2">
          <div
            className="w-1.5 h-1.5 rounded-full"
            style={{ background: isConnected ? "#34D399" : "#F87171" }}
          />
          <span
            className="text-[11px] font-medium"
            style={{ color: isConnected ? "#A1A1AA" : "#F87171" }}
          >
            {isConnected ? "Connected" : "Disconnected"}
          </span>
        </div>

        {/* Version */}
        <div className="text-[10px] text-[#52525B]">
          v1.0.0
        </div>
      </div>
    </aside>
  );
}
