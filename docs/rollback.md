# Rollback del modelo servido

Estado: **en preparación** (2026-11-18, miguel). La prueba de rollback con evidencia y el tiempo real de redeploy
de la API en Render se anotan aquí cuando la API esté desplegada (Hugging Face quedó descartado: Spaces Docker exige PRO).

## Qué significa rollback en este proyecto

- El modelo que sirve la API es `produccion.actual` de `manifests/aliases.json` en el commit desplegado.
- Hoy: `produccion.actual = m1b-i1-seed1-best` (nivel `m1b`, tolera el paso (6,14) cerrado) y
  `produccion.anterior = m1-c3-seed0` (nivel `m1`).
- Rollback = `python -m pipelines.flow rollback --ranura produccion --motivo "..." --api-url <url>`: intercambia
  `actual` y `anterior` (verificando el sha256 del modelo que vuelve), publica `manifests/catalog.json` y verifica
  `/version`. Repetirlo vuelve al estado inicial; el historial de `aliases.json` registra cada cambio.
- Para que la API sirva el cambio hay que hacer commit, publicar una imagen nueva y desplegarla en Render (trazable por commit). Los dos modelos de
  producción ya están precargados en memoria (`api/_modelos.py`), así que tras el redeploy no esperan descarga.

## Antecedente medido: qué se pierde al volver a `m1-c3-seed0`

El rollback **recupera el servicio** (un modelo verificado que completa la misión en el mapa normal), pero
**pierde el escenario del incidente N3**: `m1-c3-seed0` no sabe rodear el paso cerrado.

| Modelo | Escenario | Fuente | Éxito | Choques/ep | Causa de fin |
|---|---|---|---:|---:|---|
| `m1-c3-seed0` | paso abierto (`suite-m1-v1`) | `docs/resultados/eval/incidente-m1-c3-seed0/` (lis, 2026-11-15) | 98% (49/50) | 0.0 | 49 éxito, 1 límite de tiempo |
| `m1-c3-seed0` | paso cerrado (`suite-m1b-v1`) | misma evaluación | **0%** (0/50) | 21.6 | 45 límite de tiempo, 5 batería agotada |
| `m1b-i1-seed1-best` | paso abierto / cerrado | `manifests/m1b-i1-seed1-best.json` | 100% / 100% | 0.0 / 0.0 | éxito |

Comprobación con la API (`api/_episodios.py`, 2026-11-18, todavía con el catálogo `legacy-18`), semilla 10000, determinista:

- `m1-c3-seed0` con el paso cerrado: **no completa**, `battery_depleted`, **210 choques**, 228 pasos.
- `m1-c3-seed0` con el paso abierto: completa en 82 pasos.
- `m1b-i1-seed1-best` con el paso cerrado: completa en 107 pasos, 0 choques.

Los tres coinciden episodio a episodio con las evaluaciones congeladas de la suite (misma semilla, mismo resultado),
lo que muestra que la API ejecuta la misma simulación que el pipeline de evaluación.

### Con el catálogo de la web (`trendy-27-v1`)

Los episodios de la web usan el catálogo operativo `trendy-27-v1` (decisión de lis, 2026-11-18); las evaluaciones
certificadas siguen con `legacy-18`. El diagnóstico de lis (`docs/resultados/eval/catalogo-trendy-27/resultados.json`)
no incluía el caso del rollback: `m1-c3-seed0` con el paso cerrado. Medido el 2026-11-18
(`docs/resultados/eval/catalogo-trendy-27/medir_rollback.py` → `rollback_m1-c3-seed0.json`, 50 episodios, semillas
10000–10049, determinista, sha256 del modelo verificado):

| `m1-c3-seed0` | Catálogo | Éxito | Choques/ep | Causas de fin |
|---|---|---:|---:|---|
| paso cerrado | `trendy-27-v1` | **0%** (0/50) | **85.0** | 30 límite de tiempo, 20 batería agotada |
| paso abierto | `trendy-27-v1` | 100% (50/50), 82.3 pasos | 0.0 | 50 éxito |
| paso cerrado | `legacy-18` (control) | 0% | 21.6 | 45 límite de tiempo, 5 batería agotada |
| paso abierto | `legacy-18` (control) | 98%, 86.8 pasos | 0.0 | 49 éxito, 1 límite de tiempo |

El control reproduce la evaluación congelada, así que la medición es comparable. Con el catálogo de la web el
rollback a `m1-c3-seed0` **también pierde el escenario del incidente**, y choca más (85 frente a 21.6 choques por
episodio); con el paso abierto completa todo. Semilla 10000 con `trendy-27-v1`: paso cerrado → límite de tiempo, 400
pasos, 0 choques; paso abierto → éxito en 88 pasos.

**Consecuencia operativa:** el rollback a `m1-c3-seed0` es aceptable mientras el paso (6,14) esté abierto. Si el
incidente sigue activo, volver a `m1-c3-seed0` deja la operación sin un modelo que funcione en ese escenario; en ese
caso conviene mantener `m1b-i1-seed1-best` o servir la heurística como referencia mientras se corrige.

## Pendiente

- Prueba de rollback con la API desplegada: `m1b-i1-seed1-best` → `m1-c3-seed0` → `m1b-i1-seed1-best`, con la
  evidencia del flujo (`docs/resultados/flujo/<ejecución>-rollback-produccion/`) y la respuesta de `/version` antes y
  después de cada cambio.
- Tiempo real del redeploy en Render (commit → imagen → `/version` muestra el modelo nuevo), medido, no estimado.
- Tiempo de despertar de Render Free tras 15 min sin tráfico: la primera medición (2026-11-18) no sirvió porque el
  servicio no llegó a dormirse (mismo proceso antes y después); repetirla sin tráfico de nadie.
