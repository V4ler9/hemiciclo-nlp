"use client";

import { useEffect, useRef } from "react";
import { type ChartOption, echarts } from "@/lib/echarts";

/**
 * Contenedor de un gráfico ECharts en canvas.
 *
 * El gráfico se inicializa en el cliente (efecto), se reajusta con
 * `ResizeObserver` y se libera al desmontar; un cambio de `option` (memoizado
 * por el padre) lo vuelve a montar. El `ariaLabel` describe el contenido en
 * texto para lectores de pantalla (el canvas no es accesible).
 */
export function Chart({
  option,
  className,
  ariaLabel,
}: {
  option: ChartOption;
  className?: string;
  ariaLabel: string;
}) {
  const containerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const container = containerRef.current;
    if (!container) return undefined;
    const chart = echarts.init(container, undefined, { renderer: "canvas" });
    chart.setOption(option);
    const observer = new ResizeObserver(() => chart.resize());
    observer.observe(container);
    return () => {
      observer.disconnect();
      chart.dispose();
    };
  }, [option]);

  return <div ref={containerRef} className={className} role="img" aria-label={ariaLabel} />;
}
