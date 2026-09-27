#!/usr/bin/env node

/**
 * Orquestador de `npm run pipeline`: sincroniza dependencias con uv y ejecuta
 * las fases del pipeline (Fase 1 → 3b) en la raíz del repositorio.
 *
 * Reglas de ejecución:
 *   - Primero `uv sync --all-extras` (extras de corpus, nlp y analysis); con
 *     `--no-sync` se omite, para conservar en máquinas NVIDIA un torch CUDA
 *     instalado a mano que uv.lock reemplazaría por la rueda de PyPI.
 *   - Una fase se omite si todas sus salidas ya existen.
 *   - Si una fase se ejecuta, todas las aguas abajo se ejecutan también aunque
 *     tengan salida, para no dejar artefactos obsoletos (p. ej. clon nuevo,
 *     donde `reports/` viene versionado pero `data/` no).
 *   - La cadena se detiene en el primer error y propaga su código de salida.
 *
 * Para regenerar un artefacto concreto, bórralo y vuelve a lanzar el comando.
 *
 * Uso: `npm run pipeline [-- --no-sync]` desde la raíz del repositorio.
 */

import { existsSync } from "node:fs";
import { spawnSync } from "node:child_process";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const REPO_ROOT = join(dirname(fileURLToPath(import.meta.url)), "..");

/**
 * Fases en orden de ejecución. `salidas` son las rutas (relativas a la raíz)
 * cuya existencia marca la fase como completada.
 *
 * @type {{ nombre: string; modulo: string; salidas: string[] }[]}
 */
const FASES = [
  {
    nombre: "Fase 1 · descarga del corpus",
    modulo: "src.corpus.downloader",
    salidas: [
      "data/raw/corpus/ParlaMint-ES.txt",
      "data/raw/corpus/cda1055_dat_ParlaCAP-ES_speeches_no_text.tsv",
    ],
  },
  {
    nombre: "Fase 1 · parseo del corpus",
    modulo: "src.corpus.parser",
    salidas: ["data/processed/intervenciones.parquet"],
  },
  {
    nombre: "Fase 2 · limpieza",
    modulo: "src.preprocessing.cleaner",
    salidas: ["data/processed/intervenciones_limpias.parquet"],
  },
  {
    nombre: "Fase 3a · embeddings",
    modulo: "src.nlp.embeddings",
    salidas: ["data/intermediate/embeddings.parquet"],
  },
  {
    nombre: "Fase 3a · tópicos",
    modulo: "src.nlp.topic_model",
    salidas: ["data/processed/intervenciones_topicos.parquet"],
  },
  {
    nombre: "Fase 3a · validación de sentimiento",
    modulo: "src.nlp.sentiment",
    salidas: ["reports/validacion_sentimiento_revision.html"],
  },
  {
    nombre: "Fase 3b · series mensuales",
    modulo: "src.analysis.temporal",
    salidas: ["data/intermediate/series_mensuales.parquet"],
  },
  {
    nombre: "Fase 3b · cambios de régimen",
    modulo: "src.analysis.regime_change",
    salidas: ["reports/tables/cambios_regimen.csv"],
  },
];

/**
 * Lanza un comando en la raíz del repositorio con salida a consola.
 *
 * @param {string} command - Ejecutable (uv).
 * @param {string[]} args - Argumentos del comando.
 * @returns {number} Código de salida del proceso (0 = correcto).
 */
function run(command, args) {
  const started = Date.now();
  // Sin `args` junto a `shell` (DEP0190): se concatena la línea; los argumentos
  // son constantes del script, sin caracteres especiales.
  const result = spawnSync([command, ...args].join(" "), {
    cwd: REPO_ROOT,
    stdio: "inherit",
    shell: true,
  });
  const seconds = ((Date.now() - started) / 1000).toFixed(1);
  if (result.error) {
    console.error(`[pipeline] no se pudo lanzar "${command}": ${result.error.message}`);
    return result.error.code === "ENOENT" ? 127 : 1;
  }
  if (result.status === null) {
    console.error(`[pipeline] "${command}" terminó por señal ${result.signal}`);
    return 1;
  }
  if (result.status !== 0) {
    console.error(`[pipeline] "${command}" terminó con código ${result.status} (${seconds} s)`);
    return result.status;
  }
  return 0;
}

/**
 * Ejecuta la sincronización de dependencias y todas las fases en orden.
 *
 * @param {boolean} noSync - Si es true, se omite `uv sync --all-extras`.
 * @returns {void}
 */
function main(noSync) {
  if (noSync) {
    console.log("[pipeline] sync omitido (--no-sync): se conserva el entorno actual");
  } else {
    console.log("[pipeline] uv sync --all-extras");
    const syncStatus = run("uv", ["sync", "--all-extras"]);
    if (syncStatus !== 0) {
      console.error("[pipeline] abortado: falló la instalación de dependencias");
      process.exit(syncStatus);
    }
  }

  let aguasAbajoSucias = false;
  let ejecutadas = 0;
  let omitidas = 0;

  for (const fase of FASES) {
    const completada = fase.salidas.every((salida) => existsSync(join(REPO_ROOT, salida)));
    if (completada && !aguasAbajoSucias) {
      omitidas += 1;
      console.log(`[pipeline] omitida ${fase.nombre} (ya presente: ${fase.salidas[0]})`);
      continue;
    }

    console.log(`[pipeline] ▶ ${fase.nombre} → python -m ${fase.modulo}`);
    const status = run("uv", ["run", "python", "-m", fase.modulo]);
    if (status !== 0) {
      console.error(`[pipeline] ✖ ${fase.nombre} falló con código ${status}`);
      console.error(`[pipeline] progreso: ${ejecutadas} ejecutadas, ${omitidas} omitidas`);
      process.exit(status);
    }
    ejecutadas += 1;
    aguasAbajoSucias = true;
  }

  console.log(`[pipeline] ✓ completado: ${ejecutadas} ejecutadas, ${omitidas} omitidas`);
}

const argv = process.argv.slice(2);
const desconocidos = argv.filter((arg) => arg !== "--no-sync");
if (desconocidos.length > 0) {
  console.error(`[pipeline] argumento desconocido: ${desconocidos.join(", ")}`);
  console.error("[pipeline] uso: npm run pipeline [-- --no-sync]");
  process.exit(2);
}

main(argv.includes("--no-sync"));
