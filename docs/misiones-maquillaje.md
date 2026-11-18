# Misiones de maquillaje — dev/angie

El visor local (`warehouse-rush view --no-open`) inicia pedidos automáticos de 1–3 SKUs temporales. «Generar pedido» crea y reserva otro pedido usando la semilla visible y el stock disponible; no repone inventario. El modo maquillaje usa el escenario amplio v0.4: conserva las seis categorías y estructuras de estantería, con posiciones y pasillos más separados. El escenario v0.1 conserva sus posiciones originales para entrenamiento y compatibilidad. Seleccionar una etiqueta E01–E06 o el selector muestra los tres niveles y sus existencias. El checklist consume cantidades confirmadas por Python; no permite marcar manualmente las líneas.

## Modelo y operaciones

`inventory.py` contiene el catálogo provisional, separado de Three.js. Cada nivel tiene un SKU temporal de cinco unidades iniciales. `Inventory.reserve` valida todas las líneas bajo un bloqueo y reserva todo o rechaza todo. Un ID repetido con las mismas líneas devuelve la orden existente; con otro contenido se rechaza. `pick` exige cantidades exactas, descuenta una vez, y libera reserva. `deliver` confirma sin descontar. Repetir recogida/entrega no genera eventos ni movimientos adicionales. Cancelación/fallo libera lo no recogido y registra `pending_return` para carga no entregada. No hay reposición implícita ni eliminación del historial.

El generador devuelve directamente la orden reservada, con eventos GENERATED y RESERVED (o REJECTED para solicitudes directas sin stock). El estado IN_TRANSIT corresponde a carga en el robot; PICKING indica que quedan líneas después de una descarga; DELIVERED requiere todas las líneas entregadas. CANCELLED/FAILED/REJECTED cierran la orden. Eventos incluyen tiempo simulado; ID UUID independiente de la semilla, líneas reproducibles para igual stock y semilla.

`MakeupMissionEnv` añade estaciones de interacción sobre la cara norte de los racks y valida su accesibilidad con y sin bloqueo. No añade obstáculos ni permite atravesarlos. Interactuar exige adyacencia, orientación correcta y velocidad cero. La transferencia se realiza con una bandeja de rodillos sobre una plataforma telescópica; sólo puede recoger a la altura del nivel solicitado y baja antes de desplazarse. Capacidad predeterminada: 3 unidades; el generador limita cada línea a esa capacidad. El robot reúne varias líneas en los estantes antes de ir a despacho mientras quepan en su capacidad; si no caben, descarga y continúa con las líneas pendientes. `cargo_lines` contiene los SKUs y cantidades físicas transportadas. La recompensa de entrega se aplica una vez por interacción de descarga, aunque descargue varias líneas; no cambia la función ni sus coeficientes.

La invariancia comprobada es: stock inicial = stock físico restante + unidades recogidas acumuladas; reservas <= stock físico; entregadas <= recogidas <= solicitadas. La carga pendiente de devolución sigue fuera del estante. No se implementó una operación de devolución física.

El inventario se mantiene en la sesión local, incluido al generar pedidos sucesivos. Reiniciar el proceso inicia un almacén nuevo: no hay persistencia durable. El adaptador stateless conserva el libro por visitante en cookie comprimida y firmada; no representa stock compartido entre visitantes. Conserva cookies legacy. Al exceder su límite de 3800 caracteres falla explícitamente, sin truncar trazabilidad. Para producción con historial extenso o stock compartido hará falta almacenamiento servidor; no se incorpora una base externa en esta tarea.

## Compatibilidad — Lis / Naomi

`WarehouseRushEnv` y el entrenamiento no cambian. El modo legacy sigue disponible desmarcando «Pedidos de maquillaje»; la API usa `makeup: true` para solicitar el nuevo modo. PPO recibe únicamente el mismo vector de 22 valores y las mismas cinco acciones. En maquillaje cambian la distribución de objetivos a estanterías y el progreso de entregas se normaliza por líneas (1–3); no se añaden observaciones de SKU, nivel ni cantidad. Los coeficientes de recompensa y el presupuesto de batería/pasos son los existentes; el elevador añade consumo físico, penalizado con el mismo coeficiente de batería. No se entrenó ni reentrenó ningún modelo. Los checkpoints legacy pueden cargarse, pero no se garantiza su rendimiento en estos nuevos objetivos. La ruta BFS visual no elige acciones PPO.

Naomi puede sustituir el catálogo provisional cuando entregue productos y assets. No se añadieron imágenes comerciales ni se reconstruyeron sus modelos; las etiquetas y el panel de inventario son capas de interfaz.

## Ejecutar

```sh
cd /workspace/Warehouse-Rush
source .venv/bin/activate
npm --prefix web ci
npm --prefix web run build
warehouse-rush view --no-open
```

En otra terminal, con el visor ejecutándose:

```sh
.venv/bin/python -m pytest -q
.venv/bin/python -m pytest tests/test_inventory_missions.py -k full_lip -s
CHROMIUM_PATH=/usr/bin/chromium npm --prefix web test
```

El repositorio no define un script de lint. El build de Vite comprueba el bundle; pytest valida contratos legacy, inventario, bloqueo, idempotencia, cookies y misiones integrales. Los tests de navegación incluyen 24 combinaciones de semilla/bloqueo con presupuesto explícito de 300 de batería y 600 pasos para cubrir tres viajes sin alterar defaults. La prueba de aceptación Labios usa el presupuesto normal y capacidad explícita 4: inicial 5, reserva 4, recogida 4, entrega 4, final 1.

La escena usa el fondo azul oscuro original. En modo maquillaje se ocultan las estaciones legacy P1/P2 y sus paquetes; el despacho empieza vacío. Cada unidad temporal aparece sobre su nivel y desaparece únicamente cuando el inventario confirma su recogida. Los mismos SKUs se muestran sobre el robot durante el transporte y sobre la zona de despacho al entregar. No se usan cajas decorativas como inventario.


## Alcance vertical y decisiones de viaje

Se eligió un elevador telescópico con bandeja de rodillos en lugar de un brazo: los productos tienen ubicaciones fijas y no hay modelos de agarre ni pesos definitivos. El mecanismo añade alcance vertical, no una pinza universal. La transferencia horizontal sobre la bandeja sigue siendo una operación automática simplificada (el estante debe estar preparado para entregarla); no simula dedos, agarre ni empaquetado. Es una simulación logística, no una validación mecánica de hardware.

Las tres baldas de almacenamiento son las tres superiores de la geometría existente: alturas de transferencia 0.99, 1.79 y 2.60 m. La balda de base queda como soporte estructural. La plataforma viaja a 0.55 m; velocidad vertical 0.40 m por paso de 1 s; consumo 0.80 unidades de batería por metro vertical, tanto al subir como al bajar. La plataforma sólo inicia el ciclo con el robot detenido, adyacente y orientado hacia el estante. Se bloquean avance y giro durante subida, transferencia y bajada. INTERACTUAR inicia la elevación y, cuando alcanza la altura, confirma la recogida. No se descuenta stock antes. FRENAR mientras está lista permite abortar y bajar sin recoger. No se puede descargar con la plataforma levantada.

Cada ciclo registra LIFT_START, LIFT_READY, PICK, LIFT_LOWERING y LIFT_STOWED con tiempo simulado. `state.lift` incluye altura, destino vertical, fase, energía, movimientos bloqueados y número real de visitas a despacho. Se conserva al recargar mediante el adaptador firmado, incluso a mitad de elevación. La visualización interpola la altura confirmada sin adelantar recogidas.

El despachador de misiones ordena candidatos por distancia navegable más pasos de elevación, respetando capacidad. Antes de recoger estima desplazamiento al producto y a despacho, ciclos verticales, bajada pendiente, 12 pasos de margen para orientación/transferencia y reserva de 5 unidades de batería. Se reevalúa tras cada recogida. Si lleva carga y no cabe otro producto, vuelve por capacidad; si no queda margen estimado de batería/tiempo, vuelve con lo recogido. Si está vacío y no puede iniciar un viaje de ida y vuelta según ese presupuesto, termina con `insufficient_budget` y libera reservas; no repone batería mágicamente. No se ha implementado estación de carga. La estimación es conservadora y no garantiza retorno de una política aleatoria o PPO que se desvíe. No busca una solución global óptima al problema de rutas.

Estas decisiones del despachador y el enclavamiento del elevador son reglas explícitas del entorno, no decisiones aprendidas por PPO. La heurística espera con FRENAR durante subida/bajada; Random y PPO conservan sus acciones propias y se someten al mismo bloqueo físico. El entrenamiento sigue intacto y el vector legacy sigue teniendo 22 valores. Para Lis: el modo maquillaje ahora tiene tiempos de servicio, consumo extra e inhibición de movimiento mientras se eleva; altura/fase no están en el vector legacy, por lo que el modelo existente no observa todo ese estado. Un experimento PPO específico debe decidir si amplía observaciones y versiona el checkpoint; no se entrenó ni se modificó su entrenamiento aquí.


## Bodega amplia y señalización integrada (v0.3)

La distribución amplia está en `configs/layout_v0.3.json`; los pedidos nuevos usan su variante con empaque `configs/layout_v0.4.json`: 25 × 19 celdas de 1 m, frente a 17 × 13 del escenario original. Se mantienen seis estanterías de dos por dos celdas, con cinco celdas transitables entre columnas, cuatro entre filas y mayor margen perimetral. Base y despacho tienen una franja propia, separada por la barrera con dos accesos; bloquear uno mantiene la ruta alternativa. La lógica de colisiones y el visor consumen las mismas coordenadas del mapa, sin escalado visual que permita atravesar estructuras.

Las distancias mayores usan un presupuesto de episodio propio del escenario de maquillaje: 180 unidades de batería y 400 pasos. Costes por acción, velocidad, elevador, radio de interacción y capacidad no cambian. El entorno Gymnasium legacy y su mapa siguen usando 100 unidades y 250 pasos. No se retocó ningún entrenamiento ni checkpoint. El vector conserva 22 valores, pero las distancias relativas y la distribución de objetivos son distintas en el mapa amplio: no se atribuye generalización al PPO existente sin medirla en un experimento separado.

La categoría aparece en un único rótulo rígido sobre el estante, legible desde ambas caras. Cada balda tiene una banda frontal y trasera con su subcategoría. Son superficies Three.js con profundidad, luz y oclusión reales; no siguen a la cámara ni contienen cantidades, reservas o listados de SKUs. Los tonos de las placas y vigas son rosa empolvado y neutros claros sobre el fondo oscuro existente. Se elimina todo rótulo DOM flotante de estantería y nivel. El detalle del inventario queda en el panel lateral. Un clic sobre la estructura, o el selector del panel, cambia el estante consultado; la cámara de detalle muestra ese mismo estante.

Los snapshots firmados registran `layout_version`. Las cookies anteriores, sin ese campo, continúan en v0.1 con el mismo estado, autonomía y posiciones; las de v0.3 conservan también su geometría. Al generar un nuevo pedido cambian a v0.4, conservando el inventario de la sesión. `/api/layout` devuelve el mapa de la sesión firmada; el frontend reconstruye la escena cuando cambia el hash del mapa. Esto evita que un robot simulado en un mapa se dibuje sobre otro.


## Despacho sobre cinta y caja (v0.4)

El despacho ocupa dos celdas reservadas `(22,16)` y `(23,16)` en la esquina. El punto de descarga es `(21,16)`, mirando hacia el este; no se acepta una entrega desde otro lado ni se permite atravesar la mesa. `dispatch_area` forma parte del mapa compartido por sensores, búsquedas, colisiones y visor. Las sesiones v0.1/v0.3 siguen con sus huellas originales hasta iniciar otro pedido. La vista ofrece entonces una caja compacta elevada, sin extender una cinta sobre celdas que eran transitables en esos mapas.

La cinta tiene bastidor, patas, rodillos, superficie móvil y una entrada alineada con la bandeja del robot. Su superficie queda a 0.62 m, con una pequeña rampa de recepción desde la altura de transporte de 0.55 m. Al final hay una caja rosa con interior claro y papel, apoyada sobre una mesa; los marcadores terminan dentro de ella a 0.47 m del suelo. Ninguna unidad entregada se dibuja sobre el piso. La tapa con lazo se cierra al terminar el empaque visual del pedido completo.

El evento real DELIVER dispara la secuencia visual: transferencia desde el robot → cinta → interior de caja → cierre. DELIVERED sigue significando entrega confirmada a la estación receptora; no se añade una nueva transición Gym ni un segundo descuento de stock. El panel distingue esa entrega de «Cinta en marcha», «Cerrando la caja» y «Caja preparada». El tiempo del efecto es de presentación, no modifica el reloj, acciones, recompensas ni consumo físico del episodio. Se usa tiempo de reloj monotónico para que una tasa de cuadros baja no deje el empaque detenido.

La cola visual usa pares SKU/índice de unidad y no duplica productos ante payloads repetidos. Al recargar se reconstruyen las unidades ya entregadas dentro de la caja y no se repite la entrega. Una orden parcial mantiene la caja abierta hasta recibir lo que falta. Generar otro pedido limpia la estación visual (se asume retirada de la caja anterior), conservando el historial de inventario y entregas. «Ver despacho» y un clic sobre la propia estación permiten acercar la cámara sin cambiar la misión ni la selección del inventario lateral.

La caja representa el pedido activo con marcadores provisionales. No hay integración con transportistas, pagos, embalaje de productos reales ni simulación física de cinta o caída: es la representación visual solicitada, ligada a las entregas reales del simulador. El entrenamiento PPO y el mapa v0.1 permanecen intactos; en v0.4 sólo cambia el acceso válido a la estación receptora, sin ampliar el vector de observación ni las acciones.
