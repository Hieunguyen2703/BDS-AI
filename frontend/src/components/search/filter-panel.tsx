"use client";

import { useQuery } from "@tanstack/react-query";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { getDistricts } from "@/lib/api";
import { X, Filter } from "lucide-react";

interface FilterState {
  district?: string;
  property_type?: string;
  price_min?: string;
  price_max?: string;
  area_min?: string;
  area_max?: string;
}

interface FilterPanelProps {
  filters: FilterState;
  onChange: (filters: FilterState) => void;
  onReset: () => void;
}

export const PROPERTY_TYPES = [
  { value: "chung-cu", label: "Căn hộ chung cư" },
  { value: "nha-rieng", label: "Nhà riêng" },
  { value: "biet-thu", label: "Biệt thự / Liền kề" },
  { value: "nha-mat-pho", label: "Nhà mặt phố" },
  { value: "shophouse", label: "Shophouse / Nhà phố thương mại" },
  { value: "dat-nen", label: "Đất nền dự án" },
  { value: "dat", label: "Đất" },
  { value: "trang-trai", label: "Trang trại / Khu nghỉ dưỡng" },
  { value: "condotel", label: "Condotel" },
  { value: "kho-xuong", label: "Kho / Nhà xưởng" },
];

const PRICE_OPTIONS = [
  { value: "500000000", label: "500 triệu" },
  { value: "1000000000", label: "1 tỷ" },
  { value: "2000000000", label: "2 tỷ" },
  { value: "3000000000", label: "3 tỷ" },
  { value: "5000000000", label: "5 tỷ" },
  { value: "10000000000", label: "10 tỷ" },
  { value: "20000000000", label: "20 tỷ" },
];

export function FilterPanel({ filters, onChange, onReset }: FilterPanelProps) {
  const { data: districtsData } = useQuery({
    queryKey: ["districts"],
    queryFn: getDistricts,
  });

  const districts = districtsData?.districts || [];

  const updateFilter = (key: keyof FilterState, value: string | undefined) => {
    onChange({ ...filters, [key]: value === "all" ? undefined : value });
  };

  const hasFilters = Object.values(filters).some((v) => v);

  return (
    <div className="space-y-4 p-6 border border-white/5 rounded-xl bg-slate-900/50 backdrop-blur-md shadow-xl">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2 font-medium">
          <Filter className="h-4 w-4" />
          Bộ lọc
        </div>
        {hasFilters && (
          <Button variant="ghost" size="sm" onClick={onReset}>
            <X className="h-4 w-4 mr-1" />
            Xóa lọc
          </Button>
        )}
      </div>

      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {/* District */}
        <div className="space-y-2">
          <Label>Quận/Huyện</Label>
          <Select
            value={filters.district || "all"}
            onValueChange={(v) => updateFilter("district", v)}
          >
            <SelectTrigger>
              <SelectValue placeholder="Tất cả" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">Tất cả</SelectItem>
              {districts.map((d) => (
                <SelectItem key={d.name} value={d.name}>
                  {d.name}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>

        {/* Property Type */}
        <div className="space-y-2">
          <Label>Loại BĐS</Label>
          <Select
            value={filters.property_type || "all"}
            onValueChange={(v) => updateFilter("property_type", v)}
          >
            <SelectTrigger>
              <SelectValue placeholder="Tất cả" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">Tất cả</SelectItem>
              {PROPERTY_TYPES.map((t) => (
                <SelectItem key={t.value} value={t.value}>
                  {t.label}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>

        {/* Price Range */}
        <div className="space-y-2">
          <Label>Giá từ</Label>
          <Select
            value={filters.price_min || "all"}
            onValueChange={(v) => updateFilter("price_min", v)}
          >
            <SelectTrigger>
              <SelectValue placeholder="Không giới hạn" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">Không giới hạn</SelectItem>
              {PRICE_OPTIONS.map((p) => (
                <SelectItem key={p.value} value={p.value}>
                  {p.label}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>

        <div className="space-y-2">
          <Label>Giá đến</Label>
          <Select
            value={filters.price_max || "all"}
            onValueChange={(v) => updateFilter("price_max", v)}
          >
            <SelectTrigger>
              <SelectValue placeholder="Không giới hạn" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">Không giới hạn</SelectItem>
              {PRICE_OPTIONS.map((p) => (
                <SelectItem key={p.value} value={p.value}>
                  {p.label}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>

        {/* Area Range */}
        <div className="space-y-2">
          <Label>Diện tích từ (m²)</Label>
          <Input
            type="number"
            placeholder="0"
            value={filters.area_min || ""}
            onChange={(e) => updateFilter("area_min", e.target.value || undefined)}
          />
        </div>

        <div className="space-y-2">
          <Label>Diện tích đến (m²)</Label>
          <Input
            type="number"
            placeholder="Không giới hạn"
            value={filters.area_max || ""}
            onChange={(e) => updateFilter("area_max", e.target.value || undefined)}
          />
        </div>
      </div>
    </div>
  );
}
