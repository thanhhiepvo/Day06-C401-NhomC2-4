import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "AI Food Recommendation Agent",
  description: "Gợi ý món ăn từ dataset JSON local bằng FastAPI + ReAct tools",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="vi">
      <body>{children}</body>
    </html>
  );
}

