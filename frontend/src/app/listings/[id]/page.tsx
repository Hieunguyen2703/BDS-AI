"use client";

import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import {
  ArrowLeft,
  MapPin,
  Bed,
  Bath,
  Maximize,
  Compass,
  Building,
  Phone,
  ExternalLink,
  Calendar,
  Share2,
} from "lucide-react";
import { Header, Footer } from "@/components/layout/header";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { ListingCard } from "@/components/listings/listing-card";
import { getListing, getSimilarListings } from "@/lib/api";
import {
  formatPrice,
  formatPricePerM2,
  formatArea,
  formatRelativeDate,
  getPropertyTypeLabel,
  getPlatformColor,
} from "@/lib/utils";

export default function ListingDetailPage({
  params,
}: {
  params: { id: string };  // Changed: Remove Promise wrapper
}) {
  const id = params.id;  // Direct access

  const { data: listing, isLoading } = useQuery({
    queryKey: ["listing", id],
    queryFn: () => getListing(id),
  });

  const { data: similarListings } = useQuery({
    queryKey: ["similar", id],
    queryFn: () => getSimilarListings(id, 4),
    enabled: !!listing,
  });

  if (isLoading) {
    return (
      <div className="flex min-h-screen flex-col">
        <Header />
        <main className="flex-1 container py-8">
          <Skeleton className="h-8 w-48 mb-6" />
          <div className="grid gap-6 lg:grid-cols-3">
            <div className="lg:col-span-2 space-y-6">
              <Skeleton className="h-64" />
              <Skeleton className="h-48" />
            </div>
            <Skeleton className="h-96" />
          </div>
        </main>
        <Footer />
      </div>
    );
  }

  if (!listing) {
    return (
      <div className="flex min-h-screen flex-col">
        <Header />
        <main className="flex-1 container py-8">
          <p className="text-center text-muted-foreground">
            Không tìm thấy tin đăng
          </p>
        </main>
        <Footer />
      </div>
    );
  }

  return (
    <div className="flex min-h-screen flex-col">
      <Header />

      <main className="flex-1 container py-8">
        {/* Back button */}
        <Button variant="ghost" className="mb-6" asChild>
          <Link href="/listings">
            <ArrowLeft className="h-4 w-4 mr-2" />
            Quay lại danh sách
          </Link>
        </Button>

        <div className="grid gap-6 lg:grid-cols-3">
          {/* Main Content */}
          <div className="lg:col-span-2 space-y-6">
            {/* Title & Meta */}
            <div>
              <div className="flex items-start justify-between gap-4">
                <h1 className="text-2xl font-bold">
                  {listing.title || "Không có tiêu đề"}
                </h1>
                <Badge className={getPlatformColor(listing.source_platform)}>
                  {listing.source_platform}
                </Badge>
              </div>
              <div className="flex items-center gap-2 mt-2 text-muted-foreground">
                <MapPin className="h-4 w-4" />
                <span>
                  {listing.address ||
                    [listing.ward, listing.district, listing.city]
                      .filter(Boolean)
                      .join(", ") ||
                    "Không xác định"}
                </span>
              </div>
            </div>

            {/* Price */}
            <Card>
              <CardContent className="pt-6">
                <div className="flex items-baseline gap-4">
                  <span className="text-3xl font-bold text-primary">
                    {formatPrice(listing.price_number)}
                  </span>
                  {listing.price_per_m2 && (
                    <span className="text-lg text-muted-foreground">
                      ({formatPricePerM2(listing.price_per_m2)})
                    </span>
                  )}
                </div>
              </CardContent>
            </Card>

            {/* Specs */}
            <Card>
              <CardHeader>
                <CardTitle>Thông tin chi tiết</CardTitle>
              </CardHeader>
              <CardContent>
                <div className="grid gap-4 sm:grid-cols-2">
                  {listing.area_m2 && (
                    <div className="flex items-center gap-3">
                      <Maximize className="h-5 w-5 text-muted-foreground" />
                      <div>
                        <div className="text-sm text-muted-foreground">
                          Diện tích
                        </div>
                        <div className="font-medium">
                          {formatArea(listing.area_m2)}
                        </div>
                      </div>
                    </div>
                  )}
                  {listing.bedrooms && (
                    <div className="flex items-center gap-3">
                      <Bed className="h-5 w-5 text-muted-foreground" />
                      <div>
                        <div className="text-sm text-muted-foreground">
                          Phòng ngủ
                        </div>
                        <div className="font-medium">{listing.bedrooms}</div>
                      </div>
                    </div>
                  )}
                  {listing.bathrooms && (
                    <div className="flex items-center gap-3">
                      <Bath className="h-5 w-5 text-muted-foreground" />
                      <div>
                        <div className="text-sm text-muted-foreground">
                          Phòng tắm
                        </div>
                        <div className="font-medium">{listing.bathrooms}</div>
                      </div>
                    </div>
                  )}
                  {listing.floors && (
                    <div className="flex items-center gap-3">
                      <Building className="h-5 w-5 text-muted-foreground" />
                      <div>
                        <div className="text-sm text-muted-foreground">
                          Số tầng
                        </div>
                        <div className="font-medium">{listing.floors}</div>
                      </div>
                    </div>
                  )}
                  {listing.direction && (
                    <div className="flex items-center gap-3">
                      <Compass className="h-5 w-5 text-muted-foreground" />
                      <div>
                        <div className="text-sm text-muted-foreground">
                          Hướng
                        </div>
                        <div className="font-medium">{listing.direction}</div>
                      </div>
                    </div>
                  )}
                  {listing.property_type && (
                    <div className="flex items-center gap-3">
                      <Building className="h-5 w-5 text-muted-foreground" />
                      <div>
                        <div className="text-sm text-muted-foreground">
                          Loại BĐS
                        </div>
                        <div className="font-medium">
                          {getPropertyTypeLabel(listing.property_type)}
                        </div>
                      </div>
                    </div>
                  )}
                </div>
              </CardContent>
            </Card>

            {/* Description */}
            {listing.description && (
              <Card>
                <CardHeader>
                  <CardTitle>Mô tả</CardTitle>
                </CardHeader>
                <CardContent>
                  <p className="whitespace-pre-wrap text-muted-foreground">
                    {listing.description}
                  </p>
                </CardContent>
              </Card>
            )}
          </div>

          {/* Sidebar */}
          <div className="space-y-6">
            {/* Contact Card */}
            <Card>
              <CardHeader>
                <CardTitle>Liên hệ</CardTitle>
              </CardHeader>
              <CardContent className="space-y-4">
                {listing.contact_name && (
                  <div>
                    <div className="text-sm text-muted-foreground">
                      Người đăng
                    </div>
                    <div className="font-medium">{listing.contact_name}</div>
                  </div>
                )}
                {listing.contact_phone && (
                  <Button className="w-full" asChild>
                    <a href={`tel:${listing.contact_phone}`}>
                      <Phone className="h-4 w-4 mr-2" />
                      {listing.contact_phone}
                    </a>
                  </Button>
                )}
                {listing.source_url && (
                  <Button variant="outline" className="w-full" asChild>
                    <a
                      href={listing.source_url}
                      target="_blank"
                      rel="noopener noreferrer"
                    >
                      <ExternalLink className="h-4 w-4 mr-2" />
                      Xem tin gốc
                    </a>
                  </Button>
                )}
                <Button variant="outline" className="w-full">
                  <Share2 className="h-4 w-4 mr-2" />
                  Chia sẻ
                </Button>
              </CardContent>
            </Card>

            {/* Meta Card */}
            <Card>
              <CardContent className="pt-6 space-y-2 text-sm">
                <div className="flex items-center justify-between">
                  <span className="text-muted-foreground">Ngày đăng</span>
                  <span>{formatRelativeDate(listing.scraped_at)}</span>
                </div>
                <div className="flex items-center justify-between">
                  <span className="text-muted-foreground">Cập nhật</span>
                  <span>{formatRelativeDate(listing.updated_at)}</span>
                </div>
                <div className="flex items-center justify-between">
                  <span className="text-muted-foreground">Trạng thái</span>
                  <Badge variant="secondary">{listing.status}</Badge>
                </div>
              </CardContent>
            </Card>
          </div>
        </div>

        {/* Similar Listings */}
        {similarListings && similarListings.length > 0 && (
          <div className="mt-12">
            <h2 className="text-xl font-bold mb-6">Tin tương tự</h2>
            <div className="grid gap-6 md:grid-cols-2 lg:grid-cols-4">
              {similarListings.map((l) => (
                <ListingCard key={l.id} listing={l} variant="compact" />
              ))}
            </div>
          </div>
        )}
      </main>

      <Footer />
    </div>
  );
}
