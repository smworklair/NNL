import type { Metadata, Viewport } from "next";
import Script from "next/script";
import "./globals.css";
import Telegram from "@/components/Telegram";

export const metadata: Metadata = {
  title: "Справка по годности",
  description: "Найдите свою болезнь в Расписании болезней и узнайте, что дальше.",
};

export const viewport: Viewport = {
  width: "device-width", initialScale: 1, viewportFit: "cover",
  themeColor: [{ media: "(prefers-color-scheme: dark)", color: "#121211" }, { media: "(prefers-color-scheme: light)", color: "#f6f6f2" }],
};

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html lang="ru">
      <body>
        <Script src="https://telegram.org/js/telegram-web-app.js" strategy="beforeInteractive" />
        <Telegram />
        {children}
      </body>
    </html>
  );
}
