import type { Metadata } from "next";
import { Inter, Space_Grotesk } from "next/font/google";
import "./globals.css";
import { Header } from "@/components/header";
import { Footer } from "@/components/footer";
import { AnimatedBackground } from "@/components/animated-background";
import { getSessionUser } from "@/lib/auth";

const inter = Inter({ subsets: ["latin", "cyrillic"], variable: "--font-sans" });
const display = Space_Grotesk({ subsets: ["latin"], variable: "--font-display" });

export const metadata: Metadata = {
  title: "Cloud-5 · Маркетплейс цифровых товаров",
  description:
    "Телеграм-боты, исходники игр, скрипты и ассеты. Магазин будущего.",
};

export default async function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const user = await getSessionUser();
  return (
    <html lang="ru" className={`${inter.variable} ${display.variable}`}>
      <body className="font-sans antialiased">
        <AnimatedBackground />
        <div className="relative z-10 flex min-h-screen flex-col">
          <Header user={user} />
          <main className="flex-1">{children}</main>
          <Footer />
        </div>
      </body>
    </html>
  );
}
