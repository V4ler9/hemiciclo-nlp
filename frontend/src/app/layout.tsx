import type { Metadata } from "next";
import { Inter, Source_Serif_4 } from "next/font/google";
import { SiteHeader } from "@/components/site-header";
import "./globals.css";

const inter = Inter({
  variable: "--font-inter",
  subsets: ["latin"],
});

const sourceSerif = Source_Serif_4({
  variable: "--font-source-serif",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  title: "hemiciclo-nlp · El tono del debate",
  description:
    "Evolución temática y tonal del Congreso de los Diputados (2015-2023): cambios de régimen, métricas y justificación.",
};

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html lang="es" className={`${inter.variable} ${sourceSerif.variable} h-full antialiased`}>
      <body className="bg-background text-foreground flex min-h-full flex-col">
        <SiteHeader />
        <main className="mx-auto w-full max-w-6xl flex-1 px-6 py-10">{children}</main>
        <footer className="border-border border-t">
          <div className="text-muted-foreground mx-auto flex w-full max-w-6xl items-center justify-between gap-4 px-6 py-6 text-[0.7rem] tracking-[0.2em] uppercase">
            <span>hemiciclo-nlp</span>
            <span>Congreso de los Diputados · 2015-2023</span>
          </div>
        </footer>
      </body>
    </html>
  );
}
