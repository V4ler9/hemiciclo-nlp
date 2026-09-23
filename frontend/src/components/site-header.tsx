"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

const SECTIONS = [
  { href: "/", label: "Cambios de tono" },
  { href: "/metricas", label: "Métricas" },
  { href: "/evidencias", label: "Evidencias por tópico" },
  { href: "/metodologia", label: "Metodología" },
] as const;

function isActive(pathname: string, href: string): boolean {
  return href === "/" ? pathname === "/" : pathname.startsWith(href);
}

/** Cabecera editorial: marca, subtítulo y navegación por subpestañas. */
export function SiteHeader() {
  const pathname = usePathname();

  return (
    <header className="border-border border-b">
      <div className="mx-auto w-full max-w-6xl px-6">
        <div className="flex flex-wrap items-baseline justify-between gap-x-6 gap-y-2 pt-8 pb-4">
          <p className="text-foreground text-xs font-medium tracking-[0.3em] uppercase">
            hemiciclo-nlp
          </p>
          <p className="text-muted-foreground text-[0.7rem] tracking-[0.2em] uppercase">
            Análisis de tópicos y tono · Congreso de los Diputados (2015-2023)
          </p>
        </div>
        <nav aria-label="Secciones del informe">
          <ul className="-mb-px flex flex-wrap gap-x-6 gap-y-2">
            {SECTIONS.map((section) => {
              const active = isActive(pathname, section.href);
              return (
                <li key={section.href}>
                  <Link
                    href={section.href}
                    aria-current={active ? "page" : undefined}
                    className={
                      "inline-block border-b-2 pb-3 text-sm transition-colors " +
                      "focus-visible:outline-foreground focus-visible:outline-2 focus-visible:outline-offset-2 " +
                      (active
                        ? "border-foreground text-foreground font-medium"
                        : "text-muted-foreground hover:text-foreground border-transparent")
                    }
                  >
                    {section.label}
                  </Link>
                </li>
              );
            })}
          </ul>
        </nav>
      </div>
    </header>
  );
}
