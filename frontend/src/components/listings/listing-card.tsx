"use client";

import Link from "next/link";
import {
  MapPin,
  Bed,
  Bath,
  Maximize,
  ExternalLink,
  Phone,
} from "lucide-react";
import { Card, CardContent, CardFooter, CardHeader } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  formatPrice,
  formatPricePerM2,
  formatArea,
  formatRelativeDate,
  getPropertyTypeLabel,
  getPlatformColor,
  truncate,
} from "@/lib/utils";
import type { Listing, SearchResultItem } from "@/lib/api";

interface ListingCardProps {
  listing: Listing | SearchResultItem;
  variant?: "default" | "compact";
}

export function ListingCard({ listing, variant = "default" }: ListingCardProps) {
  const isCompact = variant === "compact";
  // Cast to any to handle both Listing and SearchResultItem types
  const item = listing as any;

  return (
    <Card className="h-full hover:shadow-lg transition-shadow">
      <CardHeader className={isCompact ? "pb-2" : "pb-3"}>
        <div className="flex items-start justify-between gap-2">
          <div className="flex-1 min-w-0">
            <Link href={`/listings/${item.id}`}>
              <h3 className={`font-semibold hover:text-primary line-clamp-2 ${isCompact ? "text-sm" : "text-base"}`}>
                {item.title || "Không có tiêu đề"}
              </h3>
            </Link>
            <div className="flex items-center gap-1 text-muted-foreground mt-1">
              <MapPin className="h-3 w-3" />
              <span className="text-sm truncate">
                {typeof item.location === 'object' && item.location !== null
                  ? item.location.district || item.location.address || "Không xác định"
                  : item.district || item.address || "Không xác định"}
              </span>
            </div>
          </div>
          <Badge className={getPlatformColor(item.source_platform)}>
            {item.source_platform || "N/A"}
          </Badge>
        </div>
      </CardHeader>

      <CardContent className={isCompact ? "py-2" : "py-3"}>
        {/* Price */}
        <div className="mb-3">
          <div className="text-2xl font-bold text-primary">
            {(listing as any).price_text || formatPrice(item.price_number)}
          </div>
          {/* Handle both price_per_m2 (item) and calculated from price/area (SearchResultItem) */}
          {((listing as any).price_per_m2 || (item.price_number && item.area_m2 && item.price_number / item.area_m2)) && (
            <div className="text-sm text-muted-foreground">
              {formatPricePerM2((listing as any).price_per_m2 || (item.price_number! / item.area_m2!))}
            </div>
          )}
        </div>

        {/* Specs */}
        <div className="flex flex-wrap gap-3 text-sm text-muted-foreground">
          {item.area_m2 && (
            <div className="flex items-center gap-1">
              <Maximize className="h-4 w-4" />
              <span>{formatArea(item.area_m2)}</span>
            </div>
          )}
          {item.bedrooms && (
            <div className="flex items-center gap-1">
              <Bed className="h-4 w-4" />
              <span>{item.bedrooms} PN</span>
            </div>
          )}
          {(listing as any).bathrooms && (
            <div className="flex items-center gap-1">
              <Bath className="h-4 w-4" />
              <span>{(listing as any).bathrooms} WC</span>
            </div>
          )}
        </div>

        {/* Property type & Date */}
        <div className="flex items-center justify-between mt-3 text-sm">
          <Badge variant="secondary">
            {getPropertyTypeLabel(item.property_type)}
          </Badge>
          <span className="text-muted-foreground">
            {formatRelativeDate((listing as any).scraped_at || new Date().toISOString())}
          </span>
        </div>

        {/* Description */}
        {!isCompact && (listing as any).description && (
          <p className="mt-3 text-sm text-muted-foreground line-clamp-2">
            {truncate((listing as any).description, 150)}
          </p>
        )}
      </CardContent>

      <CardFooter className="pt-0 gap-2">
        {/* Handle both contact_phone (item) and contact.phone (SearchResultItem) */}
        {((listing as any).contact_phone || (typeof (listing as any).contact === 'object' && (listing as any).contact?.phone)) && (
          <Button variant="outline" size="sm" className="flex-1" asChild>
            <a href={`tel:${(listing as any).contact_phone || (listing as any).contact?.phone}`}>
              <Phone className="h-4 w-4 mr-1" />
              Liên hệ
            </a>
          </Button>
        )}
        {item.source_url && (
          <Button variant="outline" size="sm" asChild>
            <a href={item.source_url} target="_blank" rel="noopener noreferrer">
              <ExternalLink className="h-4 w-4" />
            </a>
          </Button>
        )}
        <Button size="sm" asChild className="flex-1">
          <Link href={`/listings/${item.id}`}>Chi tiết</Link>
        </Button>
      </CardFooter>
    </Card>
  );
}

export function ListingCardSkeleton() {
  return (
    <Card className="h-full">
      <CardHeader className="pb-3">
        <div className="flex items-start justify-between gap-2">
          <div className="flex-1 space-y-2">
            <div className="h-5 bg-muted rounded animate-pulse w-3/4" />
            <div className="h-4 bg-muted rounded animate-pulse w-1/2" />
          </div>
          <div className="h-5 w-16 bg-muted rounded animate-pulse" />
        </div>
      </CardHeader>
      <CardContent className="py-3">
        <div className="h-8 bg-muted rounded animate-pulse w-1/3 mb-3" />
        <div className="flex gap-3">
          <div className="h-4 bg-muted rounded animate-pulse w-16" />
          <div className="h-4 bg-muted rounded animate-pulse w-16" />
          <div className="h-4 bg-muted rounded animate-pulse w-16" />
        </div>
      </CardContent>
      <CardFooter className="pt-0 gap-2">
        <div className="h-9 bg-muted rounded animate-pulse flex-1" />
        <div className="h-9 bg-muted rounded animate-pulse flex-1" />
      </CardFooter>
    </Card>
  );
}
