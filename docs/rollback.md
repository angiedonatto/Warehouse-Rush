# Rollback del modelo servido

Estado: **en preparación** (2026-11-18, miguel). La prueba de rollback con evidencia y el tiempo real de redeploy
del Hugging Face Space se anotan aquí cuando la API esté desplegada.

## Qué significa rollback en este proyecto

- El modelo que sirve la API es `produccion.actual` de `manifests/aliases.json` en el commit desplegado.
- Hoy: `produccion.actual = m1b-i1-seed1-best` (nivel `m1b`, tolera el paso (6,14) cerrado) y
  `produccion.anterior = m1-c3-seed0` (nivel `m1`).
- Rollback = `python -m pipelines.flow rollback --ranura produccion --motivo "..." --api-url <url>`: intercambia
  `actual` y `anterior` (verificando el sha256 del modelo que vuelve), publica `manifests/catalog.json` y verifica
  `/version`. Repetirlo vuelve al estado inicial; el historial de `aliases.json` registra cada cambio.
- Para que la API sirva el cambio hay que hacer commit y redeploy del Space (trazable por commit). Los dos modelos de
  producción ya están precargados en memoria (`api/_modelos.py`), así que tras el redeploy no esperan descarga.

## Antecedente medido: qué se pierde al volver a `m1-c3-seed0`

El rollback **recupera el servicio** (un modelo verificado que completa la misión en el mapa normal), pero
**pierde el escenario del incidente N3**: `m1-c3-seed0` no sabe rodear el paso cerrado.

| Modelo | Escenario | Fuente | Éxito | Choques/ep | Causa de fin |
|---|---|---|---:|---:|---|
| `m1-c3-seed0` | paso abierto (`suite-m1-v1`) | `docs/resultados/eval/incidente-m1-c3-seed0/` (lis, 2026-11-15) | 98% (49/50) | 0.0 | 49 éxito, 1 límite de tiempo |
| `m1-c3-seed0` | paso cerrado (`suite-m1b-v1`) | misma evaluación | **0%** (0/50) | 21.6 | 45 límite de tiempo, 5 batería agotada |
| `m1b-i1-seed1-best` | paso abierto / cerrado | `manifests/m1b-i1-seed1-best.json` | 100% / 100% | 0.0 / 0.0 | éxito |

Comprobación con la API (`api/_episodios.py`, 2026-11-18), semilla 10000, determinista:

- `m1-c3-seed0` con el paso cerrado: **no completa**, `battery_depleted`, **210 choques**, 228 pasos.
- `m1-c3-seed0` con el paso abierto: completa en 82 pasos.
- `m1b-i1-seed1-best` con el paso cerrado: completa en 107 pasos, 0 choques.

Los tres coinciden episodio a episodio con las evaluaciones congeladas de la suite (misma semilla, mismo resultado),
lo que muestra que la API ejecuta la misma simulación que el pipeline de evaluación.

**Consecuencia operativa:** el rollback a `m1-c3-seed0` es aceptable mientras el paso (6,14) esté abierto. Si el
incidente sigue activo, volver a `m1-c3-seed0` deja la operación sin un modelo que funcione en ese escenario; en ese
caso conviene mantener `m1b-i1-seed1-best` o servir la heurística como referencia mientras se corrige.

## Pendiente

- Prueba de rollback con la API desplegada: `m1b-i1-seed1-best` → `m1-c3-seed0` → `m1b-i1-seed1-best`, con la
  evidencia del flujo (`docs/resultados/flujo/<ejecución>-rollback-produccion/`) y la respuesta de `/version` antes y
  después de cada cambio.
- Tiempo real del redeploy del Space (commit → `/version` muestra el modelo nuevo), medido, no estimado.
