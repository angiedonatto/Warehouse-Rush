# Warehouse Rush — ficha del ambiente v0.9 (`warehouse-v9`)

Cambios respecto de [ambiente-v0.8.md](ambiente-v0.8.md): se añade el término `potential` (shaping basado en potencial, un solo peso W, por defecto 0; con 0, v9 es idéntico a v8, verificado por prueba) y el método `potential()` del ambiente. Observación `Box(27)`, acciones `Discrete(8)`, mapas, presupuesto y pedidos no cambian. Contrato: [`envs/CONTRATO.md`](../envs/CONTRATO.md). `env/warehouse-v8` conserva el código con `face_bonus` y los runs j1–j3.

## Por qué
El shaping de v5–v8 creció término a término (`progress`, `manhattan_progress`, `height_mismatch`, `carry_milestone`, `face_bonus`): en una misión perfecta con la recompensa de j1 el shaping valía ≈ 66 de 166.8 puntos (40%), con dos términos que miden lo mismo (`progress` BFS y `manhattan_progress`) y zonas de evitación (ir y mirar el estante y quedarse, −37.8 > quieto −40.8 solo por el bono de 10 y la penalización de altura). Un potencial por etapas reemplaza todos con un solo peso y no crea esas zonas.

## Término: `potential` (W ≥ 0)
Recompensa por paso: `W · (γ·Φ(s') − Φ(s))`, con γ = 0.99 (`POTENTIAL_GAMMA`, el gamma de PPO de todos los configs; si cambia, la invariancia se rompe) y Φ(s) ∈ [0,1] función **solo del estado** (`MakeupMissionEnv.potential()`), sin historia. Resultado de Ng, Harada y Russell (1999): el shaping basado en potencial no cambia la política óptima; con W = 30 la ganancia total de potencial en una misión es una unidad de W.

`Φ(s) = (K + φ) / (2n)`, con `n` líneas del pedido y `K` = líneas recogidas + líneas entregadas (0…2n). `φ ∈ [0,1]` mide el avance del tramo actual hacia su objetivo (estante o despacho):
| Parte | Peso | Cuándo |
|---|---:|---|
| bandeja guardada mientras se viaja | 0.10 | nivel 0, o ya en la celda de interacción (subirla no resta) |
| navegación | 0.40 | `1 − d/d_max`, d = distancia BFS a la celda de interacción del objetivo |
| mirar la estación | 0.20 | en la celda de interacción y con la estación justo delante |
| altura de la bandeja | 0.30 | mirando: `1 − |nivel − exigido| / 3` (exigido 0 al entregar) |
Sin objetivo (misión completa) φ = 0 y Φ = 1. Φ ya incluye `K`, así que recoger y entregar quedan encadenados sin saltos negativos; el potencial de la heurística es monótono y termina en 1.

## Parada por estancamiento (solo entrenamiento, no es parte del ambiente)
`pipelines/train.py::StagnationStop`, activada con la clave YAML `parada_estancamiento: N`: trunca (`truncated`, no `terminated`, así PPO hace bootstrap) tras N pasos sin superar el mejor Φ del episodio. Se aplica únicamente a los ambientes de entrenamiento; las suites, `evaluate.py` y la evaluación periódica usan el ambiente sin envolver con 400 pasos. Medido antes de entrenar (mapa con muro): la heurística nunca pasa más de 2 pasos sin mejorar Φ; los éxitos de `m1-e4x-seed2` con acciones muestreadas, ≤ 49 (p95 30); los episodios atascados de `m1-j1-seed0`, ≈ 384. N = 100.

## Mediciones previas con conductas guionizadas (mapa con muro, 10 semillas, retorno **descontado** γ = 0.99, W = 30; no son resultados de un modelo)
| Conducta | W = 0 | W = 30 |
|---|---:|---:|
| quieto en la base | −10.0 | −11.4 |
| ir, mirar el estante y quedarse | −10.2 | −11.6 |
| recoger el 1.º y quedarse | −2.0 | −3.3 |
| pedido completo | 50.6 | 62.4 |
El orden de las conductas no cambia (invarianza): ir y mirar y quedarse sigue sin superar a quedarse quieto, así que no hay zona de evitación nueva ni conducta que se vuelva rentable por el shaping. El retorno **no descontado** del shaping sí es negativo al quedarse en un estado de potencial alto (fuga (γ−1)Φ por paso), por lo que el retorno sin descontar de la evaluación no es comparable con el de v8.

## Límites conocidos (declarados antes de entrenar)
- La invarianza conserva el óptimo, no garantiza que PPO lo encuentre antes: es una hipótesis.
- Φ usa el BFS (privilegiado) solo en la recompensa; la política sigue viendo solo `Box(27)`.
- Los pesos internos de φ (0.10/0.40/0.20/0.30) son una elección de diseño, sin ajustar con resultados.
- `K` suma recogidas y entregas por igual; un pedido con pocas líneas tiene saltos mayores por etapa.

## Pruebas
`tests/test_reward_config.py` (sección v9): apagado por defecto y signo; γ igual al de PPO; Φ ∈ [0,1], 1 al terminar con éxito; suma descontada exacta `W(γ^T Φ_T − Φ_0)`; con W = 0 el retorno es idéntico; no se puede explotar quedándose quieto ni girando y volviendo. `tests/test_stagnation.py`: trunca (no termina) a los 100 pasos, el contador se reinicia, la heurística nunca se corta y el config se valida.
