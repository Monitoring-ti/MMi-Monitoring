# Límites de subida a la base de datos — Motor RAG MMI

**Fecha:** 2026-08-29 · **Autor:** Manus AI

Este informe documenta los límites de inserción y subida de las dos bases de datos del motor MMI —**Supabase/Postgres** (fuente de verdad, vía PostgREST) y **Qdrant Cloud** (motor vectorial)—, los contrasta con el uso actual del pipeline y entrega recomendaciones de dimensionado para la carga masiva del corpus completo.

## Resumen ejecutivo

El pipeline actual está **bien dimensionado** y lejos de cualquier límite. El lote 1 generó 556 chunks con un tamaño medio de ~1,9 KB por fila; incluso el peor lote de 1 000 filas apenas supera 1 MB, muy por debajo de los umbrales problemáticos. Las dos mejoras concretas para la carga masiva son **subir el lote de Postgres de 200 a 500–1000 filas** y **paralelizar el upsert de Qdrant** con `upload_points`.

## 1. Supabase / Postgres (vía PostgREST)

La inserción masiva por la API REST no tiene un límite duro de filas por llamada; el límite práctico lo imponen el tamaño del cuerpo HTTP, el timeout y la memoria [1]. La mejor práctica de Postgres sitúa el lote óptimo en **500–1000 filas** por sentencia, equilibrando rendimiento y consumo de memoria [2]. Como techo teórico, Postgres admite **65 535 parámetros** por sentencia, lo que para la tabla `chunks` (13 columnas) equivale a unas 5 000 filas por lote [3].

En lectura, Supabase devuelve por defecto un máximo de **1 000 filas** por consulta, configurable en *Project Settings → API → "Max rows"* hasta **1 000 000** [4]. Respecto a la seguridad, las tablas creadas en el esquema `public` reciben por defecto privilegios `SELECT/INSERT/UPDATE/DELETE` para los roles `anon`, `authenticated` y `service_role`, aunque el RLS sigue aplicando por fila [5]. El pipeline usa `service_role`, que bypasea RLS —lo correcto para un proceso de backend—.

## 2. Qdrant Cloud

La recomendación oficial para el upsert es de **64–256 puntos por lote**: lotes menores subutilizan la red y lotes mayores aumentan la presión de memoria y el coste de reintento [6]. El método `upload_points` del cliente Python gestiona el batching y la paralelización automáticamente mediante los parámetros `batch_size` y `parallel` [6]. Como referencia de throughput, con un lote de 200 puntos se han reportado tasas de **30 000–40 000 puntos por segundo** [7].

Tres puntos operativos relevantes. Primero, conviene **paralelizar con 2–4 hilos** (idealmente uno por shard) porque un solo hilo rara vez satura el servidor [6]. Segundo, es **obligatorio crear los índices de payload antes de ingerir** los puntos; de lo contrario el grafo HNSW carece de los enlaces extra y la búsqueda filtrada degrada hasta una reconstrucción costosa [6] —en nuestro caso ya se hizo correctamente en la Fase 0. Tercero, el payload es JSON arbitrario cuyo coste se estima como `base × tamaño_medio × 1,5` en disco, y cada índice de payload añade aproximadamente **2× el tamaño del campo indexado** [8].

En cuanto a techos, Qdrant soporta hasta **65 535 dimensiones** por vector (nuestro denso usa 1536) [9], un límite de **200 colecciones** y **32 índices de payload por colección** [10], y un solo nodo suele soportar del orden de **100 millones de vectores** como techo aproximado [8].

## 3. Contraste con el uso actual del pipeline

La medición sobre los 556 chunks reales del lote 1 arroja un tamaño medio de **1 615 bytes** de contenido por fila (máximo 6 141) y una mediana de **468 tokens**. Con estos datos, el contraste con las recomendaciones oficiales es el siguiente:

| Parámetro | Valor actual | Recomendación | Evaluación |
|---|---|---|---|
| Lote INSERT Postgres `chunks` | 200 filas | 500–1000 [2] | Bajo el óptimo; subir a 500 |
| Lote upsert Qdrant | 100 puntos | 64–256 [6] | Correcto |
| Índices payload antes de ingerir | Sí (Fase 0) | Obligatorio [6] | Correcto |
| Paralelización Qdrant | Secuencial | 2–4 hilos [6] | Mejorable para carga masiva |
| Payload Qdrant `content` | acotado a 4 000 chars | según sizing [8] | Correcto |
| Peor lote de 1 000 filas | ~1,0 MB | sin límite duro [1] | Muy por debajo del umbral |

## 4. Recomendaciones para la carga masiva

El corpus completo (~60 archivos) generará del orden de **4 000–5 000 chunks**, una escala que ambos motores absorben sin esfuerzo. Para optimizar el proceso conviene aplicar dos ajustes al pipeline: **subir el lote de Postgres de 200 a 500 filas** (sigue siendo ~1 MB por petición) y **migrar el upsert de Qdrant a `upload_points` con `parallel=2`**, que gestiona batching y concurrencia de forma nativa. No se requieren cambios de infraestructura: el cluster actual de Qdrant Cloud y el proyecto de Supabase tienen capacidad de sobra para este volumen.

## Referencias

1. [Supabase — insert (Data API)](https://supabase.com/docs/reference/javascript/insert)
2. [TigerData — Benchmarking PostgreSQL Batch Ingest](https://www.tigerdata.com/blog/benchmarking-postgresql-batch-ingest)
3. [defn.io — Batch Inserts in PostgreSQL (65 535 parámetros)](https://defn.io/2025/02/15/postgres-batch-inserts/)
4. [Supabase — Max rows (1 000 por defecto, hasta 1 000 000)](https://github.com/orgs/supabase/discussions/3765)
5. [Supabase — Securing your API (grants, RLS, rate limits)](https://supabase.com/docs/guides/api/securing-your-api)
6. [Qdrant — Bulk Upload](https://qdrant.tech/documentation/manage-data/bulk-upload/)
7. [Qdrant — Throughput 30–40K puntos/s (issue #5642)](https://github.com/qdrant/qdrant/issues/5642)
8. [Qdrant — Capacity Planning](https://qdrant.tech/documentation/capacity-planning/)
9. [Qdrant — FAQ (65 535 dimensiones, batch 64–256)](https://qdrant.tech/documentation/faq/qdrant-fundamentals/)
10. [Qdrant — Límites de colección e índices de payload (issue #7529)](https://github.com/qdrant/qdrant/issues/7529)
