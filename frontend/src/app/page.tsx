import Link from "next/link";
import { ArrowRight, Search, BarChart3, Bell, Zap, TrendingUp, Shield } from "lucide-react";
import { Button } from "@/components/ui/button";
import { SearchBox } from "@/components/search/search-box";
import { Header, Footer } from "@/components/layout/header";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";

const FEATURES = [
  {
    icon: Search,
    title: "Tìm kiếm AI thông minh",
    description: "Tự động phân tích và tìm kiếm BĐS trên đa nền tảng (Chợ Tốt, Batdongsan...) với độ chính xác cao.",
  },
  {
    icon: Zap,
    title: "Dữ liệu Real-time",
    description: "Cập nhật tin đăng mới nhất theo thời gian thực. Không bỏ lỡ bất kỳ cơ hội đầu tư nào.",
  },
  {
    icon: TrendingUp,
    title: "Định giá chuẩn xác",
    description: "Mô hình AI phân tích hàng triệu điểm dữ liệu để đưa ra định giá và dự báo xu hướng thị trường.",
  },
  {
    icon: Shield,
    title: "Thông tin minh bạch",
    description: "Tự động lọc tin ảo, tin rác. Chỉ hiển thị các bất động sản đã được xác thực sơ bộ.",
  },
];

export default function HomePage() {
  return (
    <div className="flex min-h-screen flex-col">
      <Header />

      <main className="flex-1 overflow-hidden">
        {/* Hero Section */}
        <section className="relative py-24 md:py-32 lg:py-40 flex items-center justify-center overflow-hidden">
          {/* Background Blobs */}
          <div className="absolute top-0 -left-64 w-96 h-96 bg-purple-500 rounded-full mix-blend-multiply filter blur-3xl opacity-20 animate-blob"></div>
          <div className="absolute top-0 -right-64 w-96 h-96 bg-blue-500 rounded-full mix-blend-multiply filter blur-3xl opacity-20 animate-blob animation-delay-2000"></div>
          <div className="absolute -bottom-64 left-20 w-96 h-96 bg-teal-500 rounded-full mix-blend-multiply filter blur-3xl opacity-20 animate-blob animation-delay-4000"></div>

          <div className="container px-4 relative z-10">
            <div className="mx-auto max-w-4xl text-center">
              <div className="inline-flex items-center rounded-full border border-blue-500/30 bg-blue-500/10 px-3 py-1 text-sm text-blue-300 mb-6 backdrop-blur-sm">
                <span className="flex h-2 w-2 rounded-full bg-blue-500 mr-2 animate-pulse"></span>
                Phiên bản AI 2.0 đã ra mắt
              </div>

              <h1 className="text-4xl font-extrabold tracking-tight sm:text-5xl md:text-6xl lg:text-7xl">
                Tìm kiếm Bất Động Sản <br className="hidden sm:inline" />
                <span className="text-transparent bg-clip-text bg-gradient-to-r from-blue-400 to-purple-400">
                  Thông minh
                </span>
              </h1>

              <p className="mt-6 text-xl text-slate-400 max-w-2xl mx-auto mb-12 leading-relaxed">
                Hệ sinh thái Bất động sản All-in-One: Tìm kiếm đa nền tảng,
                định giá bằng AI và phân tích xu hướng thị trường chỉ trong vài giây.
              </p>

              <div className="mx-auto max-w-3xl transform hover:scale-[1.01] transition-all duration-300">
                <div className="glass p-2 rounded-2xl shadow-2xl shadow-blue-500/10 border border-white/10 bg-white/5 backdrop-blur-md">
                  <SearchBox size="lg" className="w-full bg-transparent border-0 focus-visible:ring-0 text-lg placeholder:text-slate-500 text-white" />
                </div>
              </div>

              <div className="mt-12 flex flex-wrap justify-center gap-6">
                <Button size="lg" className="h-14 px-8 text-lg rounded-xl shadow-xl shadow-blue-600/20" asChild>
                  <Link href="/search">
                    Khám phá ngay
                    <ArrowRight className="ml-2 h-5 w-5" />
                  </Link>
                </Button>
                <Button size="lg" variant="outline" className="h-14 px-8 text-lg rounded-xl border-white/10 hover:bg-white/5 hover:text-white" asChild>
                  <Link href="/analytics">Xem xu hướng</Link>
                </Button>
              </div>

              {/* Stats / Social Proof */}
              <div className="mt-16 grid grid-cols-2 gap-8 md:grid-cols-4 border-t border-white/5 pt-8">
                {[
                  ["10K+", "Tin đăng/ngày"],
                  ["98%", "Độ chính xác"],
                  ["24/7", "Cập nhật"],
                  ["AI", "Powered"],
                ].map(([stat, label]) => (
                  <div key={label} className="flex flex-col items-center">
                    <span className="text-3xl font-bold text-white">{stat}</span>
                    <span className="text-sm text-slate-500">{label}</span>
                  </div>
                ))}
              </div>
            </div>
          </div>
        </section>

        {/* Features Section */}
        <section className="py-24 relative bg-slate-950/50">
          <div className="absolute inset-0 bg-grid-white/[0.02] bg-[size:60px_60px]"></div>
          <div className="container px-4 relative z-10">
            <div className="text-center mb-16">
              <h2 className="text-3xl font-bold sm:text-4xl mb-4 bg-clip-text text-transparent bg-gradient-to-r from-white to-slate-400">
                Tại sao chọn BDS Agent?
              </h2>
              <p className="text-lg text-slate-400 max-w-2xl mx-auto">
                Công nghệ tiên phong định hình lại cách bạn tìm kiếm và đầu tư bất động sản
              </p>
            </div>

            <div className="grid gap-8 md:grid-cols-2 lg:grid-cols-4">
              {FEATURES.map((feature, idx) => (
                <Card key={feature.title} className="group hover:-translate-y-2 transition-all duration-300">
                  <CardHeader>
                    <div className="mb-4 inline-block rounded-xl bg-blue-500/10 p-3 text-blue-400 group-hover:bg-blue-500 group-hover:text-white transition-colors duration-300">
                      <feature.icon className="h-8 w-8" />
                    </div>
                    <CardTitle className="text-xl group-hover:text-blue-400 transition-colors">{feature.title}</CardTitle>
                  </CardHeader>
                  <CardContent>
                    <CardDescription className="text-base leading-relaxed">
                      {feature.description}
                    </CardDescription>
                  </CardContent>
                </Card>
              ))}
            </div>
          </div>
        </section>

        {/* CTA Section */}
        <section className="py-24 relative overflow-hidden">
          <div className="absolute inset-0 bg-gradient-to-r from-blue-900/20 to-purple-900/20"></div>
          <div className="container px-4 relative z-10">
            <div className="mx-auto max-w-4xl text-center rounded-3xl border border-white/10 bg-white/5 p-12 backdrop-blur-lg shadow-2xl">
              <h2 className="text-3xl font-bold sm:text-4xl text-white mb-6">
                Sẵn sàng tìm ngôi nhà mơ ước?
              </h2>
              <p className="text-xl text-slate-300 mb-10 max-w-2xl mx-auto">
                Trải nghiệm sức mạnh của AI trong tìm kiếm bất động sản ngay hôm nay.
              </p>
              <Button size="lg" className="h-16 px-10 text-xl rounded-full shadow-2xl shadow-blue-500/30 hover:shadow-blue-500/50" asChild>
                <Link href="/search">
                  Bắt đầu ngay - Miễn phí
                  <ArrowRight className="ml-2 h-6 w-6" />
                </Link>
              </Button>
            </div>
          </div>
        </section>
      </main>

      <Footer />
    </div>
  );
}
