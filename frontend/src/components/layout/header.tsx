"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  Home,
  Search,
  LayoutList,
  BarChart3,
  Settings,
  Menu,
  Calculator,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import { useState } from "react";

const navItems = [
  { href: "/", label: "Trang chủ", icon: Home },
  { href: "/listings", label: "Tin đăng", icon: LayoutList },
  { href: "/search", label: "Tìm kiếm", icon: Search },
  { href: "/valuation", label: "Định giá AI", icon: Calculator },
  { href: "/analytics", label: "Phân tích", icon: BarChart3 },
];

export function Header() {
  const pathname = usePathname();
  const [mobileOpen, setMobileOpen] = useState(false);

  return (
    <header className="sticky top-0 z-50 w-full border-b border-white/5 bg-slate-950/70 backdrop-blur-xl supports-[backdrop-filter]:bg-slate-950/40 shadow-sm transition-all duration-300">
      <div className="container flex h-16 items-center">
        {/* Logo */}
        <Link href="/" className="mr-8 flex items-center space-x-2 group">
          <div className="bg-gradient-to-br from-blue-500 to-purple-600 p-1.5 rounded-lg shadow-lg group-hover:shadow-blue-500/50 transition-all duration-300">
            <Home className="h-5 w-5 text-white" />
          </div>
          <span className="font-bold hidden sm:inline-block text-lg bg-clip-text text-transparent bg-gradient-to-r from-white to-slate-400 group-hover:to-white transition-all">BDS Agent</span>
        </Link>

        {/* Desktop Nav */}
        <nav className="hidden md:flex items-center gap-6">
          <Link
            href="/"
            className="text-sm font-medium transition-colors hover:text-primary"
          >
            Trang chủ
          </Link>
          <Link
            href="/listings"
            className="text-sm font-medium transition-colors hover:text-primary"
          >
            Tin đăng
          </Link>
          <Link
            href="/search"
            className="text-sm font-medium transition-colors hover:text-primary"
          >
            Tìm kiếm
          </Link>
          <Link
            href="/valuation"
            className="text-sm font-medium transition-colors hover:text-primary"
          >
            Định giá AI
          </Link>
          <Link
            href="/analytics"
            className="text-sm font-medium transition-colors hover:text-primary"
          >
            Phân tích
          </Link>
        </nav>
        {/* Spacer */}
        <div className="flex-1" />

        {/* Actions */}
        <div className="flex items-center gap-2">
          <Button variant="ghost" size="icon" asChild className="hidden md:flex">
            <Link href="/settings">
              <Settings className="h-5 w-5" />
            </Link>
          </Button>

          {/* Mobile menu button */}
          <Button
            variant="ghost"
            size="icon"
            className="md:hidden"
            onClick={() => setMobileOpen(!mobileOpen)}
          >
            <Menu className="h-5 w-5" />
          </Button>
        </div>
      </div>

      {/* Mobile Nav */}
      {mobileOpen && (
        <nav className="md:hidden border-t p-4 space-y-2">
          {navItems.map((item) => (
            <Link
              key={item.href}
              href={item.href}
              onClick={() => setMobileOpen(false)}
              className={cn(
                "flex items-center gap-3 px-3 py-2 rounded-md transition-colors",
                pathname === item.href
                  ? "bg-accent text-accent-foreground"
                  : "hover:bg-accent/50"
              )}
            >
              <item.icon className="h-5 w-5" />
              {item.label}
            </Link>
          ))}
        </nav>
      )}
    </header>
  );
}

export function Footer() {
  return (
    <footer className="border-t border-white/5 py-8 md:py-0 bg-slate-950">
      <div className="container flex flex-col items-center justify-between gap-4 md:h-14 md:flex-row">
        <p className="text-sm text-muted-foreground">
          © 2026 BDS Agent. Hệ thống tìm kiếm BĐS thông minh với AI.
        </p>
        <div className="flex items-center gap-4 text-sm text-muted-foreground">
          <Link href="/about" className="hover:text-foreground">
            Giới thiệu
          </Link>
          <Link href="/contact" className="hover:text-foreground">
            Liên hệ
          </Link>
          <Link href="/privacy" className="hover:text-foreground">
            Chính sách
          </Link>
        </div>
      </div>
    </footer>
  );
}
