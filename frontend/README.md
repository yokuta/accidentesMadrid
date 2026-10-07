# A pie · Madrid

Plataforma de comparación de percepción peatonal. Perfil breve, cinco comparaciones, respuestas duraderas, recuperación de sesión y revelación de accidentalidad después de votar. Piloto inicial con las dos ubicaciones suministradas; no contiene recuentos inventados.

## Estructura

- `app/page.tsx`, `components/survey.tsx`: cuestionario y resultados.
- `components/panorama.tsx`: Street View oficial, giro sin desplazamiento; vista fija cuando falta clave.
- `components/study-map.tsx`: mapa Leaflet con celdas de 50 m y foco narrativo.
- `app/studio/page.tsx`: vista privada de análisis, exportación y carga de catálogo.
- `lib/server.ts`: sesiones, muestreo, votos idempotentes y snapshots.
- `lib/study.ts`: contrato de datos y comparación de métricas.
- `db/schema.ts`, `drizzle/`: base D1 y migraciones del esquema.

## Dos formas de usarla

1. **Demo alojada:** API y D1 integrados; `/studio` se abre con la clave privada de la entrega. Carga `catalogo_estudio.json` producido por el cuaderno.
2. **Tu servidor:** configura `VITE_API_BASE=http://localhost:8000` en `.env` para utilizar la API portable FastAPI incluida en la entrega separada. El frontend conserva su recorrido y usa ese contrato. Permite CORS exclusivamente desde el origen del frontend; usa HTTPS en producción. Deja `VITE_API_BASE` vacío para volver a la base de la demo.

## Desarrollo local

Requisitos: Node >=22.13 y pnpm. Conserva `pnpm-lock.yaml`.

```sh
pnpm install
pnpm run db:generate
pnpm run build
```

La copia incluye `.env.example`. Copia sus claves a `.env` y a `.dev.vars` para el entorno Worker local. `ADMIN_TOKEN` es un secreto servidor; `GOOGLE_MAPS_API_KEY` es una clave pública de navegador que debe restringirse por dominio y API. Nunca subir claves, `.env`, `.dev.vars`, respuestas o bases de datos al repositorio.

La publicación aplica las migraciones D1. Para una base local vacía, después del build aplica cada archivo `drizzle/*.sql` una vez y en orden:

```sh
node --import ./scripts/sites-env.mjs ./node_modules/wrangler/bin/wrangler.js d1 execute DB --local --config dist/server/wrangler.json --persist-to .wrangler/state --file drizzle/0000_low_jane_foster.sql
pnpm run dev
```

La integración con Sites conserva la identidad en `.openai/hosting.json`. Para otro alojamiento Cloudflare configura tus recursos D1 y variables con tus credenciales; la copia no incluye credenciales de despliegue.

## Datos y comportamiento

Cada participación usa un token aleatorio en cookie HttpOnly; se guarda solo su hash. Cinco filas `study_trials` congelan las escenas y métricas. Una restricción única por sesión/ronda y una actualización condicionada a `choice IS NULL` impiden duplicar o cambiar un voto por reintentos concurrentes. Una respuesta de la sesión ajena no puede modificarse con otro token.

No se revelan cohortes ni accidentes en el cuestionario. Resultados requiere cinco respuestas guardadas. Empates de preferencia y «no puedo valorar» no se puntúan. La concordancia requiere métricas verificadas, con la misma definición, periodo, radio, calidad y versión; elegir comodidad concuerda con elegir menor accidentalidad registrada.

Con 5 puntos high y 5 controles, las cinco parejas son distintas y no repiten ubicaciones por participación. Con dos puntos se repite la pareja y se marca `study_mode=demo`. Un catálogo de 100 high y 20–30 controles está soportado; el muestreo actual es aleatorio sin reposición por participante, no optimiza el balance global de exposiciones.

El JSON del cuaderno incluye un mapa que conserva todos los accidentes de la muestra en celdas de 50 m, y hasta 100 focos contados en buffers con separación de centros de al menos 2R. El visor recorre los cinco primeros. Su ranking es metodológico, no un ranking oficial de peligrosidad.

## Límites conocidos

- Hace falta ejecutar el cuaderno en el ordenador con DuckDB y revisar las coordenadas de los panoramas.
- Street View 360° requiere una clave válida. La rotación está implementada, pero no se probó con una clave de Google en esta entrega.
- Los panoramas pueden cambiar o desaparecer; se capturan las coordenadas reales y el ID devuelto cuando el visor los proporciona. No se sustituye silenciosamente una escena por un panorama cercano.
- Una base sin accidentes o con pocos registros no demuestra seguridad; faltan exposición, tráfico y posibles registros no geolocalizados.
- No se ha realizado QA visual en un navegador de este entorno; compilación, tipos, API, permisos de sesión y concurrencia sí fueron comprobados.
- WebMCP expone solo lectura del paso actual, si el navegador lo soporta; no se pudo validar en un contexto WebMCP de este entorno.

## Verificación

Worker local compilado: 16 participaciones con hasta 8 en paralelo, 80 votos únicos, reintentos sin duplicados, orden de rondas, métricas ocultas y exportación privada. API portable: 36 participaciones con hasta 12 en paralelo y 180 votos, más importación repetible a DuckDB. Cálculos espaciales y cobertura del mapa comprobados con una base sintética independiente; no se han inventado resultados sobre el archivo del usuario.
