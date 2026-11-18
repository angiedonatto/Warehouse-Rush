# Warehouse Rush — ficha del ambiente v0.3 (`warehouse-v3`)

Cambio respecto de [ambiente-v0.2.md](ambiente-v0.2.md): **la recompensa pasa a ser un parámetro versionado de cada run.** Observación `Box(27)`,
acciones `Discrete(8)`, mapa, presupuesto, mecánica de la bandeja y nivel `m1` no cambian. Contrato: [`envs/CONTRATO.md`](../envs/CONTRATO.md).

## Por qué
El run `m1-c0-seed0` (v2) terminó con 0% de éxito y la política eligió FRENAR en 93% de los pasos. Con los datos del run
(199.6 interacciones inválidas, 15.3 choques y 400 pasos por episodio de la política aleatoria) el castigo de explorar se reparte así:
inválidas ≈ −399 (77%), choques ≈ −77 (15%), tiempo y batería ≈ −42 (8%); quedarse quieto cuesta ≈ −41. La hipótesis a probar
es que la penalización por interacción inválida (−2) domina el costo de explorar. Para poder probarla sin reescribir el código en cada
experimento, los coeficientes se leen del YAML del run.

## Qué es nuevo
- `envs.reward_config(overrides)`: parte de los coeficientes del mapa (iguales a v1/v2) y cambia solo los indicados.
- `envs.make_env(..., reward_overrides=...)`, `pipelines.train` (bloque `recompensa:` del YAML) y `pipelines.evaluate(reward_overrides=...)`.
- El bloque `recompensa` se registra en `config_sha256`, en `metadata.json` (`reward_overrides`, `rewards`) y en MLflow (tag `recompensa`).
- Validación: claves desconocidas, premios negativos, tiempo ≥ 0 o penalizaciones positivas se rechazan. Una prueba comprueba que repetir
  CARGAR/DESCARGAR/SUBIR/BAJAR inválidos siga dando retorno negativo con penalización −2, −0.2, −0.05 y 0.

## Reglas de comparación
Mismos coeficientes → se puede comparar el retorno. Coeficientes distintos → solo la tasa de éxito, los pasos, la batería, los choques y las
interacciones inválidas en la misma suite (`suite-m1-v1`). Cada experimento cambia **una** dimensión respecto del control.

## Experimentos de esta versión
Ver `docs/experimentos.md` (sección «Barrido de penalización por interacción inválida»): control `m1-c0b`, y `m1-r1`, `m1-r2`, `m1-r3`
con `invalid_interaction` = −1, −0.2 y −0.05. Pendientes en esta versión: bonos por sub-pasos pagados una vez por línea y penalización de choques.
