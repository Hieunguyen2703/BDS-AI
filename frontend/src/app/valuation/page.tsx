"use client";

import { useState } from "react";
import { Calculator, TrendingUp, MapPin, Home, Loader2, History } from "lucide-react";
import { useQuery } from "@tanstack/react-query";
import { getValuationHistory } from "@/lib/api";
import { formatDistanceToNow } from "date-fns";
import { vi } from "date-fns/locale";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
    Select,
    SelectContent,
    SelectItem,
    SelectTrigger,
    SelectValue,
} from "@/components/ui/select";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Header, Footer } from "@/components/layout/header";

interface ValuationResult {
    price_min?: number;
    price_max?: number;
    price_suggested?: number;
    price_per_m2?: number;
    confidence?: number;
    reasoning?: string;
    market_comparison?: string;
    market_samples?: number;
    error?: string;
    ml_estimate?: number; // Raw ML value
}

export default function ValuationPage() {
    const [activeTab, setActiveTab] = useState<"estimate" | "history">("estimate");
    const [formData, setFormData] = useState({
        property_type: "chung_cu",
        area_m2: "",
        district: "",
        bedrooms: "",
        direction: "",
        legal_status: "",
    });

    const [result, setResult] = useState<ValuationResult | null>(null);
    const [loading, setLoading] = useState(false);

    const { data: historyItems, isLoading: historyLoading } = useQuery({
        queryKey: ["valuationHistory"],
        queryFn: () => getValuationHistory(),
        enabled: activeTab === "history",
    });

    const formatPrice = (price: number) => {
        if (price >= 1_000_000_000) {
            return `${(price / 1_000_000_000).toFixed(1)} tỷ`;
        }
        return `${(price / 1_000_000).toFixed(0)} triệu`;
    };

    const handleSubmit = async (e: React.FormEvent) => {
        e.preventDefault();
        setLoading(true);
        setResult(null);

        try {
            const response = await fetch("/api/v1/valuation/estimate", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    property_type: formData.property_type,
                    area_m2: parseFloat(formData.area_m2),
                    district: formData.district,
                    bedrooms: formData.bedrooms ? parseInt(formData.bedrooms) : null,
                    direction: formData.direction || null,
                    legal_status: formData.legal_status || null,
                }),
            });

            const data = await response.json();
            setResult(data);
        } catch (error) {
            console.error("Valuation error:", error);
            setResult({ error: "Có lỗi xảy ra. Vui lòng thử lại." });
        } finally {
            setLoading(false);
        }
    };

    return (
        <>
            <Header />
            <div className="container mx-auto py-8 px-4 max-w-6xl">
                <div className="mb-8">
                    <h1 className="text-3xl font-bold mb-2 flex items-center gap-2">
                        <Calculator className="h-8 w-8 text-primary" />
                        Định Giá BĐS Tự Động
                    </h1>
                    <p className="text-muted-foreground">
                        Sử dụng AI để phân tích thị trường và đưa ra mức giá hợp lý cho bất động sản của bạn
                    </p>



                    {/* Tab Navigation */}
                    <div className="flex gap-2 mt-6 border-b">
                        <button
                            onClick={() => setActiveTab("estimate")}
                            className={`px-4 py-2 font-medium transition-colors ${activeTab === "estimate"
                                ? "border-b-2 border-primary text-primary"
                                : "text-muted-foreground hover:text-foreground"
                                }`}
                        >
                            Định giá mới
                        </button>
                        <button
                            onClick={() => setActiveTab("history")}
                            className={`px-4 py-2 font-medium transition-colors ${activeTab === "history"
                                ? "border-b-2 border-primary text-primary"
                                : "text-muted-foreground hover:text-foreground"
                                }`}
                        >
                            Lịch sử định giá
                        </button>
                    </div>
                </div>

                {activeTab === "estimate" ? (
                    <div className="grid md:grid-cols-2 gap-6">
                        {/* Form */}
                        <Card>
                            <CardHeader>
                                <CardTitle>Thông Tin Bất Động Sản</CardTitle>
                                <CardDescription>Nhập thông tin để nhận định giá</CardDescription>
                            </CardHeader>
                            <CardContent>
                                <form onSubmit={handleSubmit} className="space-y-4">
                                    <div>
                                        <Label htmlFor="property_type">Loại BĐS *</Label>
                                        <Select
                                            value={formData.property_type}
                                            onValueChange={(value) =>
                                                setFormData({ ...formData, property_type: value })
                                            }
                                        >
                                            <SelectTrigger>
                                                <SelectValue />
                                            </SelectTrigger>
                                            <SelectContent>
                                                <SelectItem value="chung_cu">Chung cư</SelectItem>
                                                <SelectItem value="nha_rieng">Nhà riêng</SelectItem>
                                                <SelectItem value="nha_mat_pho">Nhà mặt phố</SelectItem>
                                                <SelectItem value="biet_thu">Biệt thự</SelectItem>
                                            </SelectContent>
                                        </Select>
                                    </div>

                                    <div>
                                        <Label htmlFor="area_m2">Diện tích (m²) *</Label>
                                        <Input
                                            id="area_m2"
                                            type="number"
                                            placeholder="VD: 80"
                                            value={formData.area_m2}
                                            onChange={(e) =>
                                                setFormData({ ...formData, area_m2: e.target.value })
                                            }
                                            required
                                        />
                                    </div>

                                    <div>
                                        <Label htmlFor="district">Quận/Huyện *</Label>
                                        <Input
                                            id="district"
                                            placeholder="VD: Cầu Giấy"
                                            value={formData.district}
                                            onChange={(e) =>
                                                setFormData({ ...formData, district: e.target.value })
                                            }
                                            required
                                        />
                                    </div>

                                    <div>
                                        <Label htmlFor="bedrooms">Số phòng ngủ</Label>
                                        <Input
                                            id="bedrooms"
                                            type="number"
                                            placeholder="VD: 2"
                                            value={formData.bedrooms}
                                            onChange={(e) =>
                                                setFormData({ ...formData, bedrooms: e.target.value })
                                            }
                                        />
                                    </div>

                                    <div>
                                        <Label htmlFor="direction">Hướng nhà</Label>
                                        <Select
                                            value={formData.direction}
                                            onValueChange={(value) =>
                                                setFormData({ ...formData, direction: value })
                                            }
                                        >
                                            <SelectTrigger>
                                                <SelectValue placeholder="Chọn hướng" />
                                            </SelectTrigger>
                                            <SelectContent>
                                                <SelectItem value="Đông">Đông</SelectItem>
                                                <SelectItem value="Tây">Tây</SelectItem>
                                                <SelectItem value="Nam">Nam</SelectItem>
                                                <SelectItem value="Bắc">Bắc</SelectItem>
                                                <SelectItem value="Đông Nam">Đông Nam</SelectItem>
                                                <SelectItem value="Tây Nam">Tây Nam</SelectItem>
                                            </SelectContent>
                                        </Select>
                                    </div>

                                    <Button type="submit" className="w-full" disabled={loading}>
                                        {loading ? "Đang phân tích..." : "Định Giá Ngay"}
                                    </Button>
                                </form>
                            </CardContent>
                        </Card>

                        {/* Results */}
                        <div className="space-y-4">
                            {result?.error && (
                                <Card className="border-destructive">
                                    <CardContent className="pt-6">
                                        <p className="text-sm text-destructive">{result.error}</p>
                                    </CardContent>
                                </Card>
                            )}

                            {result && !result.error && (
                                <>
                                    <Card>
                                        <CardHeader>
                                            <CardTitle className="flex items-center gap-2">
                                                <TrendingUp className="h-5 w-5 text-primary" />
                                                Kết Quả Định Giá
                                            </CardTitle>
                                        </CardHeader>
                                        <CardContent className="space-y-4">
                                            <div className="text-center p-6 bg-primary/10 rounded-lg">
                                                <div className="text-sm text-muted-foreground mb-1">
                                                    Giá đề xuất
                                                </div>
                                                <div className="text-4xl font-bold text-primary">
                                                    {result.price_suggested
                                                        ? formatPrice(result.price_suggested)
                                                        : "N/A"}
                                                </div>
                                                <div className="text-sm text-muted-foreground mt-2">
                                                    {result.price_per_m2
                                                        ? `${(result.price_per_m2 / 1_000_000).toFixed(1)} triệu/m²`
                                                        : ""}
                                                </div>
                                                {result.ml_estimate && (
                                                    <div className="mt-4 pt-4 border-t border-primary/20">
                                                        <div className="text-xs text-muted-foreground mb-1 font-medium">
                                                            Dự báo từ AutoML (Tham khảo)
                                                        </div>
                                                        <div className="text-lg font-semibold text-primary/80">
                                                            {formatPrice(result.ml_estimate)}
                                                        </div>
                                                    </div>
                                                )}
                                            </div>

                                            <div className="grid grid-cols-2 gap-4">
                                                <div className="p-4 border rounded-lg">
                                                    <div className="text-sm text-muted-foreground">Giá thấp nhất</div>
                                                    <div className="text-xl font-semibold">
                                                        {result.price_min ? formatPrice(result.price_min) : "N/A"}
                                                    </div>
                                                </div>
                                                <div className="p-4 border rounded-lg">
                                                    <div className="text-sm text-muted-foreground">Giá cao nhất</div>
                                                    <div className="text-xl font-semibold">
                                                        {result.price_max ? formatPrice(result.price_max) : "N/A"}
                                                    </div>
                                                </div>
                                            </div>

                                            {result.confidence && (
                                                <div className="p-4 bg-muted rounded-lg">
                                                    <div className="text-sm font-medium mb-2">
                                                        Độ tin cậy: {result.confidence}%
                                                    </div>
                                                    <div className="w-full bg-background rounded-full h-2">
                                                        <div
                                                            className="bg-primary h-2 rounded-full"
                                                            style={{ width: `${result.confidence}%` }}
                                                        />
                                                    </div>
                                                </div>
                                            )}
                                        </CardContent>
                                    </Card>

                                    {result.reasoning && (
                                        <Card>
                                            <CardHeader>
                                                <CardTitle className="text-base">Phân Tích</CardTitle>
                                            </CardHeader>
                                            <CardContent>
                                                <p className="text-sm text-muted-foreground">
                                                    {result.reasoning}
                                                </p>
                                            </CardContent>
                                        </Card>
                                    )}

                                    {result.market_comparison && (
                                        <Card>
                                            <CardHeader>
                                                <CardTitle className="text-base flex items-center gap-2">
                                                    <MapPin className="h-4 w-4" />
                                                    So Sánh Thị Trường
                                                </CardTitle>
                                            </CardHeader>
                                            <CardContent>
                                                <p className="text-sm text-muted-foreground">
                                                    {result.market_comparison}
                                                </p>
                                                {result.market_samples && (
                                                    <div className="mt-2 text-xs text-muted-foreground">
                                                        Dựa trên {result.market_samples} tin đăng tương tự
                                                    </div>
                                                )}
                                            </CardContent>
                                        </Card>
                                    )}
                                </>
                            )}

                            {!result && (
                                <Card className="border-dashed">
                                    <CardContent className="flex flex-col items-center justify-center py-12">
                                        <Home className="h-12 w-12 text-muted-foreground mb-4" />
                                        <p className="text-muted-foreground text-center">
                                            Nhập thông tin bên trái để nhận định giá
                                        </p>
                                    </CardContent>
                                </Card>
                            )}
                        </div>
                    </div>
                ) : (
                    <div className="max-w-4xl mx-auto py-8">
                        {historyLoading ? (
                            <div className="flex justify-center py-12">
                                <Loader2 className="h-8 w-8 animate-spin text-primary" />
                            </div>
                        ) : historyItems && historyItems.length > 0 ? (
                            <div className="space-y-4">
                                {historyItems.map((item: any) => (
                                    <Card
                                        key={item.id}
                                        className="hover:bg-muted/50 transition-colors cursor-pointer group"
                                        onClick={() => {
                                            setFormData({
                                                property_type: item.property_type,
                                                area_m2: item.area_m2.toString(),
                                                district: item.district,
                                                bedrooms: item.bedrooms?.toString() || "",
                                                direction: "",
                                                legal_status: "",
                                            });
                                            setResult({
                                                price_suggested: item.price_suggested,
                                                price_min: item.price_min,
                                                price_max: item.price_max,
                                                confidence: item.confidence,
                                                property_type: item.property_type,
                                                area_m2: item.area_m2,
                                                district: item.district,
                                            } as any);
                                            setActiveTab("estimate");
                                        }}
                                    >
                                        <CardContent className="p-4">
                                            <div className="flex justify-between items-start mb-2">
                                                <div>
                                                    <h4 className="font-semibold text-lg flex items-center gap-2">
                                                        {item.property_type === "chung_cu" ? "Chung cư" :
                                                            item.property_type === "nha_rieng" ? "Nhà riêng" : "Bất động sản"}
                                                        {" "}{item.area_m2}m² tại {item.district}
                                                    </h4>
                                                </div>
                                                <span className="text-xs text-muted-foreground whitespace-nowrap">
                                                    {formatDistanceToNow(new Date(item.created_at), { addSuffix: true, locale: vi })}
                                                </span>
                                            </div>
                                            <div className="flex items-center gap-6">
                                                <div className="text-primary font-bold text-xl">
                                                    {item.price_suggested ? formatPrice(item.price_suggested) : "N/A"}
                                                </div>
                                                <div className="flex gap-4 text-sm text-muted-foreground">
                                                    <span>Min: {item.price_min ? formatPrice(item.price_min) : "N/A"}</span>
                                                    <span>Max: {item.price_max ? formatPrice(item.price_max) : "N/A"}</span>
                                                </div>
                                                <div className="ml-auto text-xs bg-primary/10 text-primary px-2 py-1 rounded">
                                                    Độ tin cậy: {item.confidence}%
                                                </div>
                                            </div>
                                        </CardContent>
                                    </Card>
                                ))}
                            </div>
                        ) : (
                            <Card className="border-dashed">
                                <CardContent className="flex flex-col items-center justify-center py-12">
                                    <History className="h-12 w-12 text-muted-foreground mb-4" />
                                    <h3 className="text-lg font-medium">Chưa có lịch sử định giá</h3>
                                    <p className="text-muted-foreground text-center mb-4">
                                        Các lần định giá của bạn sẽ xuất hiện tại đây
                                    </p>
                                    <Button variant="outline" onClick={() => setActiveTab("estimate")}>
                                        Định giá ngay
                                    </Button>
                                </CardContent>
                            </Card>
                        )}
                    </div>
                )}
            </div>
            <Footer />
        </>
    );
}
