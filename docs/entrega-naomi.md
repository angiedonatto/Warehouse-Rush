> Documento histórico de la primera versión `df7c28b`. Para el estado integrado de `dev/naomi`, consultar [integración rosa](integracion-rosa.md). El catálogo operativo actual conserva 18 SKU TMP; los 27 TRD se mantienen como catálogo visual, sin migración de inventario implícita.

# Entrega Naomi — catálogo y dirección visual Trendy

Implementación en `dev/naomi`, sobre la base funcional de `dev/angie` (commit `860e188`).
Gymnasium ejecuta las misiones; Three.js representa el estado real del simulador.

## Selección y trazabilidad

Fuente: PDF aportado por Naomi, «Documento sin título.pdf», 7 páginas.
Se incluyen los 27 productos y sus categorías/subcategorías; se corrigen únicamente tildes.
Los identificadores `TRD-xx-xx` son internos del proyecto, no referencias comerciales oficiales.
Cada kit cuenta como un SKU: sus ocho labiales no son ocho unidades de inventario.
Stock inicial de simulación: cinco unidades por SKU. No son existencias de una tienda real.

SHA-256 del PDF: `f38ca5fb946f0f4fd03e09663eaaf8480abf0c535ba6d1751b84cbba3bc0e8aa`.

| SKU | Categoría | Subcategoría | Producto | Ubicación | PDF |
|---|---|---|---|---|---|
| TRD-01-01 | Maquillaje | Cejas | Lápiz retráctil | E01-L1 | p. 1 |
| TRD-01-02 | Maquillaje | Cejas | Fijador de cejas | E01-L1 | p. 1 |
| TRD-01-03 | Maquillaje | Cejas | Kit depilador de cejas | E01-L1 | p. 1 |
| TRD-01-04 | Maquillaje | Labios | Kit x8 Labiales | E01-L1 | p. 1 |
| TRD-01-05 | Maquillaje | Labios | Kit x6 delineadores | E01-L2 | p. 2 |
| TRD-01-06 | Maquillaje | Labios | Gloss | E01-L2 | p. 2 |
| TRD-01-07 | Maquillaje | Ojos | Delineador de ojos | E01-L2 | p. 2 |
| TRD-01-08 | Maquillaje | Ojos | Kit Pestañina + fortalecedor | E01-L2 | p. 2 |
| TRD-01-09 | Maquillaje | Ojos | Paleta de sombras | E01-L3 | p. 2 |
| TRD-01-10 | Maquillaje | Rostro | Base | E01-L3 | p. 3 |
| TRD-01-11 | Maquillaje | Rostro | Corrector | E01-L3 | p. 3 |
| TRD-01-12 | Maquillaje | Rostro | Polvos compactos | E01-L3 | p. 3 |
| TRD-02-01 | Cuidado de la piel | Corporal | Crema | E02-L1 | p. 3 |
| TRD-02-02 | Cuidado de la piel | Corporal | Exfoliante | E02-L2 | p. 4 |
| TRD-02-03 | Cuidado de la piel | Corporal | Splash | E02-L3 | p. 4 |
| TRD-02-04 | Cuidado de la piel | Facial | Mascarilla | E02-L3 | p. 4 |
| TRD-03-01 | Brochas | Brochas individuales | Brocha polvos | E03-L1 | p. 4 |
| TRD-03-02 | Brochas | Esponjas | Esponja | E03-L2 | p. 5 |
| TRD-04-01 | Accesorios | Bolsos y monederos | Tarjetero | E04-L1 | p. 5 |
| TRD-04-02 | Accesorios | Cosmetiqueras | Cosmetiquera viajera | E04-L2 | p. 5 |
| TRD-04-03 | Accesorios | Pestañas | Pegante de pestañas | E04-L3 | p. 5 |
| TRD-05-01 | Capilar | Accesorios para el cabello | Pinzas | E05-L1 | p. 6 |
| TRD-05-02 | Capilar | Accesorios para el cabello | Kit Peinillas | E05-L2 | p. 6 |
| TRD-05-03 | Capilar | Accesorios para el cabello | Caimán mariposa | E05-L3 | p. 6 |
| TRD-06-01 | Disney | Toy Story 5 | Rubor Lotso | E06-L1 | p. 6 |
| TRD-06-02 | Disney | Stitch | Cadena Stitch | E06-L2 | p. 7 |
| TRD-06-03 | Disney | Intensamente 2 | Brillo Ansiedad | E06-L3 | p. 7 |

## Investigación y propuesta estética

Referencias consultadas el 6 de noviembre de 2026:

- [Sitio oficial de Trendy](https://www.maquillajetrendyshop.com/): navegación por categorías y presentación de productos de belleza.
- [Tiendas de la marca](https://www.maquillajetrendyshop.com/nuestras-tiendas): contexto comercial de la simulación.
- [Banner oficial de colección](https://b2ctrendy.vtexassets.com/assets/vtex.file-manager-graphql/images/35311a59-2338-45da-8fc7-ddc92f52f437___fd57ec4cee2171837ab1ce1688aaaf77.jpg): fondo rosa suave, brochas de acabado metálico y empaques pastel.
- Fotos de los 27 productos del PDF: siluetas, combinaciones de color y presentación de los kits.

Propuesta propia inspirada en esas referencias: rosa crema `#fff5f9`, fucsia
`#ad366f`, lavanda y detalles oro rosa. Racks claros, vigas rosadas, iluminación
suave, señalización por categorías y letrero TRENDY. Se conservan las marcas de
seguridad diferenciadas por color y las mismas huellas, colisiones y rutas del mapa.
No se afirma que el mapa reproduzca una bodega real de la marca.

## Assets y arquitectura

- `configs/products.json`: fuente única del catálogo. Python la carga a través del enlace `src/warehouse_rush/configs`; Vite importa ese mismo JSON.
- `web/src/products.js`: fábricas Three.js de modelos originales estilizados, con materiales y geometrías compartidos.
- `web/public/assets/products/`: 27 archivos GLB independientes, miniaturas PNG y manifiesto.
- `web/src/catalog.js`: buscador, filtro de categorías, vista orbitable y descarga de cada GLB.
- `web/src/warehouse.js`: cinco representaciones visuales por SKU, visibles según stock físico restante. El modelo recogido aparece sobre el robot.
- La reserva no hace desaparecer stock físico; la recogida sí. Los datos del checklist y del panel de inventario proceden de Python.
- E01: maquillaje; E02: piel; E03: brochas; E04: accesorios; E05: capilar; E06: Disney. Tres niveles por rack, con varios SKU por nivel cuando corresponde.

Las siluetas son aproximaciones de baja complejidad basadas en las fotos del PDF,
no escaneos ni réplicas exactas de empaques. No se distribuyen fotografías comerciales
ni texturas descargadas. La escala de exhibición es aproximada; no representa dimensiones
reales de los productos. Los GLB pueden abrirse en Blender o en un visor compatible con glTF 2.0.

## Ejecutar y regenerar

Para la instalación completa, seguir el README del proyecto. Para revisar únicamente
el visor y las misiones heurísticas (sin entrenamiento PPO), basta un entorno con
Python 3.12, `gymnasium==1.0.0` y `numpy==1.26.4`:

```sh
npm ci --prefix web
npm run assets --prefix web
npm run build --prefix web
PYTHONPATH=src .venv/bin/python -m warehouse_rush.cli view --no-open
```

Abrir `http://127.0.0.1:8080`, pulsar «Explorar los 27 productos» o activar
«Pedidos de maquillaje» y «Generar pedido». Usar el heurístico para recorrer la bodega.
El modo de maquillaje existente incluye todas las categorías del PDF.

Para actualizar miniaturas después de editar los modelos, mantener el servidor local
encendido, ejecutar el siguiente comando y volver a compilar:

```sh
CHROMIUM_PATH=/usr/bin/chromium node web/scripts/preview-products.mjs
npm run build --prefix web
```

El exportador GLB no necesita navegador; las miniaturas requieren Chromium/Playwright.
El inventario sigue siendo por sesión y sin persistencia durable. Las cookies antiguas
con SKU `TMP-` requieren reiniciar la misión para crear una sesión con el nuevo catálogo;
no se inventa una equivalencia entre productos provisionales y los seleccionados.
No se reentrena PPO ni se cambian sus observaciones o recompensas.

## Verificación

- 33 pruebas existentes de inventario y misiones.
- 15 pruebas existentes de visor y sesiones firmadas.
- 55 pruebas del catálogo: cantidades por categoría, contrato Gymnasium del ambiente base y recogida/entrega de cada SKU con y sin bloqueo.
- 27 GLB cargados mediante `GLTFLoader` de Three.js.
- Build de producción Vite.
- Playwright: catálogo, filtros, descarga GLB, vista móvil y entrega integral con inventario real.

No se ejecuta aquí el entrenamiento ni la suite completa dependiente de Stable-Baselines3/PyTorch;
la comprobación usa el entorno ligero descrito arriba.
