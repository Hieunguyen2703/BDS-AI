"use client";

import { useQuery } from "@tanstack/react-query";
import { BarChart3, Building, TrendingUp, Activity } from "lucide-react";
import { Header, Footer } from "@/components/layout/header";
import {
  DistrictChart,
  PlatformChart,
  PriceTrendChart,
  StatsCard,
} from "@/components/analytics/charts";
import { Skeleton } from "@/components/ui/skeleton";
import { getAnalytics, getPriceTrends } from "@/lib/api";

import { Suspense } from "react";
import { Loader2 } from "lucide-react";
import { useSearchParams } from "next/navigation";

function AnalyticsContent() {
  const searchParams = useSearchParams();
  const query = searchParams.get("query") || undefined;

  const { data: analytics, isLoading: analyticsLoading } = useQuery({
    queryKey: ["analytics", query],
    queryFn: () => getAnalytics(query),
  });

  const { data: trends } = useQuery({
    queryKey: ["price-trends", query],
    queryFn: () => getPriceTrends({ days: 30, district: query }), // Simple approximation for trends
  });

  return (
    <div className="flex min-h-screen flex-col">
      <Header />

      <main className="flex-1 container py-8">
        <div className="mb-8">
          <h1 className="text-3xl font-bold text-white">
            {query ? `Phân tích: "${query}"` : "Phân tích thị trường"}
          </h1>
          <p className="text-slate-400 mt-1">
            {query
              ? `Thống kê từ các tin đăng phù hợp với từ khóa "${query}"`
              : "Thống kê và xu hướng thị trường bất động sản Hà Nội"}
          </p>
        </div>

        {/* Stats Cards */}
        <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4 mb-8">
          {analyticsLoading ? (
            Array.from({ length: 4 }).map((_, i) => (
              <Skeleton key={i} className="h-32" />
            ))
          ) : (
            <>
              <StatsCard
                title="Tổng tin đăng"
                value={analytics?.total_listings?.toLocaleString() || "0"}
                description="Tất cả tin trong database"
                icon={<Building className="h-4 w-4 text-slate-500" />}
              />
              <StatsCard
                title="Tin đang hoạt động"
                value={analytics?.active_listings?.toLocaleString() || "0"}
                description="Tin còn hiệu lực"
                icon={<Activity className="h-4 w-4 text-slate-500" />}
              />
              <StatsCard
                title="Lượt scrape 7 ngày"
                value={analytics?.scrape_stats?.total_scrapes || "0"}
                description={`${analytics?.scrape_stats?.total_new_listings || 0} tin mới`}
                icon={<TrendingUp className="h-4 w-4 text-slate-500" />}
              />
              <StatsCard
                title="Nguồn dữ liệu"
                value={analytics?.platforms?.length || "0"}
                description="Nền tảng được thu thập"
                icon={<BarChart3 className="h-4 w-4 text-slate-500" />}
              />
            </>
          )}
        </div>

        {/* Charts */}
        <div className="grid gap-6 lg:grid-cols-2 mb-8">
          {analyticsLoading ? (
            <>
              <Skeleton className="h-[400px]" />
              <Skeleton className="h-[400px]" />
            </>
          ) : (
            <>
              <DistrictChart data={analytics?.districts || []} />
              <PlatformChart data={analytics?.platforms || []} />
            </>
          )}
        </div>

        {/* Price Trend */}
        {trends && (
          <div className="mb-8 p-6 bg-slate-900/50 rounded-xl border border-white/5">
            <PriceTrendChart data={trends.data} />
          </div>
        )}

        {/* Scrape Stats Table */}
        {analytics && (
          <div className="rounded-xl border border-white/5 bg-slate-900/50 p-6">
            <h3 className="text-lg font-semibold mb-4 text-white">Thống kê thu thập dữ liệu</h3>
            <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
              <div className="text-center p-4 rounded-lg bg-white/5">
                <div className="text-2xl font-bold text-blue-400">
                  {analytics?.scrape_stats?.total_scrapes || 0}
                </div>
                <div className="text-sm text-slate-500">Tổng lượt scrape</div>
              </div>
              <div className="text-center p-4 rounded-lg bg-white/5">
                <div className="text-2xl font-bold text-green-400">
                  {analytics?.scrape_stats?.successful_scrapes || 0}
                </div>
                <div className="text-sm text-slate-500">Thành công</div>
              </div>
              <div className="text-center p-4 rounded-lg bg-white/5">
                <div className="text-2xl font-bold text-blue-500">
                  {analytics?.scrape_stats?.total_listings_found?.toLocaleString() || 0}
                </div>
                <div className="text-sm text-slate-500">Tin tìm thấy</div>
              </div>
              <div className="text-center p-4 rounded-lg bg-white/5">
                <div className="text-2xl font-bold text-amber-500">
                  {(analytics?.scrape_stats?.avg_duration_seconds || 0).toFixed(1)}s
                </div>
                <div className="text-sm text-slate-500">Thời gian TB</div>
              </div>
            </div>
          </div>
        )}
      </main>

      <Footer />
    </div>
  );
}

export default function AnalyticsPage() {
  return (
    <Suspense fallback={<div className="flex min-h-screen items-center justify-center"><Loader2 className="h-8 w-8 animate-spin text-blue-500" /></div>}>
      <AnalyticsContent />
    </Suspense>
  );
}
