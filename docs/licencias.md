# Licencias de assets y dependencias

Proyecto académico, sin fines comerciales: proyecto final de MLOps, Universidad Externado de Colombia.

## Assets propios
| Asset | Origen | Licencia |
|---|---|---|
| Modelos 3D de productos (`web/public/assets/products/*.glb`, `*.png`) | Generados por el equipo con código propio: `web/src/products.js` (`createProduct`) exportado con `three/addons/exporters/GLTFExporter` (`web/scripts/export-products.mjs`). No incluyen mallas, texturas ni imágenes de terceros. | Del equipo, mismo uso que el repositorio |
| Bodega 3D, estanterías, elevador, cinta y caja (`web/src/*.js`) | Geometría procedural de Three.js escrita por el equipo | Del equipo |
| Mapas, catálogo y configuraciones (`configs/`) | Del equipo | Del equipo |
| Curvas y resultados (`docs/resultados/`, `web/public/modelos/`) | Generados por los pipelines del proyecto | Del equipo |

## Referencias de marca
El catálogo de 27 productos (`configs/products.json`) toma nombres y categorías del PDF que aportó Naomi (SHA-256 en [entrega-naomi.md](entrega-naomi.md)). Ese PDF se inspira en la tienda de maquillaje Trendy.
La marca solo se cita como contexto de la simulación. No se usan logotipos, fotografías ni material gráfico de la marca, y el proyecto no tiene relación con ella.

## Recursos de terceros que usa la web
| Recurso | Uso | Licencia |
|---|---|---|
| Three.js 0.186.1 | Escena 3D, OrbitControls, GLTFExporter | MIT |
| Vite 8.3.5 | Build de la web | MIT |
| Playwright 1.64.1 | Pruebas de navegador (solo desarrollo) | Apache-2.0 |
| Fuentes Barlow, Barlow Condensed, JetBrains Mono (Google Fonts) | Tipografía | SIL Open Font License 1.1 |

## Dependencias de Python principales
| Paquete | Licencia |
|---|---|
| Stable-Baselines3 2.4.1 | MIT |
| Gymnasium 1.0.0 | MIT |
| PyTorch 2.2.2 (CPU) | BSD-3-Clause |
| NumPy 1.26.4 | BSD-3-Clause |
| Matplotlib 3.9.4 | Licencia de Matplotlib (estilo PSF/BSD) |
| MLflow 3.18.0 | Apache-2.0 |
| DVC 3.67.1 | Apache-2.0 |
| FastAPI 0.162.0 | MIT |
| Prefect 3.8.8 | Apache-2.0 |

Versiones exactas: `requirements.txt` y `web/package-lock.json`.
