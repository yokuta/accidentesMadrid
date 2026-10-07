# A pie · Madrid: guía de uso y análisis

La entrega tiene tres partes: la plataforma web, este paquete de análisis/backend y un cuaderno Jupyter autónomo. No es necesario arrancar la API portable para probar la demo alojada.

## 1. Lo que ya funciona

- Tres preguntas iniciales: edad, género y residencia en una ciudad. La ciudad permite sugerencias y escritura libre. Piloto para mayores de 18 años, con opciones de no respuesta.
- Cinco comparaciones de las dos ubicaciones que proporcionaste, con izquierda/derecha aleatoria.
- Elección de comodidad al caminar, empate o imposibilidad de valorar; motivos opcionales.
- Guardado de cada respuesta, recuperación de una participación al recargar y protección frente a reintentos duplicados.
- Resultados después de cinco respuestas, mapa y recorrido por los cinco focos calculados cuando cargas el catálogo.
- Panel privado en `/studio`: filtrar por edad/género, consultar preferencias, exportar respuestas y cargar un catálogo nuevo.
- Capacidad para usar un catálogo de 100 ubicaciones de mayor accidentalidad y 20–30 de contraste. Con al menos cinco de cada grupo, las cinco parejas son diferentes y no se repite una ubicación dentro de una participación.

La demo alojada guarda las respuestas en una base transaccional D1. La API portable de este paquete usa SQLite WAL en tu servidor. Tu archivo DuckDB queda para el análisis; no recibe las escrituras simultáneas de los visitantes.

## 2. Primer uso recomendado

1. Abre la plataforma desde el enlace entregado y completa las cinco comparaciones.
2. Entra en el panel `/studio`. La clave está en `ACCESO_PRIVADO.txt` dentro de este paquete.
3. En el filtro «Tipo de participación», selecciona «Piloto repetido» para ver las pruebas de esta pareja.
4. Abre `A_pie_Madrid_preparacion_y_analisis.ipynb` en Jupyter, en el ordenador donde está tu base de accidentes.
5. Ejecuta las celdas de preparación. La ruta ya viene configurada:

```python
DB_PATH = Path(r"C:\Users\khora\Downloads\accidentesMadrid\accidentes_madrid.duckdb")
```

6. Comprueba las coordenadas de los dos panoramas. Los recuentos se calculan provisionalmente, pero no se evalúa concordancia hasta marcar `coordinates_reviewed=True` en las ubicaciones revisadas.
7. Carga el archivo generado `percepcion_output/catalogo_estudio.json` desde el panel privado.
8. Empieza una participación nueva desde otro perfil de navegador para comprobar los datos nuevos. Una participación anterior mantiene la información con la que empezó, incluso si actualizas el catálogo.

La demo se publica privada. Cuando quieras recoger respuestas de otras personas, comparte o abre el acceso de la plataforma. La clave del panel sigue siendo privada.

## 3. Vistas de Street View

Hasta que añadas una clave, la web muestra vistas fijas correspondientes a tus dos identificadores de panorama. Estas imágenes se solicitan a Google desde el navegador y pueden fallar si Google no sirve la miniatura; en ese caso el participante puede reintentar o marcar que no puede valorar.

Para activar la rotación, usa «Activar las vistas de 360°» en el panel e introduce una clave de **Google Maps JavaScript API**, restringida al dominio de la plataforma y a esa API. La integración desactiva desplazamiento, flechas de navegación, clic para avanzar y zoom. Permite arrastrar para mirar y botones de giro.

No se ha probado con una clave real de Google en esta entrega. Los panoramas pueden desaparecer o cambiar de identificador; no se reemplazan silenciosamente por otro lugar. Revisa también las fechas de las imágenes y las posiciones reales antes de una campaña de investigación.

Documentación: https://developers.google.com/maps/documentation/javascript/get-api-key

## 4. Qué añade el cuaderno a DuckDB

La lectura y exportación JSON funcionan sin modificar tu base. Para guardar la réplica analítica, activa:

```python
WRITE_TO_DUCKDB = True
```

El código está incluido en el cuaderno y en `analisis/estudio.py`. Añade solamente:

| Tabla | Una fila representa |
|---|---|
| `pc_points` | Ubicación del catálogo y panorama |
| `pc_point_metrics` | Recuento para un punto, periodo, radio y versión |
| `pc_story` | Versión del mapa y de sus focos |
| `pc_sessions` | Participación importada desde la plataforma |
| `pc_trials` | Comparación y respuesta importada |

La operación usa transacciones y puede repetirse sin duplicar IDs. Conserva una copia de la base y cierra otras conexiones de escritura antes de ejecutar la sección opcional. Las tablas originales y sus vistas no se modifican.

## 5. Cálculo espacial inicial

- Periodo: **2019–2025**, editable.
- Radio alrededor de cada punto: **25 m**, editable.
- Coordenadas para medir: `x_final`, `y_final`, EPSG:25830.
- Tabla: `accidentes_todos`, `con_peaton=true`, `apto_mapa=true`, calidad `high` o `medium`.
- Unidad: un `accident_uid`, sin unirlo con personas para contar accidentes.
- Mapa completo de la muestra: agrupación en celdas de **50 m**. La suma de accidentes en las celdas se comprueba contra el total de la muestra.
- Focos: buffers con el radio elegido, centrados en coordenadas de accidentes, seleccionando centros separados al menos 2 × radio. Los cinco primeros no son cinco centros del mismo entorno.

El ranking es una regla espacial reproducible, no una lista oficial de los cruces más peligrosos. Usa la auditoría de cobertura y las variantes de radio/2020 incluidas en el cuaderno. Un punto sin registros no demuestra que nunca haya ocurrido un accidente.

## 6. Cómo analizar las respuestas

Desde el panel descarga «Exportar todo · JSON». Cambia `RESPONSES_PATH` en el cuaderno al archivo descargado.

El análisis incluye:

- Preferencia por punto, con el número de veces que aparece y de participaciones.
- Desglose por edad, género, ciudad y residencia urbana.
- Frecuencia de motivos, empates y respuestas no valorables.
- Concordancia: la elección de comodidad coincide con escoger la ubicación de menor accidentalidad registrada en una comparación evaluable.
- Intervalos por bootstrap de participaciones, conservando juntas sus cinco respuestas.
- Control de preferencia por el lado izquierdo y respuestas muy rápidas, señaladas para revisar pero no eliminadas automáticamente.
- Ranking exploratorio Bradley–Terry para considerar los rivales de cada punto y detectar componentes desconectados.
- Regresión exploratoria de preferencia frente a diferencias de accidentalidad, con errores agrupados por participación, cuando hay datos suficientes.

Las participaciones `study_mode=demo` quedan fuera del análisis principal. Cinco repeticiones de una pareja no son cinco observaciones independientes. Se pueden mostrar en una tabla descriptiva separada.

No interpretes «coincidencia» como acierto o fallo del participante. La percepción es una respuesta válida sobre su experiencia. Los registros son accidentes observados, no probabilidades de accidente: faltan exposición peatonal y tráfico. Tampoco asumas representatividad a partir del número de votos o de IDs aleatorios.

## 7. Propuesta de recorrido final

1. Mostrar las elecciones del participante, sin calificar su sensación.
2. Abrir el mapa de Madrid y explicar el periodo, cobertura y unidad.
3. Recorrer cinco focos con el mismo radio y sin duplicar el entorno de un cruce.
4. Revelar en cuáles de las comparaciones eligió el lugar con menos accidentes registrados.
5. Mostrar el resultado colectivo y destacar discrepancias útiles para investigar:

| Percepción | Accidentalidad | Lectura posible |
|---|---|---|
| Mayor comodidad | Mayor acumulación | El entorno puede transmitir una sensación favorable pese a los registros; investigar |
| Menor comodidad | Mayor acumulación | La percepción y los registros convergen |
| Menor comodidad | Pocos registros | Puede haber barreras, miedo, poca exposición o falta de datos |
| Mayor comodidad | Pocos registros | Coincidencia favorable que necesita contexto de exposición |

Define los umbrales antes de analizar los resultados y compara lugares con condiciones semejantes. Para mejorar un ranking futuro conviene añadir comparaciones dentro de cada grupo y entre tipologías, además de alto contra bajo, para conectar el grafo.

## 8. API portable para tu servidor — opcional

Esta API ofrece el mismo contrato que la web: `/api/config`, `/api/session`, `/api/vote`, `/api/results`, `/api/admin/export`, `/api/admin/catalog` y `/api/admin/maps`.

Desde PowerShell, en la carpeta de este paquete:

```powershell
py -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
$env:ADMIN_TOKEN = "una-clave-larga-privada"
$env:VOTES_DB = "C:\ruta\privada\respuestas.sqlite"
$env:ALLOWED_ORIGINS = "http://localhost:5173"
.\.venv\Scripts\python.exe -m uvicorn backend.app:app --host 127.0.0.1 --port 8000 --workers 4
```

En el proyecto web, configura `VITE_API_BASE=http://localhost:8000` en `.env` y vuelve a compilar o iniciar el frontend. Si dejas la variable vacía, usa la API de la demo alojada. Ambos orígenes deben coincidir con la lista de CORS.

Para servirla a otras personas, despliega la API en tu servidor con HTTPS y acceso al origen de la web; usa `COOKIE_SECURE=1`. Guarda SQLite en disco local del servidor, no en una carpeta de red o NAS. WAL permite lecturas concurrentes y serializa escrituras cortas con espera de hasta 30 segundos. Para carga sostenida elevada, migrar la base de votos a PostgreSQL es una evolución; la plataforma ya separa esos votos de DuckDB.

La API no lee el archivo de accidentes durante cada voto. La preparación se ejecuta en Jupyter y se incorpora mediante el catálogo. El frontend y la API portable son alternativas de alojamiento; no necesitas mantener dos bases de votos para una misma campaña.

## 9. Verificación realizada

- Worker compilado local: 16 participaciones, hasta 8 en paralelo, y 80 respuestas únicas; orden de rondas, reintentos, métricas ocultas y exportación privada.
- API portable: 36 participaciones, hasta 12 en paralelo, y 180 respuestas únicas; aislamiento, reintentos y exportación sin tokens.
- Cálculos espaciales, cobertura íntegra del mapa e importaciones/escrituras repetibles a DuckDB comprobados con datos sintéticos ajenos a tu archivo.
- Todas las celdas de cálculo del cuaderno ejecutadas sobre esa base sintética. El cuaderno entregado no contiene salidas inventadas de tu base.
- Compilación y comprobación de tipos superadas. No se pudo realizar una revisión visual en un navegador de este entorno ni una prueba con clave de Street View. WebMCP es opcional y tampoco se verificó en un navegador compatible.

## Archivos privados

`ACCESO_PRIVADO.txt` contiene la clave de tu panel alojado. No publiques ese archivo ni lo incluyas en repositorios o paquetes que compartas con participantes.
