import { type ClassValue, clsx } from "clsx";
import { twMerge } from "tailwind-merge";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

/**
 * Format price to Vietnamese format
 */
export function formatPrice(price: number | null | undefined): string {
  if (!price) return "Thỏa thuận";

  if (price >= 1_000_000_000) {
    const ty = price / 1_000_000_000;
    return `${ty.toFixed(ty % 1 === 0 ? 0 : 1)} tỷ`;
  }

  if (price >= 1_000_000) {
    const trieu = price / 1_000_000;
    return `${trieu.toFixed(trieu % 1 === 0 ? 0 : 0)} triệu`;
  }

  return new Intl.NumberFormat("vi-VN").format(price) + " đ";
}

/**
 * Format price per m2
 */
export function formatPricePerM2(price: number | null | undefined): string {
  if (!price) return "N/A";

  const trieu = price / 1_000_000;
  return `${trieu.toFixed(1)} tr/m²`;
}

/**
 * Format area
 */
export function formatArea(area: number | null | undefined): string {
  if (!area) return "N/A";
  return `${area.toFixed(0)}m²`;
}

/**
 * Format date relative
 */
export function formatRelativeDate(dateStr: string | null | undefined): string {
  if (!dateStr) return "";

  const date = new Date(dateStr);
  const now = new Date();
  const diffMs = now.getTime() - date.getTime();
  const diffDays = Math.floor(diffMs / (1000 * 60 * 60 * 24));

  if (diffDays === 0) return "Hôm nay";
  if (diffDays === 1) return "Hôm qua";
  if (diffDays < 7) return `${diffDays} ngày trước`;
  if (diffDays < 30) return `${Math.floor(diffDays / 7)} tuần trước`;
  if (diffDays < 365) return `${Math.floor(diffDays / 30)} tháng trước`;

  return `${Math.floor(diffDays / 365)} năm trước`;
}

/**
 * Truncate text
 */
export function truncate(text: string | null | undefined, length: number): string {
  if (!text) return "";
  if (text.length <= length) return text;
  return text.slice(0, length) + "...";
}

/**
 * Get property type display name
 */
export function getPropertyTypeLabel(type: string | null | undefined): string {
  const types: Record<string, string> = {
    "nha-rieng": "Nhà riêng",
    "chung-cu": "Chung cư",
    "dat": "Đất nền",
    "biet-thu": "Biệt thự",
    "nha-pho": "Nhà phố",
    "shop-house": "Shophouse",
    "penthouse": "Penthouse",
  };

  return type ? types[type] || type : "Khác";
}

/**
 * Get platform badge color
 */
export function getPlatformColor(platform: string | null | undefined): string {
  const colors: Record<string, string> = {
    chotot: "bg-orange-100 text-orange-800",
    batdongsan: "bg-blue-100 text-blue-800",
    mogi: "bg-green-100 text-green-800",
    nhadat24h: "bg-purple-100 text-purple-800",
    google: "bg-red-100 text-red-800",
  };

  return platform ? colors[platform] || "bg-gray-100 text-gray-800" : "bg-gray-100 text-gray-800";
}
