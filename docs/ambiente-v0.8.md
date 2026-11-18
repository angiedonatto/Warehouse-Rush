# Warehouse Rush — ficha del ambiente v0.8 (`warehouse-v8`)

Cambios respecto de [ambiente-v0.7.md](ambiente-v0.7.md): se añade **un término** de recompensa, `face_bonus` (por defecto 0; con 0, v8 se comporta como v7, verificado por prueba). Observación `Box(27)`, acciones `Discrete(8)`, mapas, presupuesto y pedidos no cambian. Contrato: [`envs/CONTRATO.md`](../envs/CONTRATO.md). La etiqueta `env/warehouse-v7` conserva el código anterior.

## Por qué
En el mapa con muro (`layout_v0.4`, nivel `m1`) `m1-e4l`, `m1-c0l` y 2 de 3 semillas de `m1-e4x` (600 000 y 1 800 000 pasos) nunca llegan a mirar al estante: 0/50 episodios con «miró al estante» (e4l-seed0/1, c0l-seed0/1), o se quedan en giros/inválidas (e4x-seed0). Solo `m1-e4x-seed2` descubre la cadena. El primer paso de la cadena (llegar a una celda de interacción **mirando** a la estación) no tiene señal propia.

## Término: `face_bonus` (≥ 0)
`c_cara` se paga **una vez por estación objetivo y episodio**, la primera vez que el robot está en una celda de interacción (distancia BFS 0) de la estación objetivo del paso y la tiene justo delante (celda frontal = estación).
- No se paga por tramo sino por estación y episodio: recoger/soltar repetidamente, salir y volver, quedarse quieto o girar no vuelven a pagar. Máximo total = `c_cara` × nº de estaciones distintas que sean objetivo (≈ 4 con 3 productos: hasta 3 estantes + despacho).
- No exige altura de bandeja correcta ni acción: solo posición y orientación. Se evalúa tras el movimiento y antes de la interacción, con el objetivo previo.

## Medición previa con conductas guionizadas (mapa con muro, 20 semillas 10000–10019, recompensa de e4; no son resultados de un modelo)
| `face_bonus` | quieto en la base | ir al estante, mirarlo y quedarse | completar el pedido (heurística) |
|---:|---:|---:|---:|
| 0 | −40.8 | −47.8 | 128.8 |
| 5 | −40.8 | −42.8 | 147.8 |
| **10** | −40.8 | **−37.8** | 166.8 |

Con 5 ir y mirar y quedarse seguiría costando más que quedarse en la base (zona de evitación, como `height_mismatch` en e2/e3); con 10 ya compensa (+3). Se usa **10.0** (igual al pago de `pickup`).

## Límites conocidos (declarados antes de entrenar)
- Solo premia llegar y mirar; no la altura ni la carga. Puede producir políticas que miran y se quedan (−37.8 > idle −40.8, pero < −26.3 de recoger el 1.º y quedarse).
- Pago único por estación: no ayuda a la segunda línea del mismo estante.
- No cambia los atascos tras cargar (para eso está `carry_milestone`).

## Pruebas
`tests/test_reward_config.py` (sección v8): apagado por defecto y signo validado; con 0 el retorno guionizado es idéntico y con 10 solo suma un pago por estación (heurística, ambos mapas); no es explotable quedándose quieto ni girando.
