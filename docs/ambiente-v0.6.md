# Warehouse Rush — ficha del ambiente v0.6 (`warehouse-v6`)

Cambios respecto de [ambiente-v0.5.md](ambiente-v0.5.md): la recompensa gana **un término** (`lower_bonus`, por defecto 0, es decir, v6 sin él se comporta como v5; verificado por prueba).
Observación `Box(27)`, acciones `Discrete(8)`, mapas, presupuesto y pedidos de 3 productos no cambian. Contrato: [`envs/CONTRATO.md`](../envs/CONTRATO.md).
La etiqueta `env/warehouse-v5` conserva el código de e1–e5 y de `m1o-e4l`.

## Por qué
El diagnóstico de `m1o-e4l` mostró que los runs que fallan se quedan sin bajar la bandeja o sin completar el viaje tras cargar, y que en el único modelo que funciona (seed 0) los episodios exitosos duran lo mismo que la heurística (71.8 pasos
frente a 71.3): los episodios largos son los fallidos (3 de 4 fallos agotan los 400 pasos). Con la bandeja arriba el robot no puede moverse, así que bajarla es obligatorio para entregar; el término de altura de v5 no lo empuja
(solo actúa en la celda de interacción del objetivo actual).

## Término nuevo: `lower_bonus` (≥ 0)
`c_baj · L`, con `L` = puestos que BAJAR baja la bandeja en este paso, solo si **antes de la acción**:
1. el objetivo es DELIVERY (ya se recogió todo lo que se entregará; ver «Objetivo tras la última recogida»),
2. la distancia BFS al despacho es > 0 (todavía no se está en la celda de entrega), y
3. la bandeja estaba por encima de 0.

**Una vez por tramo y puesto.** Se guarda el puesto más bajo ya alcanzado en el tramo (`_delivery_floor`); si el agente sube de nuevo y vuelve a bajar, no cobra otra vez. Sin esto, SUBIR/BAJAR repetidos serían un bucle rentable
(SUBIR en el tramo de entrega es válido en los puestos 1–3). El máximo por tramo es 3·c_baj. El tramo se reinicia al salir de objetivo DELIVERY (por ejemplo tras una entrega parcial por capacidad).

## Objetivo tras la última recogida (verificado, sin cambio de código)
Al recoger la última línea, `_assign_next_target` no encuentra líneas pendientes y, al llevar carga, fija `objetivo = DELIVERY`, `etapa = entregar`. Por tanto la observación (índices 10–11: x, y del objetivo normalizadas),
la distancia BFS (`route_distance`) y la Manhattan (`manhattan_to`) apuntan al punto de entrega desde ese mismo paso. También pasa si lo pendiente no cabe por capacidad o no es factible por batería/tiempo.
Lo fija `test_after_the_last_pickup_the_target_is_the_delivery_point` (10 semillas, mapa abierto).

## Límites conocidos (declarados antes de entrenar)
- El bono solo actúa con objetivo DELIVERY. Tras una recogida intermedia (el objetivo es otro estante) bajar la bandeja, igualmente obligatorio para moverse, no cobra bono; solo lo empuja la diferencia Manhattan.
- Aumentar `time` (−0.1 → −0.2) cambia la escala del retorno: los retornos no se comparan con e4l; se compara éxito, pasos de los éxitos, fallos por límite de tiempo, inválidas y choques.
- Puede inducir bajar la bandeja demasiado pronto, antes de entrar en la zona de entrega; es correcto (es obligatorio para moverse) pero no se mide si ayuda a entregar.

## Pruebas
`tests/test_reward_config.py` (sección v6): apagado por defecto y signo validado; el objetivo apunta al despacho tras la última recogida (obs, etapa, distancias); paga por puesto, solo lejos del despacho y una vez; SUBIR/BAJAR no es explotable;
sin bono con objetivo en un estante; con `lower_bonus = 0` el retorno de un episodio guionizado es idéntico a v5. Los tests de configs v5 leen los YAML como datos (`raw`) porque `load_config` rechaza otra versión.
