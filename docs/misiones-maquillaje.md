# Misiones de maquillaje — dev/angie

El visor local (`warehouse-rush view --no-open`) inicia pedidos automáticos de 1–3 SKUs temporales. «Generar pedido» crea y reserva otro pedido usando la semilla visible y el stock disponible; no repone inventario. Las seis estanterías conservan posición, geometría y colisiones. Seleccionar una etiqueta E01–E06 o el selector muestra los tres niveles y sus existencias. El checklist consume cantidades confirmadas por Python; no permite marcar manualmente las líneas.

## Modelo y operaciones

`inventory.py` contiene el catálogo provisional, separado de Three.js. Cada nivel tiene un SKU temporal de cinco unidades iniciales. `Inventory.reserve` valida todas las líneas bajo un bloqueo y reserva todo o rechaza todo. Un ID repetido con las mismas líneas devuelve la orden existente; con otro contenido se rechaza. `pick` exige cantidades exactas, descuenta una vez, y libera reserva. `deliver` confirma sin descontar. Repetir recogida/entrega no genera eventos ni movimientos adicionales. Cancelación/fallo libera lo no recogido y registra `pending_return` para carga no entregada. No hay reposición implícita ni eliminación del historial.

El generador devuelve directamente la orden reservada, con eventos GENERATED y RESERVED (o REJECTED para solicitudes directas sin stock). El estado IN_TRANSIT corresponde a carga en el robot; PICKING indica que quedan líneas después de una descarga; DELIVERED requiere todas las líneas entregadas. CANCELLED/FAILED/REJECTED cierran la orden. Eventos incluyen tiempo simulado; ID UUID independiente de la semilla, líneas reproducibles para igual stock y semilla.

`MakeupMissionEnv` añade estaciones de interacción sobre la cara norte de los racks y valida su accesibilidad con y sin bloqueo. No añade obstáculos ni permite atravesarlos. Interactuar exige adyacencia, orientación correcta y velocidad cero. La transferencia de nivel es automática, sin brazo. Capacidad predeterminada: 3 unidades; el generador limita cada línea a esa capacidad. Se realiza un viaje por línea (sin optimización de agrupación).

La invariancia comprobada es: stock inicial = stock físico restante + unidades recogidas acumuladas; reservas <= stock físico; entregadas <= recogidas <= solicitadas. La carga pendiente de devolución sigue fuera del estante. No se implementó una operación de devolución física.

El inventario se mantiene en la sesión local, incluido al generar pedidos sucesivos. Reiniciar el proceso inicia un almacén nuevo: no hay persistencia durable. El adaptador stateless conserva el libro por visitante en cookie comprimida y firmada; no representa stock compartido entre visitantes. Conserva cookies legacy. Al exceder su límite de 3800 caracteres falla explícitamente, sin truncar trazabilidad. Para producción con historial extenso o stock compartido hará falta almacenamiento servidor; no se incorpora una base externa en esta tarea.

## Compatibilidad — Lis / Naomi

`WarehouseRushEnv` y el entrenamiento no cambian. El modo legacy sigue disponible desmarcando «Pedidos de maquillaje»; la API usa `makeup: true` para solicitar el nuevo modo. PPO recibe únicamente el mismo vector de 22 valores y las mismas cinco acciones. En maquillaje cambian la distribución de objetivos a estanterías y el progreso de entregas se normaliza por líneas (1–3); no se añaden observaciones de SKU, nivel ni cantidad. Las recompensas y el presupuesto de batería/pasos son los existentes. No se entrenó ni reentrenó ningún modelo. Los checkpoints legacy pueden cargarse, pero no se garantiza su rendimiento en estos nuevos objetivos. La ruta BFS visual no elige acciones PPO.

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
