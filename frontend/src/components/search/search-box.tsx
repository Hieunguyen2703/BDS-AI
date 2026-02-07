"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { Search, Loader2, Sparkles } from "lucide-react";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

interface SearchBoxProps {
  className?: string;
  placeholder?: string;
  defaultValue?: string;
  onSearch?: (query: string) => void;
  onReset?: () => void;
  size?: "default" | "lg";
  showAIBadge?: boolean;
}

export function SearchBox({
  className,
  placeholder = "Tìm kiếm bất động sản...",
  defaultValue = "",
  onSearch,
  onReset,
  size = "default",
  showAIBadge = true,
}: SearchBoxProps) {
  const [query, setQuery] = useState(defaultValue);
  const [isLoading, setIsLoading] = useState(false);
  const router = useRouter();

  // Reset local state when defaultValue changes (e.g. parent reset)
  if (defaultValue !== query && defaultValue === "") {
    // setQuery(""); // This causes infinite loop if not careful, handled by parent key or effect usually.
    // Better: Parent passes key to force re-mount if strictly needed, or we expose a reset handler.
    // For now, let's trust onReset handles parent state, and we handle local.
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();

    // Allow empty query to support filter-only search
    const effectiveQuery = query.trim();

    setIsLoading(true);

    if (onSearch) {
      await onSearch(effectiveQuery);
      setIsLoading(false);
    } else {
      router.push(`/search?q=${encodeURIComponent(effectiveQuery)}`);
    }
  };

  const handleReset = () => {
    setQuery("");
    if (onReset) onReset();
  };

  return (
    <div className={cn("w-full", className)}>
      <form onSubmit={handleSubmit} className="relative">
        <div className="relative">
          <Search className={cn(
            "absolute left-3 top-1/2 -translate-y-1/2 text-muted-foreground",
            size === "lg" ? "h-5 w-5" : "h-4 w-4"
          )} />
          <Input
            type="text"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder={placeholder}
            className={cn(
              "pl-10 pr-32", // Increased padding right to accommodate buttons
              size === "lg" && "h-14 text-lg"
            )}
          />

          {/* Controls Container */}
          <div className="absolute right-1 top-1/2 -translate-y-1/2 flex items-center gap-1">
            {/* AI Badge */}
            {showAIBadge && (
              <div className="hidden sm:flex items-center gap-1 text-xs text-muted-foreground mr-2">
                <Sparkles className="h-3 w-3" />
                <span>AI</span>
              </div>
            )}

            {/* Reset Button */}
            {onReset && (
              <Button
                type="button"
                variant="ghost"
                size="icon"
                className="h-8 w-8 hover:bg-transparent text-muted-foreground hover:text-foreground"
                onClick={handleReset}
                title="Xóa tìm kiếm"
              >
                <span className="sr-only">Reset</span>
                <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="lucide lucide-x"><path d="M18 6 6 18" /><path d="m6 6 12 12" /></svg>
              </Button>
            )}

            <Button
              type="submit"
              disabled={isLoading}
              className={cn(
                size === "lg" && "h-12"
              )}
            >
              {isLoading ? (
                <Loader2 className="h-4 w-4 animate-spin" />
              ) : (
                "Tìm kiếm"
              )}
            </Button>
          </div>
        </div>
      </form>
    </div>
  );
}
