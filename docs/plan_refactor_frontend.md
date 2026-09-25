# Plan: Refactorización del frontend — Streamlit → Next.js

> Documento vivo derivado de la sesión de diseño del 2026-09-23. Cada decisión está
> referenciada por la Q que la cerró. Cambios de alcance: documentarlos aquí y, si son
> de rigor analítico, en `docs/DECISIONS.md`.

## 0. Decisiones cerradas (resumen)

| Área | Decisión | Ref. |
|---|---|---|
| Alcance | Python solo como backend (FastAPI existente); frontend 100% TS. Convivencia temporal con Streamlit hasta validación | Q1, Q8 |
| Frontend | Next.js (App Router) + TypeScript estricto en `frontend/` | Q2 |
| Datos | Evolución **solo aditiva** del API; tipos TS generados del OpenAPI | Q3, Q24 |
| Estética | Registro editorial data-journalism, light, serif en titulares | Q4, Q10 |
| Portada | Artefactos existentes: 3 cambios de tono global + rejilla de cambios por tópico (cuota) | Q16b, Q20a |
| Estadística | Mann-Whitney antes/después por cambio → `p`, `r` (rank-biserial), `n`; BH → `q` auditado en Métricas, `p` en hover | Q21a, Q22a |
| Series pequeñas | Todas visibles; badge "baja potencia" si `tamano_serie < 24` + filtro para ocultarlas | Q23a |
| Tooltip | `r`, `p`, `n` + intervalo temporal comparado | Q12a+n |
| UI | Tailwind + shadcn/ui · ECharts · solo español · sin filtro temporal · sin escrituras | Q9, Q30, Q13, Q28, Q29 |
| Secciones | I Cambios de tono · II Métricas · III Evidencias por tópico · IV Metodología | Q6b, Q19a, Q25b, Q32a |
| Responsive | Desktop-first; tablet correcta; móvil legible con tooltips por toque | Q31a |
| Identidad | Título editorial propio + firma "hemiciclo-nlp" en el pie | Q33b |
| Arranque | `npm run dev:all` (concurrently) + `docker compose` con servicio `web` (:3000) | Q14, Q27a |
| Calidad | TS estricto + ESLint/Prettier · Vitest · Playwright + axe-core (WCAG AA) | Q15c |
| Fuera de alcance | Tono×tópico, i18n, modo oscuro, revisión de etiquetas en UI, despliegue real, borrado inmediato de Streamlit | Q16, Q13, Q10, Q29, Q8 |

## 1. Fases

### Fase 0 — Backend aditivo: estadísticos por cambio ✅
- [x] Nuevo cálculo sobre `reports/tables/cambios_regimen.csv`: Mann-Whitney U (antes vs. después de cada `fecha`) sobre los valores mensuales de la serie correspondiente (`data/intermediate/series_mensuales.parquet`), `r` = coeficiente de efecto rank-biserial (signo concordante con `delta`), `n` = meses antes + después, y BH por familia → `q`.
- [x] Nuevo artefacto `reports/tables/cambios_regimen_test.csv` (columnas: `serie, serie_id, fecha, r, p, q, n_antes, n_despues, n, significativo_bh`). Regenerado sobre los datos reales: 136 filas; de los 3 cambios de tono, solo 2020-06 sobrevive BH (q=0,0001).
- [x] Endpoint `GET /changes/stats` en `src/api/main.py` (503 si falta el artefacto, filtros `serie`/`serie_id`/`max_q`, igual que el resto).
- [x] Tests: `tests/test_api.py` ampliado (fixture + `/changes/stats` + CORS + OpenAPI completo); unitarios de `build_changes_stats` en `tests/test_analysis.py` (escalonado, signo, degenerado, validaciones).
- [x] Semillas: no aplica — MW y BH son deterministas (no hay remuestreo); `SEED = 42` intacto.
- [x] CORS explícito en `create_app` (`HEMICICLO_ALLOWED_ORIGINS`, por defecto `http://localhost:3000`; solo GET) con test de aceptación y rechazo.
- **Criterio**: ✅ Streamlit sin cambios (`git diff reports/tables` vacío tras regenerar); `/changes` intacto; 144 tests + pyright estricto en verde.

### Fase 1 — Cimientos del frontend (`frontend/`) ✅
- [x] Scaffold Next.js 16.3 (App Router, TS, ESLint flat, Prettier, Tailwind v4) + shadcn/ui (base `neutral`, token `--font-sans` reparado).
- [x] Dependencias: `echarts`, `concurrently`, `openapi-typescript`, `prettier` + plugin Tailwind. `vitest`/`@playwright/test`/`@axe-core/playwright` → Fase 7.
- [x] `tsconfig` estricto: `strict` + `noUncheckedIndexedAccess`.
- [x] Tipos TS desde el OpenAPI de FastAPI: `npm run gen:api` = vuelca `reports/openapi.json` (nuevo CLI `src/api/openapi.py`, logging sin `print`) + `openapi-typescript` → `src/lib/api-types.gen.ts`.
- [x] Capa de datos `src/lib/api.ts`: GET tipado por path/query, `ApiError` con red/404/503, timeout 15 s, `NEXT_PUBLIC_HEMICICLO_API_URL` (default `http://localhost:8000`).
- [x] `npm run dev:all` levanta uvicorn + next dev con `concurrently -k`.
- **Criterio**: ✅ `npm run build` verde y `/` consume `/meta`: 30.027 intervenciones, 58 tópicos, 32 % outliers, c_v 0,7546, diversidad 0,9414 (verificado con los dos servidores levantados, y el fallback de "API no disponible" con la API parada).

### Fase 2 — Shell e identidad ✅
- [x] Layout editorial: titular serif *«El tono del debate: tópicos y cambios de régimen en el Congreso (2015-2023)»* en la portada, marca `hemiciclo-nlp` en cabecera y firma en el pie. Tipografías: **Source Serif 4** (titulares) + **Inter** (cuerpo), auto-alojadas con `next/font` y conectadas a los tokens `--font-serif`/`--font-sans` de shadcn (reparada la autorerencia que rompía la tipografía).
- [x] Navegación a las 4 secciones como subpestañas en `SiteHeader` (`aria-current="page"`, foco visible): `/` · `/metricas` · `/evidencias` · `/metodologia`, con placeholders honestos que enumeran su contenido previsto. Solo modo claro, sin i18n.
- [x] Estados de la API: `loading.tsx` (esqueleto con `aria-busy`) + `ApiErrorNotice` que distingue 503 (artefacto ausente), status 0 (API caída) y otros. Paleta neutral shadcn (contraste AA razonable; **barrido formal con axe queda para Fase 7**).
- **Criterio**: ✅ build verde con las 4 rutas; DOM renderizado verificado por HTTP (KPIs reales, `aria-current` único por página, fuentes definidas en CSS sin autorreferencia rota). *No verificado por screenshot: esta sesión no tiene navegador de escritorio conectado.*

### Fase 3 — Portada «Cambios de tono» ✅
- [x] Titular: serie de tono global (`senti_n`, eje 0–6) con las líneas de los 3 cambios (2015-10 +0,401 · 2016-09 −0,306 · 2020-06 −0,196) y fichas por cambio con `media_antes → media_despues`; delta con tooltip `r`, `p`, `n` + intervalo comparado (hover **y** foco de teclado; también con toque).
- [x] Rejilla de 58 small multiples (cuota mensual por tópico) ordenada por `max |delta|` descendente, 133 líneas de cambio, badge «Baja potencia» y filtro para ocultarlas.
  - **Umbral corregido con datos**: la propuesta inicial de 24 meses marcaba **38 de 58** tópicos y anulaba el distintivo. Fijado en **10 meses con ≥5 intervenciones** (= p25 actual → 12 tópicos), documentado en `src/lib/constants.ts`.
- [x] Etiquetado honesto: héroe = «Cambios de tono detectados»; rejilla = «Cambios por tópico… son de **prevalencia, no de tono**».
- [x] Sin filtro temporal; 136 tooltips `r`/`p`/`n` generados (3 + 133).
- **Criterio**: ✅ `next build` + lint + prettier verdes; SSR verificado por HTTP (3 fichas, 58 tarjetas = 52 con cambios + 6 sin, 12 badges = cálculo Python, contador de filtro (12), fallback sin API funcionando). **No verificado**: render de los canvas de ECharts (sin navegador de escritorio conectado a la sesión) — pendiente de revisión visual con `npm run dev:all` → `localhost:3000`.
- **Incidencias detectadas y corregidas durante la fase**:
  1. `TypeError: frame.join is not a function` (React Flight) en cada render del fallback: pasaba la **instancia `ApiError` con cadena `cause`** como prop al componente de aviso. Tri-estado comprobado: instancia+`cause` = error; instancia sin `cause` = limpio; objeto plano = limpio. Arreglo: la capa de presentación recibe un registro plano `ApiFailure {status, detail}`; la cadena completa se registra con `console.error` en el servidor. Documentado en `src/components/api-error.tsx`.
  2. El `catch` de la portada se tragaba el sentinel interno `DYNAMIC_SERVER_USAGE` de Next (usado para marcar la ruta dinámica) y lo registraba como fallo de API. Arreglo: `isDynamicUsage()` en `src/lib/api.ts`, re-lanzado en `apiGet` y en la portada; la build vuelve a marcar `ƒ /` sin ruido.

### Fase 4 — Pestaña Métricas (4 bloques) ✅
- [x] Modelo de tópicos: rejilla de selección completa (36 configs, la elegida resaltada), c_v 0,7546, diversidad 0,9414, outliers 32,0 %, regla D-32 como entradilla y sensibilidad de embeddings (D-39, ARI/NMI). Endpoint nuevo **`GET /topics/selection`** (adiactivo; declarado antes de `/topics/{topic_id}` — lo cazó el test) + fixture y test.
- [x] Validación de sentimiento: métricas D-36/D-37, ICs bootstrap (`est [ic_inf, ic_sup]`, n_boot), acuerdo 3 bandas con Fleiss y matrices de confusión `senti_3`/`senti_6` conmutables (radios accesibles, intensidad proporcional con contraste AA).
- [x] Detección de cambios: KPIs (136 contrastes · p<0,05 crudos · **45 con q<0,05 tras BH** · mediana de tamaños), sensibilidad de penalización agregada por factor (0,25×–4×), criterio de potencia (10 meses con ≥5 intervenciones) + distribución de tamaños, y tabla completa de los136 contrastes ordenada por `q` (scroll, cabecera fija).
- [x] Calidad de datos: KPIs de escala + volumen mensual (barras) y tasa de outliers (línea) en ECharts (`BarChart` registrado). `apiGet` extiendido con parámetros de ruta para `/sentiment/confusion/{level}`.
- **Criterio**: ✅ pytest **145 passed** / ruff / pyright estricto / ESLint / Prettier / `next build` verdes; `/metricas` renderizada con datos reales (11 llamadas API concurrentes, `ƒ /metricas`) y log sin errores.

### Fase 5 — Pestaña «Evidencias por tópico» ✅
- [x] Explorador de tópicos: `<select>` accesible con los **58 tópicos** ordenados alfabéticamente por etiqueta, carga perezosa del detalle vía `GET /topics/{id}` (estado derivado del dato, sin `setState` síncrono en efecto), etiqueta + descripción LLM + tamaño/cuota + estado de revisión (honesto: «aún sin revisión humana (D-25)»), términos c-TF-IDF como chips y textos representativos en `<details>` expandibles con su `utterance_id`.
- [x] Heatmap «cuota relativa por tópico y mes» en ECharts: **top-20 por intervenciones** (misma regla que `charts.py::topic_heatmap`), etiquetas truncadas a 42, rampa viridis, celdas nulas donde no hay datos, tooltip tópico+mes+cuota; `HeatmapChart` y `VisualMapComponent` registrados. Lógica pura `buildTopicHeatmap` en `lib/changes.ts` (testeable en Fase 7).
- [x] Estado de carga del panel y `ApiErrorNotice` ante fallo del endpoint de detalle.
- **Criterio**: ✅ lint/Prettier/`next build` verdes; verificado con Node: `/evidencias` 200, **58 opciones**, aria del heatmap «los 20 tópicos», detalle real (`/topics/0` → etiqueta,3 textos,15 términos), log sin errores.

### Fase 6 — Pestaña «Metodología» ✅
- [x] Prosa en español redactada por el agente desde `DECISIONS.md` y README (Q26a) en siete secciones: Alcance, Corpus y limpieza, Modelado de tópicos (regla D-32,36 configs →58 tópicos,32,0 % outliers, c_v 0,7546; robustez D-39 ARI 0,711/NMI 0,875), Medición y validación del tono (reweighted 0,675/0,374, κ² 0,656/0,701 y **limitación D-37 explícita**), Series y cambios de régimen (PELT,136 cambios en53 series, **45/136 con q<0,05**), **Análisis exploratorio de eventos (resultado nulo)** y Trazabilidad. *Pendiente de revisión por el usuario.*
- [x] Bloque del resultado nulo (D-09): lectura honesta (8 eventos, ventana ±3 meses,472 contrastes,0 con q<0,05, mínimo0,254, potencia limitada con82 meses) + **tabla de eventos** (8×4) + **heatmap evento × tópico** en ECharts replicando `associations_figure` (top-20 por |ρ|, rampa RdBu ±máx, ★ si q<0,05) con tooltip `ρ · q · n`. Lógica pura en `lib/events.ts`.
- [x] Enlace al HTML de validación servido desde `frontend/public/informes/` con sincronización automática (`scripts/sync-informes.mjs` en `predev`/`prebuild` y `npm run sync:informes` desde la raíz; el HTML pesa17 KB).
- [x] `structure.md`: añadidos `frontend/scripts/` y `frontend/public/` al árbol.
- **Criterio**: ✅ lint/Prettier/`next build` verdes; verificado con Node:7 secciones,32 celdas de eventos, aria del heatmap, cifras clave (30.027 ·45 de136 ·0,254), HTML servido **200**, log sin errores; pytest **145 passed**.

### Fase 7 — Calidad ✅
- [x] **Vitest**:29 tests unitarios en4 archivos — `format` (formateadores es-ES, `monthShift`, truncado de etiquetas), `changes` (`toTimeline`, `buildToneView` con/sin stats, orden y baja potencia de `buildTopicCards`, `buildTopicHeatmap` con top-20 y huecos), `events` (orden cronológico, top-N por |ρ|, matrices con nulos, rango de color ≥0,6), `api` (URL con query/path-params, ApiError status 0/503, re-lanzado del sentinel `DYNAMIC_SERVER_USAGE`, `isDynamicUsage`). `npm test` (y `npm --prefix` desde la raíz).
- [x] **Playwright E2E** (`npm run e2e`, arranca API + web solos): portada (héroe,3 fichas,59 canvases, filtro58→46, tooltip `r`/`p`/`n` por hover **y** foco), métricas (4 secciones, rejilla36 scroll con cabecera fija,136 filas sin `tópico NN`, toggle3/6), evidencias (58 opciones, detalle, `<details>`, heatmap), metodología (7 secciones,8 eventos, heatmap, HTML200).
- [x] **axe-core WCAG2A/AA en las4 rutas:0 violaciones**. La auditoría cazó un **bug real**: los contenedores con scroll no eran accesibles con teclado (WCAG 2.1.1) → todos los wrappers de tablas ahora son `role="region"` + `aria-label` + `tabIndex=0` con foco visible.
- [x] Regla ESLint `no-unused-vars` con `argsIgnorePattern: "^_"` (parámetros de tipos en mocks). `.gitignore` de `test-results/` y `playwright-report/`.
- **Criterio**: ✅ `npm test` **29/29** · `npm run e2e` **17/17** · ESLint/Prettier/`next build` verdes · pytest **145 passed** · puertos libres.

### Fase 8 — Integración y retiro ✅ (validada por el usuario)
- [x] `compose.yaml`: servicios `api` (:8000) + **`web` (:3000)** con build multi-stage (`frontend/Dockerfile`, `.dockerignore` en la raíz) y URL dual: `NEXT_PUBLIC_HEMICICLO_API_URL` (build, navegador) y `HEMICICLO_API_URL_SERVER` (runtime, servidor Next → `http://api:8000`).
- [x] README: estado del refactor, roadmap con la fila del frontend, «Producto local» con `npm run dev:all` como mando único y comprobaciones (`pytest`/`test`/`e2e`); SOURCES y PROJECT_SPEC actualizados.
- [x] Retiro: **`app/`** (Streamlit + plotly), **`src/visualization/charts.py`**, los **5 PNG de `reports/figures/`** y `streamlit`/`plotly` del extra `app` (queda `fastapi`+`uvicorn`+`pyarrow`; `uv lock` regenerado). Contrato actualizado: `test_smoke.py` (rutas → `frontend/…`, módulos documentados sin `charts`) y `test_analysis.py` sin el test de figuras (**pytest 144**).
- [x] `structure.md`: borrados los bloques `app/`, `src/visualization/` y `reports/figures/`; Dockerfile y frontend descritos con D-42. **D-42** añadida a `docs/DECISIONS.md`.

### Fase 9 — Pulidos finales (post-D-42) ✅
- [x] **Q1c — Popup de subgráfico**: click/tap/teclado en el gráfico de cualquier tarjeta abre un `<dialog>` nativo (ESC, botón y fondo lo cierran) con el gráfico ampliado (`buildTopicDetailOption`: ejes, cuota y líneas de cambio etiquetadas) y la **tabla de respaldo** por cambio: fecha, Δ, medias antes/después, `r`, `p`, `n` e intervalo — **sin `q`**. Región de tabla con foco teclado (axe) y sin llamadas nuevas a la API.
- [x] **Q2 — Deep-link**: botón «Ver evidencias de este tópico →» en el popup; Evidencias ahora interpreta `?topico=N` (`PageProps` + `initialTopic` en el selector).
- [x] **Q3a — Hover con estadísticos en el héroe**: las líneas de cambio dejan de ser `silent` (`triggerLineEvent`) y el tooltip del eje añade la ficha completa bajo el puntero: fecha, Δ, medias, `r`, `p`, `n` e intervalo (mismos textos que las fichas, extraídos a `statsLine`/`intervalLine` compartidos).
- [x] **Q4a+b — Heatmap de Evidencias**: escala **logarítmica** con piso `HEATMAP_LOG_EPS` = 0,01 % (leyenda con ticks re-transformados, sin −∞), bordes de celda, tooltip con **cuota lineal + intervenciones** (`HeatmapData.counts`) y figcaption que explica la escala.
- [x] Tests: **Vitest 38/38** (`chart-options.test.ts` nuevo: tooltip del héroe, `heatmapLog`, detalle de diálogo; `statsLine`/`intervalLine` en `format.test.ts`; `counts` en `changes.test.ts`) y **Playwright 20/20** (diálogo con tabla sin `q`, deep-link `?topico=` y **5ª auditoría axe con el diálogo abierto: 0 violaciones**).
- **Criterio**: ✅ ESLint/Prettier/`next build` verdes · pytest **144 passed** · puertos libres.

## 2. Riesgos asumidos
- Segmentos cortos de PELT (`min_size=6`) → `n` pequeño en algunos contrastes; el hover expone `n` para que el lector juzgue.
- Tras BH, cambios detectados por PELT que no superen significancia: la portada los presenta como *detectados por PELT* y deja que `r`/`p`/`q` hablen, sin adornar.
- `topics_labels.csv.reviewed_by` vacío sigue siendo pendiente del proyecto (fuera de alcance, Q29a).
