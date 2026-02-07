"use client";

import { useState } from "react";
import { useQuery, keepPreviousData } from "@tanstack/react-query";
import { Loader2, AlertCircle, ChevronLeft, ChevronRight, Search, Sparkles } from "lucide-react";
import { Header, Footer } from "@/components/layout/header";
import { FilterPanel } from "@/components/search/filter-panel";
import { ListingCard, ListingCardSkeleton } from "@/components/listings/listing-card";
import { Button } from "@/components/ui/button";
import { getListings } from "@/lib/api";

export default function ListingsPage() {
  const [page, setPage] = useState(1);
  const [filters, setFilters] = useState<{
    district?: string;
    property_type?: string;
    price_min?: string;
    price_max?: string;
    area_min?: string;
    area_max?: string;
    status?: string;
  }>({});

  // State for the "pending" filters in the UI before clicking Apply
  const [pendingFilters, setPendingFilters] = useState(filters);

  const { data, isLoading, isError, error, refetch } = useQuery({
    queryKey: ["listings", page, filters], // Use 'filters' (active) for query key
    queryFn: () =>
      getListings({
        page,
        size: 20,
        district: filters.district,
        property_type: filters.property_type,
        ...filters,
      }),
    placeholderData: keepPreviousData,
  });

  const handleApplyFilters = () => {
    setFilters(pendingFilters);
    setPage(1);
  };

  const handleReset = () => {
    const empty = {};
    setPendingFilters(empty);
    setFilters(empty);
    setPage(1);
  };

  // Handle API response inconsistency (results vs items)
  const listings = (data as any)?.listings || (data as any)?.items || (data as any)?.results || [];
  const total = data?.total || 0;
  const totalPages = (data as any)?.pages || Math.ceil(total / 20) || 1;

  return (
    <div className="flex min-h-screen flex-col">
      <Header />
      <main className="flex-1 container py-8">
        <div className="flex flex-col md:flex-row items-center justify-between mb-8 gap-4">
          <div>
            <h1 className="text-3xl font-bold tracking-tight text-white">Tất cả tin đăng</h1>
            <p className="text-slate-400 mt-1">
              Danh sách toàn bộ {total ? total.toLocaleString() : "..."} tin bất động sản đã thu thập
            </p>
          </div>
          <div className="flex">
            <Button
              onClick={handleApplyFilters}
              className="bg-blue-600 hover:bg-blue-700 text-white min-w-[120px]"
            >
              <Search className="w-4 h-4 mr-2" />
              Tìm kiếm
            </Button>
          </div>
        </div>

        <div className="mb-8 p-4 bg-slate-900/50 rounded-xl border border-white/5">
          <h2 className="text-lg font-semibold text-white mb-4 flex items-center gap-2">
            <Sparkles className="h-4 w-4 text-yellow-400" />
            Bộ lọc tìm kiếm
          </h2>
          <FilterPanel
            filters={pendingFilters}
            onChange={setPendingFilters} // Valid: updates "pending" UI state
            onReset={handleReset}
          />
        </div>

        {isError && (
          <div className="rounded-lg bg-red-500/10 p-4 text-red-400 flex items-center gap-2 mb-6">
            <AlertCircle className="h-5 w-5" />
            <p>Không thể tải dữ liệu: {(error as Error).message}</p>
          </div>
        )}

        {isLoading ? (
          <div className="grid gap-6 md:grid-cols-2 lg:grid-cols-3">
            {[...Array(6)].map((_, i) => (
              <ListingCardSkeleton key={i} />
            ))}
          </div>
        ) : (
          <>
            {listings.length === 0 ? (
              <div className="text-center py-20 bg-white/5 rounded-xl border border-white/5">
                <p className="text-lg text-slate-400">Không tìm thấy tin đăng nào phù hợp.</p>
                <Button variant="link" onClick={handleReset} className="mt-2 text-blue-400">
                  Xóa bộ lọc
                </Button>
              </div>
            ) : (
              <div className="grid gap-6 md:grid-cols-2 lg:grid-cols-3 mb-8">
                {listings.map((listing: any) => (
                  <ListingCard key={listing.id} listing={listing} />
                ))}
              </div>
            )}

            {/* Pagination Controls */}
            {totalPages > 1 && (
              <div className="flex items-center justify-center gap-2 mt-8">
                <Button
                  variant="outline"
                  size="icon"
                  onClick={() => setPage((p) => Math.max(1, p - 1))}
                  disabled={page === 1}
                  className="bg-slate-900 border-slate-800 hover:bg-slate-800"
                >
                  <ChevronLeft className="h-4 w-4" />
                </Button>
                <div className="flex gap-1">
                  <span className="px-4 py-2 text-sm font-medium bg-slate-800 rounded-md text-white border border-slate-700">
                    Trang {page} / {totalPages}
                  </span>
                </div>
                <Button
                  variant="outline"
                  size="icon"
                  onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
                  disabled={page === totalPages}
                  className="bg-slate-900 border-slate-800 hover:bg-slate-800"
                >
                  <ChevronRight className="h-4 w-4" />
                </Button>
              </div>
            )}
          </>
        )}
      </main>
      <Footer />
    </div>
  );
}
