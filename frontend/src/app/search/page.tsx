"use client";

import { useSearchParams, useRouter } from "next/navigation";
import { useState, useEffect, Suspense } from "react";
import { useQuery } from "@tanstack/react-query";
import { Loader2, Search, Sparkles, Clock } from "lucide-react";
import { Header, Footer } from "@/components/layout/header";
import { SearchBox } from "@/components/search/search-box";
import { FilterPanel, PROPERTY_TYPES } from "@/components/search/filter-panel";
import { ListingCard, ListingCardSkeleton } from "@/components/listings/listing-card";
import { Button } from "@/components/ui/button";
import { searchListings, getSearchHistory, type SearchRequest } from "@/lib/api";
import { formatDistanceToNow } from "date-fns";
import { vi } from "date-fns/locale";


function SearchContent() {
  const searchParams = useSearchParams();
  const router = useRouter();
  const initialQuery = searchParams.get("q") || "";

  const [activeTab, setActiveTab] = useState<"search" | "history">("search");
  const [query, setQuery] = useState(initialQuery);

  /* Manual Search Trigger Logic: */
  const [filters, setFilters] = useState<{
    district?: string;
    property_type?: string;
    price_min?: string;
    price_max?: string;
    area_min?: string;
    area_max?: string;
  }>({});

  const [appliedFilters, setAppliedFilters] = useState(filters);

  // Track if search has been explicitly triggered by user or URL
  const [isSearchTriggered, setIsSearchTriggered] = useState(!!initialQuery);

  // Helper to build query from filters
  const buildQueryFromFilters = () => {
    if (query) return query; // User typed something -> Use it

    const parts = [];

    // 1. Property Type
    if (appliedFilters.property_type) {
      const pType = PROPERTY_TYPES.find(t => t.value === appliedFilters.property_type);
      if (pType) parts.push(pType.label);
    }

    // 2. District
    if (appliedFilters.district) {
      parts.push(appliedFilters.district);
    }

    // Join parts or fallback
    return parts.length > 0 ? parts.join(" ") : "Bất động sản";
  };

  const searchRequest: SearchRequest = {
    query: buildQueryFromFilters(),
    filters: {
      district: appliedFilters.district,
      property_type: appliedFilters.property_type,
      min_price: appliedFilters.price_min ? parseInt(appliedFilters.price_min) : undefined,
      max_price: appliedFilters.price_max ? parseInt(appliedFilters.price_max) : undefined,
      min_area: appliedFilters.area_min ? parseInt(appliedFilters.area_min) : undefined,
      max_area: appliedFilters.area_max ? parseInt(appliedFilters.area_max) : undefined,
    },
    max_results: 20,
    search_realtime: true,
  };

  const { data: searchResults, isLoading, isError, error } = useQuery({
    queryKey: ["search", searchRequest],
    queryFn: () => searchListings(searchRequest),
    enabled: isSearchTriggered && !!searchRequest.query, // Only search if triggered AND valid query
  });

  const { data: historyItems, isLoading: historyLoading } = useQuery({
    queryKey: ["searchHistory"],
    queryFn: () => getSearchHistory(50),
    enabled: activeTab === "history",
  });

  // Sync AI-inferred filters to UI AND Applied State
  useEffect(() => {
    if (searchResults?.applied_filters) {
      const af = searchResults.applied_filters;
      setFilters(prev => {
        const next = { ...prev };
        let changed = false;

        if (af.district && prev.district !== af.district) {
          next.district = af.district;
          changed = true;
        }
        if (af.property_type && prev.property_type !== af.property_type) {
          next.property_type = af.property_type;
          changed = true;
        }
        if (af.min_price && prev.price_min !== af.min_price.toString()) {
          next.price_min = af.min_price.toString();
          changed = true;
        }
        if (af.max_price && prev.price_max !== af.max_price.toString()) {
          next.price_max = af.max_price.toString();
          changed = true;
        }
        if (af.min_area && prev.area_min !== af.min_area.toString()) {
          next.area_min = af.min_area.toString();
          changed = true;
        }
        if (af.max_area && prev.area_max !== af.max_area.toString()) {
          next.area_max = af.max_area.toString();
          changed = true;
        }

        if (changed) {
          setAppliedFilters(next);
          return next;
        }
        return prev;
      });
    }
  }, [searchResults]);

  // Handle Search Trigger
  const handleSearch = (newQuery: string) => {
    setQuery(newQuery);
    setAppliedFilters(filters); // Commit pending UI filters to active search
    setIsSearchTriggered(true); // Trigger search
    setActiveTab("search"); // Switch to search tab if not already
  };

  const handleReset = () => {
    setQuery("");
    setFilters({
      property_type: undefined,
      price_min: undefined,
      price_max: undefined,
      area_min: undefined,
      area_max: undefined,
      district: undefined,
    });
    setAppliedFilters({});
    setIsSearchTriggered(false); // Reset search trigger
    // Optional: Refresh query to default state if needed, but empty state usually handles it
  };

  return (
    <div className="flex min-h-screen flex-col">
      <Header />

      <main className="flex-1 container py-8">
        <div className="max-w-7xl mx-auto mb-8">
          <div className="flex items-center gap-2 mb-2">
            <Search className="h-8 w-8 text-blue-500" />
            <h1 className="text-3xl font-bold text-white">Tìm kiếm thông minh</h1>
          </div>
          <p className="text-slate-400">Tìm kiếm bất động sản với AI và ngôn ngữ tự nhiên</p>

          {/* Tabs */}
          <div className="flex gap-2 mt-6 border-b border-white/10">
            <button
              onClick={() => setActiveTab("search")}
              className={`px-4 py-2 font-medium transition-colors ${activeTab === "search"
                ? "border-b-2 border-blue-500 text-blue-500"
                : "text-slate-400 hover:text-white"
                }`}
            >
              Tìm kiếm mới
            </button>
            <button
              onClick={() => setActiveTab("history")}
              className={`px-4 py-2 font-medium transition-colors ${activeTab === "history"
                ? "border-b-2 border-blue-500 text-blue-500"
                : "text-slate-400 hover:text-white"
                }`}
            >
              Lịch sử tìm kiếm
            </button>
          </div>
        </div>

        {activeTab === "search" ? (
          <>
            <div className="sticky top-16 z-30 bg-background/40 backdrop-blur-md py-4 -mx-4 px-4 md:static md:bg-transparent md:p-0">
              <div className="max-w-7xl mx-auto space-y-4">
                <SearchBox
                  defaultValue={query}
                  onSearch={handleSearch}
                  onReset={handleReset}
                  placeholder="Nhập yêu cầu tìm kiếm của bạn..."
                />
                <FilterPanel
                  filters={filters}
                  onChange={setFilters} // Valid: updates "pending" UI state
                  onReset={() =>
                    setFilters({
                      property_type: undefined,
                      price_min: undefined,
                      price_max: undefined,
                      area_min: undefined,
                      area_max: undefined,
                      district: undefined,
                    })
                  }
                />
              </div>
            </div>

            {/* Results Section */}
            <div className="mt-8">
              {isError && (
                <div className="rounded-lg bg-red-500/10 p-4 text-red-400 text-center">
                  <p>Đã xảy ra lỗi: {(error as Error).message}</p>
                </div>
              )}

              {isLoading && (
                <div className="flex flex-col items-center justify-center py-20">
                  <Loader2 className="h-10 w-10 animate-spin text-blue-500 mb-4" />
                  <p className="text-slate-400 animate-pulse">AI đang phân tích yêu cầu tìm kiếm...</p>
                </div>
              )}

              {/* Listings Grid */}
              {!isLoading && searchResults?.results && searchResults.results.length > 0 && (
                <div className="space-y-6">
                  <div className="flex items-center justify-between">
                    <h2 className="text-xl font-semibold text-white flex items-center gap-2">
                      <Sparkles className="h-5 w-5 text-yellow-400" />
                      Kết quả tìm kiếm
                    </h2>
                    <span className="text-sm text-slate-400">
                      Tìm thấy {searchResults.total} tin phù hợp ({searchResults.execution_time_ms}ms)
                    </span>
                  </div>

                  <div className="grid gap-6 md:grid-cols-2 lg:grid-cols-3">
                    {searchResults.results.map((listing: any) => (
                      <ListingCard key={listing.id} listing={listing} />
                    ))}
                  </div>
                </div>
              )}

              {/* Initial Empty State */}
              {!isSearchTriggered && !isLoading && !query && (
                <div className="flex flex-col items-center justify-center py-12 opacity-50">
                  <div className="bg-white/5 p-6 rounded-full mb-6 relative">
                    <Search className="h-10 w-10 text-blue-400" />
                    <Sparkles className="h-4 w-4 text-purple-400 absolute top-4 right-5 animate-pulse" />
                  </div>
                  <h3 className="text-xl font-medium text-slate-400">Nhập từ khóa để tìm kiếm</h3>
                  <p className="text-sm text-slate-600 mt-2">Hệ thống AI sẽ tự động phân tích và tìm kiếm</p>
                </div>
              )}

              {/* No Results State */}
              {isSearchTriggered && !isLoading && searchResults?.results?.length === 0 && (
                <div className="flex flex-col items-center justify-center py-20">
                  <div className="bg-white/5 p-6 rounded-full mb-4">
                    <Search className="h-8 w-8 text-slate-500" />
                  </div>
                  <h3 className="text-lg font-medium text-slate-300">Không tìm thấy kết quả nào</h3>
                  <p className="text-slate-500 mt-2">Hãy thử thay đổi từ khóa hoặc bộ lọc tìm kiếm</p>
                </div>
              )}
            </div>
          </>
        ) : (
          <div className="max-w-3xl mx-auto mt-8">
            {historyLoading ? (
              <div className="space-y-4">
                {[...Array(5)].map((_, i) => (
                  <div key={i} className="h-16 bg-white/5 rounded-xl animate-pulse" />
                ))}
              </div>
            ) : historyItems && historyItems.length > 0 ? (
              <div className="space-y-4">
                {historyItems.map((item: any) => (
                  <div
                    key={item.id}
                    className="group flex items-center justify-between p-4 rounded-xl bg-slate-900/50 border border-white/5 hover:border-blue-500/30 hover:bg-blue-500/5 transition-all"
                  >
                    <div className="flex items-center gap-4">
                      <div className="p-3 rounded-lg bg-white/5 group-hover:bg-blue-500/20 text-slate-400 group-hover:text-blue-400 transition-colors">
                        <Search className="h-5 w-5" />
                      </div>
                      <div>
                        <p className="font-medium text-lg text-slate-200 group-hover:text-blue-200 transition-colors">
                          {item.query || "Tìm kiếm không tên"}
                        </p>
                        <div className="flex items-center gap-3 text-sm text-slate-500 mt-1">
                          <span>
                            {formatDistanceToNow(new Date(item.created_at), { addSuffix: true, locale: vi })}
                          </span>
                          <span>•</span>
                          <span>{item.results_count} kết quả</span>
                        </div>
                      </div>
                    </div>
                    {/* User requested ONLY showing queries, not re-search. So no click handler on the whole row to simple set query. 
                               But leaving it non-interactive might feel broken. 
                               "lịch sử tìm kiếm o cần tìm kiếm lại chỉ cần hiện các query đã tìm kiếm thôi"
                               I will just display them. Maybe a copy button? Nah, just list is fine as requested.
                           */}
                  </div>
                ))}
              </div>
            ) : (
              <div className="text-center py-12 bg-white/5 rounded-xl border border-white/5">
                <Clock className="h-12 w-12 text-slate-600 mx-auto mb-4" />
                <p className="text-slate-400">Bạn chưa có lịch sử tìm kiếm nào.</p>
                <Button variant="link" onClick={() => setActiveTab("search")} className="mt-2 text-blue-400">
                  Bắt đầu tìm kiếm ngay
                </Button>
              </div>
            )}
          </div>
        )}
      </main>

      <Footer />
    </div>
  );
}

export default function SearchPage() {
  return (
    <Suspense fallback={<div className="flex min-h-screen items-center justify-center"><Loader2 className="h-8 w-8 animate-spin" /></div>}>
      <SearchContent />
    </Suspense>
  );
}
