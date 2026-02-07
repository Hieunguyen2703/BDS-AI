import type { Metadata } from "next";
import { Inter } from "next/font/google";
import "./globals.css";
import { Providers } from "@/components/providers";
import { Toaster } from "@/components/ui/toaster";
import { ChatWidget } from "@/components/chat-widget";

const inter = Inter({ subsets: ["latin", "vietnamese"] });

export const metadata: Metadata = {
  title: "BDS Agent - Tìm kiếm BĐS thông minh",
  description: "Hệ thống tìm kiếm và quản lý tin bất động sản tự động với AI",
  keywords: ["bất động sản", "nhà đất", "Hà Nội", "mua bán nhà", "AI"],
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="vi" suppressHydrationWarning>
      <body className={inter.className}>
        <Providers>
          {children}
          <Toaster />
          <ChatWidget />
        </Providers>
      </body>
    </html>
  );
}
