# Panel web (Next.js): build multi-stage. CONTEXTO = raíz del repositorio
# (el paso de build copia el informe HTML desde reports/).
FROM node:24-slim AS build

WORKDIR /repo

COPY frontend/package.json frontend/package-lock.json ./frontend/
RUN cd frontend && npm ci

COPY frontend ./frontend
COPY reports/validacion_sentimiento_revision.html ./reports/validacion_sentimiento_revision.html

# NEXT_PUBLIC_* se inyecta en build (la consume el navegador: localhost:8000
# desde el host). HEMICICLO_API_URL_SERVER se lee en runtime (la consume el
# servidor Next dentro del contenedor: http://api:8000).
ARG NEXT_PUBLIC_HEMICICLO_API_URL=http://localhost:8000
ENV NEXT_PUBLIC_HEMICICLO_API_URL=${NEXT_PUBLIC_HEMICICLO_API_URL}

RUN cd frontend && npm run build

FROM node:24-slim

WORKDIR /repo/frontend

ENV NODE_ENV=production
COPY --from=build /repo/frontend ./

EXPOSE 3000

CMD ["npm", "run", "start"]
