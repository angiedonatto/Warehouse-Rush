> Catálogo operativo autorizado por Naomi tras el visto bueno de Angie: las sesiones nuevas utilizan los 27 SKU TRD de `configs/products.json`, con la distribución acordada y stock fijo de 5–10 unidades. Los libros TMP antiguos se conservan sin conversión ni reposición. Esta actualización sustituye las referencias históricas a 18 productos provisionales. Ver [catálogo operativo](docs/catalogo-operativo.md). Trabajar y subir únicamente en `dev/naomi`, sin desplegar en producción.

# Warehouse Rush — guía de trabajo y relevo de Naomi

> Actualización de `dev/naomi`: Naomi autorizó expresamente integrar y subir aquí su interfaz rosa y el catálogo visual de 27 productos, conservando los mecanismos de Angie. En esta rama, esa autorización sustituye las referencias históricas a trabajar sólo en `dev/angie` y a conservar fondo oscuro. Los 18 SKU operativos TMP y sus transacciones permanecen estables; los TRD identifican assets y propuestas visuales. Ver [integración rosa](docs/integracion-rosa.md). No publicar automáticamente en Vercel desde esta rama.

Este archivo aplica a todo el repositorio. Está escrito para las integrantes del equipo y para cualquier agente de código que las ayude. Leerlo antes de editar. Las instrucciones expresas del usuario y las instrucciones de mayor prioridad prevalecen sobre esta guía; no usarla para bloquear trabajo que ya esté autorizado explícitamente.

**Objetivo del relevo:** Naomi puede desarrollar productos y presentación visual sin perder el simulador, las misiones, el inventario ni las integraciones existentes. Trabajar sobre la implementación actual, con cambios pequeños y revisables. No reconstruir el proyecto desde cero.

## 1. Referencia del proyecto y qué significa «actualizado»

- Repositorio: `https://github.com/angiedonatto/Warehouse-Rush`.
- Rama autorizada en este relevo: **`dev/angie`**. No modificar `main` ni ramas de otras integrantes.
- No crear `dev/naomi`, otra rama compartida o un worktree por deducción del nombre de la integrante. Si Angie autoriza otra rama, adaptar todos los comandos a esa rama concreta.
- En Codex Cloud, usar el checkout existente: la tarea ya está aislada. No crear worktrees por defecto.
- Producción: **https://warehouse-rush-experiment-001.vercel.app**.
- Estado público comprobable: **https://warehouse-rush-experiment-001.vercel.app/api/health**.
- Proyecto de Vercel: `warehouse-rush-experiment-001`.
- Equipo de Vercel: `angiedonato2-7290s-projects`.
- Referencia funcional de este relevo: **`9bc63d45ba5b56678a1af55560c98f99092b8863`**, con cinta de empaque y caja pastel. Es una referencia histórica comprobada, no un SHA para fijar en código ni para restaurar automáticamente.

**GitHub almacena el código; Vercel ejecuta una versión publicada.** No existe un `git pull` desde la URL de producción. Se trae el código de GitHub y se compara con el commit que informa producción. Un push a GitHub no demuestra que Vercel se haya actualizado.

El README y algunos documentos describen el experimento inicial v0.1/v0.2. Para las funcionalidades nuevas leer también [docs/misiones-maquillaje.md](docs/misiones-maquillaje.md). No retirar inventario, elevador o empaque porque un documento histórico no los mencione.

## 2. Responsabilidades y límites

| Área | Trabajo de Naomi | Condición |
| --- | --- | --- |
| Selección de productos | Proponer productos definitivos, referencias y organización visual | Mantener el catálogo temporal hasta confirmar los datos. Coordinar con Angie la integración de altas, bajas o cambios de SKU. |
| Modelado y assets 3D | Exportar modelos, texturas, materiales, empaques y props aprobados | Respetar escala, ejes, pivotes, alturas y huellas físicas. Conservar un fallback mientras carga un modelo. |
| Look & feel | Colores, tipografía, composición, iluminación, placas y apariencia de productos | Conservar los controles, la legibilidad y las conexiones con datos reales. |
| Categorías visuales | Mejorar la presentación y proponer nombres definitivos | No romper IDs, ubicaciones, reservas, pedidos guardados ni asociaciones SKU/nivel. |
| Robot y mecanismos | Mejorar su apariencia y sus accesorios visuales | Mantener movimiento, plataforma, alturas y estados recibidos del simulador. |
| Inventario, misiones y API | Fuera del alcance visual por defecto | Coordinar cambios funcionales con Angie; no reemplazar Python por una simulación en JavaScript. |
| PPO, entrenamiento y evaluación | Responsabilidad de Lis | No entrenar, reentrenar, cambiar observaciones/acciones/recompensas ni sobrescribir checkpoints o resultados para una tarea visual. |
| Publicación de producción | Requiere autorización de Angie o de la responsable del despliegue | Un encargo visual o un push no autoriza por sí solo publicar. Si esa publicación ya fue autorizada expresamente en la tarea, no pedir la misma autorización de nuevo. |

Si un modelo nuevo exige cambiar rutas, posiciones físicas, capacidades, acciones o reglas de recogida, preparar la propuesta y el asset visual por separado. Continuar el trabajo visual independiente; no aplicar silenciosamente el cambio funcional a otra integrante.

No desarrollar tienda, carrito, pagos, transportistas o una base de datos externa como parte de este relevo visual, salvo un encargo posterior explícito.

## 3. Antes de editar: traer y comparar el código

En Codex, GitHub Desktop o el IDE, seleccionar el repositorio correcto y **`dev/angie`** al empezar. Esta guía se incorpora en esa rama: no asumir que se leerá automáticamente si se abre una copia antigua de `main`. Un snapshot de entorno tampoco sustituye el `fetch`/comparación con el remoto actual. Si aparece sólo el README inicial, comprobar la rama antes de reconstruir nada.

### 3.1 Si no tienes el repositorio

En tu terminal personal, dentro de la carpeta donde quieras guardarlo:

```bash
git clone --branch dev/angie https://github.com/angiedonatto/Warehouse-Rush.git
cd Warehouse-Rush
```

En una tarea cloud, comprobar primero `/workspace` y usar el checkout existente; no clonar otra copia encima de archivos de otra persona.

### 3.2 Si ya tienes una copia

Desde la raíz del repositorio:

```bash
git status --short
git branch --show-current
```

Si hay modificaciones o archivos nuevos, **no borrarlos para poder actualizar**. Identificar de quién son, conservarlos y resolver la actualización sin sobreescribirlos. No ejecutar `reset --hard`, `clean -fd` ni descartar carpetas completas.

Con el árbol de trabajo limpio:

```bash
git fetch origin dev/angie
git switch dev/angie
git pull --ff-only origin dev/angie
git log -1 --oneline
```

Si el checkout cloud todavía no tiene esa rama local, después de un `fetch` exitoso de `dev/angie` puede crearse la rama local desde `FETCH_HEAD`. Hacerlo solamente si no existe ya `dev/angie` local y no hay trabajo pendiente:

```bash
git switch -c dev/angie FETCH_HEAD
```

Si `pull --ff-only` falla por divergencia, no forzarlo. Conservar los commits locales y revisar la diferencia con lo remoto. No reescribir commits publicados de otras integrantes. Integrar los cambios de la compañera y volver a validar antes de subir.

### 3.3 Comprobar la versión pública

Consulta pública, sin token:

```bash
curl -fsS --max-time 30 https://warehouse-rush-experiment-001.vercel.app/api/health
```

La respuesta incluye `status` y `commit`. Para comprobar si tu rama contiene el código publicado, con Bash o zsh y Python disponible:

```bash
WAREHOUSE_PROD_COMMIT=$(curl -fsS --max-time 30 https://warehouse-rush-experiment-001.vercel.app/api/health | python3 -c 'import json,re,sys; s=json.load(sys.stdin)["commit"]; assert re.fullmatch("[0-9a-f]{40}",s), "Produccion no informa un SHA verificable"; print(s)')
git show --no-patch --oneline "$WAREHOUSE_PROD_COMMIT"
git merge-base --is-ancestor "$WAREHOUSE_PROD_COMMIT" HEAD
```

Interpretación del último comando: salida de proceso `0` significa que HEAD contiene ese commit; `1` significa que no lo contiene. Un error de Git, un SHA desconocido o un `commit` igual a `local` no prueban sincronización.

- Si producción es un ancestro de tu rama, puedes tener cambios posteriores todavía no publicados: **no volver atrás para igualar el SHA**.
- Si GitHub contiene commits de documentación posteriores al despliegue, es normal que HEAD y producción difieran sin que haya diferencias en la aplicación.
- Si producción no está en el historial local, traer el historial necesario del remoto autorizado y revisar. No resetear la copia, no empujar encima de producción y no sustituir los cambios de otra integrante por una captura o un ZIP viejo.
- Si no se puede verificar producción por red o permisos, informar exactamente qué comprobación falta. No afirmar que está sincronizada ni publicar con esa incertidumbre sin resolverla.

Para ver archivos distintos, una vez que el SHA publicado existe localmente:

```bash
git diff --name-status "$WAREHOUSE_PROD_COMMIT" HEAD
```

Registrar al iniciar: rama, commit local, commit remoto y commit de producción. Esta comprobación también debe repetirse antes de subir si otras personas pudieron trabajar mientras tanto.

## 4. Qué existe y no se puede perder

1. Simulador **Python/Gymnasium** como única autoridad de movimiento, inventario y misión. La interfaz representa sus datos.
2. Seis estanterías, **E01 a E06**, con tres niveles de almacenamiento e IDs estables. Las superficies inferiores vacías son soporte estructural, no un cuarto nivel de inventario.
3. Catálogo provisional de 18 SKUs `TMP-E##-L#`. No son productos comerciales definitivos ni cantidades decorativas.
4. Inventario separado en `stock_total`, `stock_reserved` y `stock_available = stock_total - stock_reserved`.
5. Validación/reserva atómica de todas las líneas, sin stock negativo ni sobreventa.
6. Pedidos reproducibles por semilla para igual inventario: 1–3 SKUs distintos, cantidades positivas y posibles. El UUID de orden permanece único.
7. Recogida exacta, descuento físico una sola vez y liberación de reserva. Entregar no vuelve a descontar.
8. Cancelación libera lo no recogido. Un fallo conserva la carga recogida no entregada como pendiente de devolución; no reaparece mágicamente en la estantería.
9. Robot que navega sin atravesar obstáculos, frena, se orienta e interactúa solamente desde un punto válido.
10. Plataforma telescópica con bandeja de rodillos: alcanza el nivel, recoge, baja y recién entonces permite desplazarse. No sustituirla por productos que saltan desde cualquier distancia.
11. Capacidad predeterminada de 3 unidades y agrupación de líneas en un viaje cuando caben. Planificación con distancia, ciclos de elevación y margen de batería/tiempo.
12. Experimento de pasillo bloqueado con ruta alternativa, sensores, batería, reloj simulado y colisiones.
13. Políticas aleatoria, heurística, manual y PPO real. No llamar PPO o «aprendido» a una decisión del despachador/BFS.
14. Checklist rosa cuyos checks dependen de cantidades recogidas/entregadas reales. No hacerlo clicable ni completarlo mediante un temporizador de interfaz.
15. Inventario lateral actualizado, selección de estante por clic o selector, cuatro cámaras, minimapa, ruta de referencia, controles y telemetría.
16. Rótulo superior físico con categoría y bandas pequeñas por subcategoría. No volver a poner listados o etiquetas grandes flotantes sobre cada estante.
17. Despacho con cinta elevada, transferencia animada, caja pastel sobre mesa, papel interior, tapa y lazo. Ningún producto entregado se dibuja sobre el suelo.
18. Sesiones de Vercel firmadas y aisladas por visitante, recarga coherente y compatibilidad de mapas anteriores.

Estados de pedido que deben conservarse: `GENERATED`, `RESERVED`, `PICKING`, `IN_TRANSIT`, `DELIVERED`, `REJECTED`, `CANCELLED` y `FAILED`. Puede haber varios ciclos de recogida/transporte. Para mostrar textos en español, traducir en la presentación sin renombrar esos contratos.

El contrato legacy mantiene un vector de **22 valores** y **cinco acciones**: `0 AVANZAR`, `1 GIRAR_IZQUIERDA`, `2 GIRAR_DERECHA`, `3 FRENAR`, `4 INTERACTUAR`. Alturas, mallas y props nuevos no autorizan agregar entradas a ese vector ni cambiar el significado de una acción.

**No solucionar una tarea visual quitando una funcionalidad de esta lista.** No ocultar botones, eliminar datos, desactivar aserciones o dibujar un estado ficticio para que una captura «se vea mejor».

## 5. Mapa de archivos para trabajar sin romper contratos

| Archivo/ruta | Qué contiene y cómo tratarlo |
| --- | --- |
| `web/src/warehouse.js` | Escena Three.js, cámaras, coordenadas, selección y render. Se puede mejorar apariencia; preservar transformación del mundo, datos de estado, controles y limpieza de recursos. |
| `web/src/rack-signs.js` | Placas físicas de categorías/niveles. Lugar principal para estilizar señalización. Mantener anclaje a la estructura y asociación E##/nivel. |
| `web/src/stock-visuals.js` | Representa existencias, carga y unidades entregadas. Cambiar el modelo visual exige conservar cantidades, instancias, posiciones y las cuatro representaciones: estante, robot, retrato y despacho. |
| `web/src/lift-visuals.js` | Apariencia del elevador. Su altura viene de `state.lift`; no inventar un movimiento independiente que contradiga al simulador. |
| `web/src/packing-station.js` | Cinta, caja, animación por unidad y cierre. Preservar cola idempotente, reconstrucción al recargar, productos elevados y estados del empaque visual. |
| `web/src/order-sheet.js` | Hoja de pedido e inventario lateral. Estilo permitido; las cantidades y los checks siguen viniendo del backend. |
| `web/src/main.js` | Peticiones API, controles, actualización y reconstrucción de escena al cambiar mapa. Evitar refactors funcionales durante una tarea de assets. |
| `web/src/style.css`, `web/index.html` | Apariencia y estructura de interfaz. Conservar IDs, controles, accesibilidad y selectores usados por JS/tests. |
| `src/warehouse_rush/inventory.py` | Catálogo provisional **y** transacciones. Selección visual de productos no autoriza reescribir sus operaciones. Integrar datos definitivos con Angie manteniendo IDs o una migración acordada. |
| `src/warehouse_rush/missions.py`, `handling.py`, `layout.py` | Misiones, alcance vertical, planificación, mapas, acceso y colisiones. Fuera del alcance visual por defecto. |
| `src/warehouse_rush/env.py`, `rewards.py`, `policies.py` | Contratos del simulador, recompensas y acciones de políticas. Preservar para Lis/Angie. |
| `src/warehouse_rush/train.py`, `evaluate.py` | Entrenamiento y evaluación de Lis. No ejecutar entrenamiento por falta de un modelo visual o para resolver una incidencia de frontend. |
| `src/warehouse_rush/viewer.py`, `cloud.py`, `api/index.py` | Servidores, API y snapshots firmados. No reemplazar por datos locales ficticios ni debilitar su validación. |
| `configs/layout_v0.1.json`, `layout_v0.3.json`, `layout_v0.4.json` | Geometrías versionadas. No mover estantes sólo en JS ni editar mapas antiguos para «arreglar» una sesión guardada. |
| `experiments/experiment-001/`, `results/` | Checkpoint, evidencias y resultados históricos. No borrar ni sobrescribir con métricas o capturas inventadas. |
| `tests/`, `web/tests/` | Regresiones funcionales y visuales. No quitarlas para que una modificación pase. |
| `vercel.json`, `web/vite.config.js`, manifests y lockfiles | Construcción, rutas, versiones y despliegue. No cambiar proveedor, dependencias o estructura del proyecto para integrar un modelo. |

La interfaz actual es **Vite + JavaScript + Three.js**. No migrarla a React, crear otra aplicación o importar una escena de demostración completa por deducción de una descripción antigua.

## 6. Contratos visuales y espaciales de los assets

### 6.1 Ejes, escala y pivotes

- Una unidad del mundo representa aproximadamente un metro; el simulador usa celdas de 1 m.
- Coordenadas del simulador: `(x, y)` sobre el suelo. En Three.js, la altura es **Y** y el segundo eje del suelo es **Z**.
- `WarehouseScene.world(x, y, altura)` transforma a `(x - (width-1)/2, altura, y - (height-1)/2)`.
- El robot mira hacia `-Z` en su orientación local de avance; el yaw se obtiene con `-theta * π/2`.
- Ajustar el pivote/orientación del asset o un contenedor visual; no rotar el mundo ni cambiar `theta` en Python para corregir un export de Blender.
- El cilindro provisional mide 0.26 m de alto y tiene el origen en su centro. Los modelos con origen en la base necesitan un adaptador de pivote: no copiar sus coordenadas de centro sin revisarlas.
- No agrandar un modelo hasta invadir pasillos o colocar su origen bajo el piso. Mantener su envolvente dentro de las superficies y huellas que ya existen.

### 6.2 Estanterías e inventario

- Tres alturas de transferencia: **0.99, 1.79 y 2.60 m**, definidas en `handling.py` y referenciadas por el catálogo.
- La base inferior no tiene SKU ni reserva. Puede restilizarse como soporte, conservando las tres superficies de almacenamiento y las alturas funcionales.
- No añadir productos decorativos indistinguibles del stock ni un número fijo de modelos por balda: el número de unidades se deriva de `stock_total`.
- Reservar no hace desaparecer una unidad. Sólo una recogida confirmada reduce el stock físico visible.
- No cambiar los IDs `E01…E06`, `E01-L1…E06-L3` ni claves SKU para que coincidan con el nombre de un archivo 3D.
- El catálogo visual puede mapear un SKU estable a un asset. El nombre comercial, su modelo y el identificador de inventario son conceptos distintos.
- Los colores y props no deben tapar los productos, los puntos de recogida ni el recorrido del robot.

Clasificación provisional que Naomi debe tomar como punto de partida:

| Estante | Categoría | Nivel 1 | Nivel 2 | Nivel 3 |
| --- | --- | --- | --- | --- |
| E01 | Maquillaje | Ojos | Rostro | Labios |
| E02 | Cuidado de la piel | Corporal | Cuidado facial | Facial hombres |
| E03 | Brochas y esponjas | Brochas individuales | Esponjas | Kits de brochas |
| E04 | Accesorios | Bolsos y cosmetiqueras | Espejos | Pestañas |
| E05 | Capilar | Accesorios para cabello | Peines | Mascarillas capilares |
| E06 | Disney | Princesas | Villanos | Toy Story |

No es un catálogo comercial definitivo; cambiar el aspecto de un producto no crea un SKU nuevo ni repone unidades.

### 6.3 Robot y elevador

- La plataforma viaja a **0.55 m**; elevar y bajar consume tiempo y batería.
- Conservar las fases `idle`, `raising`, `ready` y `lowering`, las alturas de `state.lift` y el bloqueo de movimiento.
- No separar el modelo del robot de la posición/orientación real por una animación decorativa.
- La carga se obtiene de `cargo_lines`; no dejar un paquete permanente sobre el robot cuando está vacío.
- No añadir brazos, cambiar capacidad por peso/volumen o modificar física como parte de un cambio de materiales.

### 6.4 Estación de empaque

- En v0.4, las celdas `(22,16)` y `(23,16)` están ocupadas por la estación; el robot descarga desde **`(21,16)`, mirando al este**.
- Mantener libre esa aproximación. No colocar una planta, mueble o prop delante de la entrada de la cinta.
- Superficie de cinta a **0.62 m** y pequeña rampa desde la bandeja del robot. La caja está sobre una mesa, nunca directamente sobre el piso.
- Los marcadores empacados tienen centro a **0.47 m**. Si se cambia su tamaño/pivote, revisar que apoyen en el interior y que no atraviesen la tapa.
- La animación empieza por un aumento real de `delivered`. Cada unidad usa una identidad SKU/índice; repetir un payload no debe duplicarla.
- `DELIVERED` significa entrega confirmada a la estación. El empaque posterior es una presentación visual: no vuelve a descontar stock ni altera el reloj Gym.
- La caja permanece abierta para entregas parciales y se cierra al terminar el empaque del pedido completo. «Caja preparada» no es un estado decorativo fijo.
- Recargar reconstruye productos entregados dentro de la caja, sin repetir la recogida o la entrega. Generar otra orden limpia la estación visual, no el historial real de inventario.

### 6.5 Apariencia aprobada

- Fondo oscuro existente, detalles pastel/rosa empolvado y neutros claros. No volver blanco o rosa intenso todo el fondo porque el estilo sea girly.
- Un rótulo superior fijo por estante, con caras legibles desde ambos lados, y pequeñas bandas por subcategoría. Nada de globos gigantes ni inventario flotando sobre la escena.
- Información detallada en el lateral; checklist rosa con estados reales; caja y cinta bonitas pero sin saturar el centro.
- Preservar el clic sobre estanterías/despacho y la alternativa de selección mediante controles del panel.
- Revisar escritorio y móvil, contraste, texto legible y ausencia de desplazamiento horizontal.

## 7. Cómo incorporar modelos y texturas

1. Confirmar qué SKU/estante/prop representa cada asset y qué sustituye. Si todavía no se conocen los productos definitivos, conservar la identificación temporal.
2. Preferir `.glb` optimizado con texturas incluidas, escala aplicada y pivotes claros. Mantener una copia de origen en la ubicación de diseño acordada; no llenar el despliegue con archivos de trabajo pesados innecesarios.
3. Una ubicación recomendada, **a crear cuando haya assets**, es `web/public/assets/naomi/`. Se sirve como `/assets/naomi/…`, sin el prefijo `web/public` en la URL.
4. Otra opción es importar assets desde `web/src/assets/` mediante Vite. No usar rutas `/Users/...`, discos locales, `file://`, URLs temporales de una sesión o `localhost` dentro de URLs de producción.
5. Usar loaders de la dependencia Three.js existente, por ejemplo `GLTFLoader` de `three/addons/loaders/GLTFLoader.js`. No añadir otra librería o motor sin necesidad.
6. Cargar y reutilizar modelos/materiales; no descargarlos en cada frame ni una vez por cada actualización del inventario. No romper instancias, sus cantidades o sus matrices al sustituir una geometría simple por un GLB de varias mallas.
7. Mientras carga o si falla un asset, mantener una representación provisional coherente con el stock y comunicar el fallo. No ocultar una línea de inventario porque no se pudo cargar su imagen.
8. Cancelar/ignorar cargas asíncronas de una escena ya destruida al cambiar de mapa o reiniciar. Liberar geometrías, materiales y texturas cuando corresponda; considerar recursos compartidos y materiales en arrays.
9. Registrar en la carpeta de assets sus nombres, SKU asociados, escala, ejes, origen/autor y cualquier requisito de carga aprobado. No inventar marca, precio, cantidad o atributos comerciales no proporcionados.
10. Comprobar en el navegador que no hay solicitudes de assets con 404, errores WebGL ni texturas ausentes. Optimizar polígonos/texturas, reutilizar recursos y medir en móvil; no elevar indiscriminadamente el pixel ratio o multiplicar cargas/mallas por unidad.

No guardar modelos, texturas, base64 de imágenes ni objetos Three.js dentro de observaciones, pedidos, inventario serializado o cookies. Usar referencias estables. Evitar decodificadores de un CDN o cambios a Git LFS por defecto: primero comprobar que el flujo del proyecto los soporta.

## 8. Preparar y ejecutar el proyecto

### 8.1 Herramientas

- Python **3.12** es la versión recomendada y la de `.python-version`; el paquete admite `>=3.10,<3.13`.
- Node **24** es la versión usada en Vercel y en la validación de esta entrega.
- Usar las versiones y lockfiles existentes. No hacer `npm update`, actualizar Three.js/PyTorch o regenerar lockfiles para una tarea estética.
- Si ya existe un entorno Python funcional, reutilizarlo. El README histórico usa `.venv-rl`; en este entorno de desarrollo se usa `.venv`.

Comprobar versiones:

```bash
python3.12 --version
node --version
npm --version
```

Sólo si todavía no existe un entorno adecuado, crear uno:

```bash
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install --extra-index-url https://download.pytorch.org/whl/cpu -e '.[test]'
npm ci --prefix web
```

No hace falta instalar CUDA ni ejecutar entrenamiento para trabajar con assets. Si una instalación falla, diagnosticar versión/plataforma/red; no eliminar verificación TLS, firmas o checksums ni cambiar los pins para que «pase».

En Codex Cloud, si la caché personal es de sólo lectura, usar cachés del workspace sin cambiar `HOME` ni variables reservadas. Ejemplos específicos de esa máquina, no del Mac:

```bash
UV_CACHE_DIR=/workspace/.cache/uv uv pip install --python .venv/bin/python --extra-index-url https://download.pytorch.org/whl/cpu -e '.[test]'
npm_config_cache=/workspace/.cache/npm npm ci --prefix web
```

### 8.2 Visor completo, con build

Desde la raíz, con el entorno Python activado:

```bash
npm --prefix web run build
warehouse-rush view --no-open
```

En el equipo local abrir `http://127.0.0.1:8080`. El servidor es de desarrollo local, no una publicación en Internet.

**Importante:** si `web/dist` ya existe, el visor no recompila automáticamente cada cambio. Volver a ejecutar el build tras modificar JS/CSS/assets, o usar el modo Vite siguiente. No concluir que un cambio falla viendo un bundle antiguo.

Para probar la bodega vigente: recargar, activar **Pedidos de maquillaje**, pulsar **Generar pedido** y después **Iniciar**. **Ver despacho** acerca la cámara a la cinta y la caja.

### 8.3 Desarrollo visual con Vite

Terminal 1: mantener el servidor Python anterior en 8080.

Terminal 2, desde la raíz:

```bash
npm --prefix web run dev
```

Abrir la URL de Vite que indique el comando, normalmente `http://127.0.0.1:5173`. Su proxy `/api` apunta al servidor de 8080: la simulación sigue siendo Python. No reemplazar ese proxy por datos simulados en el frontend.

En onboarding cloud no fabricar enlaces públicos de preview con direcciones loopback. Usarlas para peticiones internas; abrir la aplicación con los mecanismos disponibles del entorno cuando correspondan.

### 8.4 Adaptador similar a Vercel

```bash
python -m warehouse_rush.cloud
```

Este preview usa el puerto 8090 y una clave de sesión efímera local si no hay una configurada. No copiar la clave de producción para hacerlo funcionar. No confundir este adaptador stateless por cookie con el visor local compartido de 8080.

## 9. Validación que debe conservarse

Referencia histórica del relevo: **125 pruebas Python aprobadas; 11 pruebas de navegador aprobadas y 1 omitida en el visor local**. No presentarlas como una nueva ejecución ni usar esos números como un umbral rígido cuando se añadan pruebas legítimas.

Para un cambio pequeño de estilos: build, pruebas visuales afectadas y revisión manual pertinente. Para integrar modelos, cambiar carga de assets, pivotes, representación de unidades o conexiones de interfaz: ejecutar también regresiones funcionales. Antes de publicar una integración visual sustancial, completar las suites.

### 9.1 Backend

```bash
python -m pytest -q
```

En este checkout también puede usarse `.venv/bin/python -m pytest -q`. Un resultado con cero pruebas no valida el proyecto.

### 9.2 Navegador

Mantener el visor local de 8080 en otra terminal y construir el frontend actual:

```bash
npm --prefix web run build
npm --prefix web test
```

La configuración usa Chrome de macOS si está en su ruta estándar. En Linux, si Chromium ya está instalado:

```bash
CHROMIUM_PATH=/usr/bin/chromium npm --prefix web test
```

Si no hay navegador instalado, usar la instalación oficial de Playwright permitida por el entorno, por ejemplo `npx playwright install chromium` desde `web/`. No saltarse silenciosamente las pruebas. El repositorio no define un script de lint: no inventar uno ni declarar que pasó.

Cobertura a revisar:

- `tests/test_env.py`, `test_workflows.py`, `test_viewer.py`, `test_cloud.py`: contratos previos, políticas, API y sesiones.
- `tests/test_inventory_missions.py`: catálogo, reservas, idempotencia, pedidos y misiones.
- `tests/test_lift.py`: alturas, bloqueo de movimiento, consumos, presupuesto y recarga de estado.
- `tests/test_layouts.py`, `test_packing.py`: mapas, compatibilidad, huella de cinta y aproximación de descarga.
- `web/tests/makeup.spec.js`, `lift.spec.js`: checklist y representación ligados a hechos del simulador.
- `web/tests/signage.spec.js`: placas físicas, selección, mapa amplio y cambio de escena.
- `web/tests/packing.spec.js`: entrega real, cinta, productos dentro de caja elevada, cierre, recarga y ausencia de duplicados.
- `web/tests/viewer.spec.js`: controles, cámaras, móvil y políticas reales.

La suite de navegador se valida primero contra el visor local. **No asumir que todas sus fixtures sirven sin cambios contra producción:** algunos tests usan sesiones compartidas y otros contextos de peticiones separados. Para verificar el adaptador por visitante usar un único contexto de navegador y `page.request`/`context.request` con sus mismas cookies. No atribuir un fallo de una fixture mal aislada a la aplicación ni eliminar una aserción para ocultarlo.

Los tests existentes pueden generar capturas sobre archivos de `results/`. Revisar el estado Git antes y después; restaurar sólo salidas generadas por la ejecución propia y que no tenían modificaciones previas. No descartar toda la carpeta ni los resultados de Lis. Guardar nuevas capturas en rutas de artefactos fuera del checkout o en rutas ignoradas del runner; comprobar `.gitignore` antes de dar por hecho que una carpeta completa está ignorada.

### 9.3 Recorrido manual obligatorio para una integración visual

1. Pedido nuevo con semilla conocida e inventario válido; registrar semilla y política usada.
2. Ver productos en sus tres niveles, rótulos integrados y detalle sólo en el lateral.
3. Comprobar selección por estructura y selector, cámaras y encuadre en escritorio/móvil.
4. Navegar con y sin bloqueo del pasillo, sin atravesar estantes, paredes o cinta.
5. Recoger de un nivel alto: frenar, elevar, transferir y bajar antes de moverse. El check no aparece antes de recoger.
6. Comprobar que estante y carga cambian las cantidades correctas, y que la carga no supera capacidad.
7. Descargar desde la entrada válida: productos del robot a cinta y después a caja, sin quedar en el suelo.
8. Esperar «Caja preparada» y cierre; repetir una actualización/recargar sin duplicaciones ni otro descuento de stock.
9. Generar otro pedido: conservar stock real de la sesión y limpiar sólo la caja visual del pedido anterior.
10. Comprobar consola y solicitudes de assets. Registrar fallos, omitidas y comprobaciones no ejecutadas separadamente de las aprobadas.

No usar una imagen generada como evidencia de que el programa funciona, ni marcar checks manualmente para una captura.

## 10. Antes de subir cualquier cambio a GitHub

1. Confirmar que siguen la rama autorizada y los archivos esperados.
2. Inspeccionar el diff completo: ninguna eliminación accidental de funcionalidad, tests, mapas antiguos o resultados; ningún secreto ni archivo enorme de trabajo.
3. Comprobar el resultado de build/tests relevantes y las capturas reales del cambio visual.
4. Actualizar la documentación si cambió el modo de cargar un asset o un contrato aprobado.
5. Traer de nuevo los cambios remotos e integrar lo que haya hecho otra integrante. No usar una copia vieja sólo porque al inicio estaba actualizada.

Comandos de revisión:

```bash
git status --short
git diff --check
git diff --stat
git diff
```

Añadir únicamente los archivos revisados. Ejemplo para una tarea que realmente cambió estos archivos; adaptar la lista a lo que corresponda:

```bash
git add -- web/src/rack-signs.js web/src/style.css
git diff --cached --name-status
git diff --cached
git commit -m "feat(visual): mejorar señalización de estantes"
```

Añadir por separado los assets nuevos aprobados. Evitar `git add .` para no incluir salidas o archivos de trabajo inesperados. Usar la identidad real de la integrante y su correo asociado a GitHub; **no atribuir el trabajo a Angie o Lis para resolver un bloqueo de permisos** ni modificar autorías ajenas.

Antes del push, esta secuencia sólo empuja si la rama local contiene el remoto recién consultado:

```bash
git fetch origin dev/angie &&
git merge-base --is-ancestor FETCH_HEAD HEAD &&
git push origin HEAD:refs/heads/dev/angie
```

Si no se ejecuta el push por cambios remotos, conservar los commits locales e integrar esos cambios. Un rebase sólo puede reorganizar commits locales aún no publicados; no reescribir el historial compartido. Resolver conflictos entendiendo cada cambio: no aceptar «ours/theirs» de forma global ni borrar código funcional para que Git termine. Volver a probar lo afectado tras la integración.

Nunca usar force push, cambiar `main` o subir a otra rama para esquivar un rechazo. Un push rechazado es motivo de revisar la sincronización, no de descartar el trabajo de la compañera.

## 11. Producción: coordinar, verificar y no adivinar

Naomi no debe publicar automáticamente por estar trabajando en estética. Solicitar autorización para un despliegue nuevo si no existe ya en el encargo; la revisión debe hacerse sobre cambios concretos, terminados y validados. No volver a solicitar una autorización que Angie ya haya dado para la misma operación.

Si se publica, usar **el proyecto existente**. No crear otra demo/proyecto y presentarlo como actualización de la URL pública. No asumir despliegue automático por Git: debe comprobarse el estado real de Vercel y el destino Production, no sólo un preview READY.

Configuración que se conserva:

- Raíz del proyecto: raíz de este repositorio.
- Node 24 / Python 3.12.
- Install: `npm ci --prefix web`.
- Build: `npm run build --prefix web`.
- Output: `web/dist`.
- `api/index.py`, rutas `/api/*`, modelo archivado y configuraciones necesarias del backend incluidos.
- `WAREHOUSE_SESSION_SECRET` estable en Vercel, sin copiarlo a Git ni rotarlo para una tarea visual.
- `VERCEL_SUPPORT_LARGE_FUNCTIONS=1` según la configuración existente del proyecto para las dependencias Python de ML.

**No depender de scripts de `/tmp` ni del historial de este chat.** Son herramientas temporales de una sesión, no un pipeline versionado. Si el mecanismo de subida usa un manifiesto/lista de archivos, comprobar que incluye los nuevos GLB/texturas, en especial `web/public/`; un build local correcto no prueba que se hayan subido esos assets a Vercel. Revisar también `.vercelignore` y las exclusiones de funciones sin confundirlas con la publicación de archivos estáticos.

Credenciales y permisos:

- `VERCEL_TOKEN` es un secreto de despliegue del entorno, no una variable de frontend. Nunca ponerlo en `VITE_*`, JS, GLB, `.env` versionado, logs, capturas o el chat.
- Comprobar nombres, presencia y estado de bindings sin mostrar sus valores. Reutilizar la autenticación suministrada por la plataforma; no pedir tokens nuevos sólo porque una CLI no muestra una sesión.
- Un token limitado al proyecto puede permitir consultar/publicar ese proyecto y rechazar endpoints de usuario/equipos. Diagnosticar el recurso concreto, no inferir que el token está mal por un `whoami` fallido.
- Si Vercel bloquea un autor Git por acceso al equipo, coordinar con Angie para dar acceso o para que ella haga una publicación autorizada con trazabilidad. No falsificar la identidad de Naomi ni alterar commits de otras personas para saltarse el control.
- Mantener proxy y verificación TLS. No usar `curl -k`, `ignoreHTTPSErrors` ni saltarse verificaciones para obtener una captura. Informar el bloqueo específico y continuar verificaciones seguras disponibles.

Después de publicar:

1. Confirmar despliegue READY con destino Production y que la URL pública apunte a él.
2. Consultar `/api/health`: el commit debe corresponder al código publicado. No confiar en el SHA que devuelve únicamente el entorno local.
3. Revisar que la página pública carga los assets nuevos sin 404 y coincide con el build validado.
4. Ejecutar una misión representativa en producción con un contexto aislado de prueba, conservando sus cookies; verificar inventario y entrega, no sólo un puerto o la página inicial.
5. Distinguir controles ejecutados de comprobaciones visuales que sólo se hicieron en local. No declarar una prueba de navegador publicada si no se ejecutó.
6. Indicar a la usuaria: **recargar → Generar pedido → Iniciar → Ver despacho**. Una sesión antigua puede conservar su mapa anterior hasta un pedido nuevo; no borrar compatibilidad para forzar la vista.

Una actualización sólo de esta guía o documentación puede subirse a GitHub sin volver a desplegar la aplicación. En ese caso, explicar que producción conserva el mismo código funcional aunque HEAD tenga un commit documental posterior.

## 12. Límites conocidos y cómo no confundirlos con fallos de assets

- El inventario local vive durante el proceso; reiniciar el servidor crea un almacén nuevo. Generar pedidos sucesivos dentro de la sesión no repone stock.
- En Vercel el estado está aislado por visitante y firmado en cookie; no es un inventario global compartido entre clientes ni una base durable. La cookie caduca y tiene un límite de tamaño de 3800 caracteres. No meter contenido visual pesado en ella ni quitar la firma para resolver tamaño.
- Las versiones de mapa admitidas incluyen v0.1, v0.3 y v0.4. No borrar decodificación o JSON históricos mientras existan sesiones/checkpoints que dependan de ellos.
- La transferencia horizontal, cinta y empaque son representaciones simplificadas. No hay agarre por dedos, física certificada de producto ni envío real a una transportadora.
- Un checkpoint PPO compatible en forma no implica que esté entrenado para los objetivos, alturas y aproximación actuales. No fabricar métricas ni reentrenar por iniciativa de una tarea visual.
- Si un fallo es funcional y queda fuera del encargo de Naomi, conservar la evidencia y señalar archivo, operación y reproducción. No «arreglarlo» retirando la característica o cambiando su contrato a escondidas.

## 13. Entrega de cada tarea

Antes de cerrar, dejar un resumen breve y comprobable con:

- Qué cambió visualmente y qué assets/SKUs cubre.
- Archivos principales modificados y cualquier requisito de importación.
- Pruebas realmente ejecutadas, sus resultados y lo que quedó sin verificar.
- Capturas reales antes/después cuando ayuden a revisar.
- Rama, commit y resultado del push; indicar por separado si hubo despliegue o sólo actualización del repositorio.
- Pendientes concretos para Angie o Lis, sin atribuirles decisiones no tomadas.

El resultado deseado es una bodega más bonita que siga haciendo correctamente **pedido → reserva → navegación → elevación/recogida → transporte → despacho → cinta/caja**, con inventario consistente y las funcionalidades de las compañeras conservadas.
