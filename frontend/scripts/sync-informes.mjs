import { cpSync, existsSync, mkdirSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

/**
 * Copia `reports/validacion_sentimiento_revision.html` a
 * `frontend/public/informes/` para que la pestaña Metodología pueda enlazarlo.
 * Si el informe aún no existe (pipeline no ejecutado), solo avisa.
 */
const frontendRoot = join(dirname(fileURLToPath(import.meta.url)), "..");
const repoRoot = join(frontendRoot, "..");
const source = join(repoRoot, "reports", "validacion_sentimiento_revision.html");
const target = join(frontendRoot, "public", "informes", "validacion_sentimiento_revision.html");

if (!existsSync(source)) {
  console.warn(`[sync:informes] informe no encontrado, se omite: ${source}`);
  process.exit(0);
}

mkdirSync(dirname(target), { recursive: true });
cpSync(source, target);
console.log(`[sync:informes] ${source} -> ${target}`);
