# Warehouse Rush — ficha del ambiente v0.7 (`warehouse-v7`)

Cambios respecto de [ambiente-v0.6.md](ambiente-v0.6.md): se **retira** `lower_bonus` (v6) y se añade **un término** nuevo, `carry_milestone` (por defecto 0; con 0, v7 se comporta como v5, verificado por prueba).
Observación `Box(27)`, acciones `Discrete(8)`, mapas, presupuesto y pedidos de 3 productos no cambian. Contrato: [`envs/CONTRATO.md`](../envs/CONTRATO.md).
Las etiquetas `env/warehouse-v5` y `env/warehouse-v6` conservan el código de e4l y de f1–f3.

## Por qué
Los runs f1–f3 (v6, ver `docs/experimentos.md`) mostraron que el bono por bajar la bandeja cumple su función (suben, cargan y bajan la bandeja en 50/50 episodios) pero **ninguno entregó** (0 entregas en ≈ 7 600 episodios de entrenamiento):
tras bajar la bandeja el agente gira en el sitio en lugar de avanzar al despacho. El único término que paga el tramo con carga es la diferencia Manhattan (0.3 por celda), que no basta. Además `time` −0.2 no acortó los éxitos y redujo el éxito. Por eso v7 vuelve a `time` −0.1,
retira `lower_bonus` (instrucción del equipo) y paga un hito en ese tramo.

## Término: `carry_milestone` (≥ 0)
`c_hito` se paga **una vez por tramo de entrega**, la primera vez que la distancia BFS al despacho (celdas de acceso) es ≤ la mitad de la que había al empezar el tramo.
- El tramo empieza en el primer paso con objetivo DELIVERY y se reinicia al cambiar de objetivo (por ejemplo tras una entrega parcial por capacidad).
- Un tramo exige una recogida, luego el máximo total es un hito por recogida que lleve a un tramo nuevo (≤ nº de tramos por pedido).
- Alejarse y volver no vuelve a pagar (bandera por tramo); con la bandeja arriba el robot no se mueve, así que el hito solo se cobra después de bajarla y de recorrer ≥ la mitad del camino.
- Se evalúa con el objetivo previo y la distancia BFS al mismo objetivo antes/después del paso, como el progreso.

## Objetivo tras la última recogida (verificado en v6, sin cambio de código)
Al recoger la última línea no quedan pendientes y, al llevar carga, `_assign_next_target` fija `objetivo = DELIVERY`, `etapa = entregar`: la observación (índices 10–11), la distancia BFS y la Manhattan apuntan al despacho desde ese paso.
Lo fija `test_after_the_last_pickup_the_target_is_the_delivery_point`.

## Límites conocidos (declarados antes de entrenar)
- El hito solo existe con objetivo DELIVERY. Tras una recogida intermedia el siguiente tramo (hacia otro estante) no tiene hito.
- Es una señal única de 5 puntos (frente a 10/30/50 de los hitos existentes): puede ser insuficiente si el atasco no es de señal sino de política (giros en el sitio).
- El hito premia recorrer la mitad del camino, no entregar; la entrega la sigue pagando `delivery`/`completion`.

## Pruebas
`tests/test_reward_config.py` (sección v7): apagado por defecto, signo validado y `lower_bonus` rechazado; el objetivo apunta al despacho tras la última recogida; el hito se paga una sola vez, a la mitad o más del camino y nunca antes; no es explotable oscilando; sin hito con objetivo en un estante;
con `carry_milestone` = 0 el retorno guionizado es idéntico al de v5; los configs f1–f3 se leen como historia (v6) y los g1 cambian solo el hito.
