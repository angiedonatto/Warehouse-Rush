"""API FastAPI (api/_app.py, api/_modelos.py, api/_episodios.py).

- Sin pesos de DVC ni red: el almacén de modelos sirve las políticas NumPy de models/numpy/ (en Git, verificadas
  contra SB3 por pipelines/exportar_numpy.py) sobre copias de manifiestos reales; la app usa el repositorio real
  (catálogo, suites, mapas) sin precargar modelos.
- Las evaluaciones certificadas son asíncronas (POST /evaluaciones → 202, GET /evaluaciones/trabajos/{id}) y
  reproducen por la API las evaluaciones congeladas de los dos modelos de producción y la degradación de
  m1-c3-seed0 con el paso cerrado (antecedente de docs/rollback.md). Los episodios usan el catálogo de la web
  (trendy-27-v1) y las evaluaciones en suites el certificado (legacy-18).
"""
import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

pytest.importorskip("fastapi")
from fastapi.testclient import TestClient  # noqa: E402

from api._app import create_app  # noqa: E402
from api._episodios import GestorEpisodios  # noqa: E402
from api._modelos import AlmacenModelos, ErrorModelo  # noqa: E402
from pipelines import registry as R  # noqa: E402

REPO = Path(__file__).resolve().parents[1]
ORIGEN = "https://warehouse-rush-experiment-001.vercel.app"


# --- Almacén de modelos (NumPy, sin torch ni DVC) --------------------------------------------------

@pytest.fixture
def raiz_falsa(tmp_path):
    """Copia de manifiestos reales, sus .npz y fichas de models/numpy/ y alias de producción inicializados."""
    (tmp_path / "manifests").mkdir()
    (tmp_path / "models/numpy").mkdir(parents=True)
    shutil.copy(REPO / "manifests/schema.json", tmp_path / "manifests/schema.json")
    for run in ("m1b-i1-seed1-best", "m1-c3-seed0", "m1-c3-seed1", "m1-c4-seed1", "m1o-e4l-seed0"):
        shutil.copy(REPO / f"manifests/{run}.json", tmp_path / f"manifests/{run}.json")
        for ext in ("npz", "json"):
            origen = REPO / f"models/numpy/{run}.{ext}"
            if origen.is_file():  # m1o-e4l-seed0 (warehouse-v5) no tiene versión NumPy
                shutil.copy(origen, tmp_path / f"models/numpy/{run}.{ext}")
    # aliases.json con la forma de pipelines.registry; no se usa inicializar_aliases porque verifica los .zip de DVC,
    # que esta raíz (como la imagen de Render) no tiene
    ranuras = {"m1": {"actual": "m1-c3-seed0", "anterior": None},
               "m1b": {"actual": "m1b-i1-seed1-best", "anterior": None},
               R.PRODUCCION: {"actual": "m1b-i1-seed1-best", "anterior": "m1-c3-seed0"}}
    (tmp_path / "manifests/aliases.json").write_text(json.dumps(
        {"schema_version": 1, "version": 1, "actualizado_en": "prueba", "ranuras": ranuras, "historial": []}))
    return tmp_path


def codigo(fn, *args):
    with pytest.raises(ErrorModelo) as exc:
        fn(*args)
    return exc.value.estado_http, exc.value.codigo


def test_almacen_rechaza_inexistente_e_incompatible(raiz_falsa):
    almacen = AlmacenModelos(raiz_falsa)
    assert codigo(almacen.obtener, "no-existe") == (404, "modelo_no_encontrado")
    assert codigo(almacen.obtener, "m1o-e4l-seed0") == (409, "modelo_incompatible")  # warehouse-v5


def test_almacen_no_carga_si_falla_la_cadena_de_hashes(raiz_falsa):
    npz, ficha = raiz_falsa / "models/numpy/m1-c3-seed1.npz", raiz_falsa / "models/numpy/m1-c3-seed1.json"
    npz.write_bytes(npz.read_bytes() + b"x")  # .npz alterado
    assert codigo(AlmacenModelos(raiz_falsa).obtener, "m1-c3-seed1") == (500, "integridad")
    shutil.copy(REPO / "models/numpy/m1-c3-seed1.npz", npz)
    datos = json.loads(ficha.read_text())
    ficha.write_text(json.dumps({**datos, "model_sha256": "0" * 64}))  # ficha de otro modelo
    assert codigo(AlmacenModelos(raiz_falsa).obtener, "m1-c3-seed1") == (500, "integridad")


def test_almacen_sin_version_numpy_responde_409(raiz_falsa):
    (raiz_falsa / "models/numpy/m1-c3-seed1.npz").unlink()
    almacen = AlmacenModelos(raiz_falsa)
    assert codigo(almacen.obtener, "m1-c3-seed1") == (409, "sin_version_numpy")
    assert almacen.estado()["cargados"] == []


def test_almacen_fija_produccion_y_desaloja_el_resto(raiz_falsa):
    almacen = AlmacenModelos(raiz_falsa, capacidad=1)
    precarga = almacen.precargar_produccion()
    assert precarga["estado"] == "ok"
    assert almacen.obtener("m1-c3-seed0") is almacen.obtener("m1-c3-seed0")  # caché
    almacen.obtener("m1-c3-seed1")
    almacen.obtener("m1-c4-seed1")  # desaloja m1-c3-seed1, no los fijos
    cargados = {m["run_id"]: m["fijo"] for m in almacen.estado()["cargados"]}
    assert cargados == {"m1b-i1-seed1-best": True, "m1-c3-seed0": True, "m1-c4-seed1": False}
    assert almacen.servido()["run_id"] == "m1b-i1-seed1-best"


def test_precarga_no_muere_ante_un_error_inesperado(raiz_falsa, monkeypatch):
    def explota(self, manifest):
        raise RuntimeError("fallo inesperado")

    monkeypatch.setattr(AlmacenModelos, "_cargar", explota)
    precarga = AlmacenModelos(raiz_falsa).precargar_produccion()
    assert precarga["estado"] == "fallido"
    assert {m["codigo"] for m in precarga["modelos"].values()} == {"error_interno"}


def test_inferencia_sin_torch_y_monitoreo_de_empates():
    """Como en la imagen de Render: torch y SB3 bloqueados; el modelo de producción completa un episodio."""
    codigo_py = (
        "import sys\n"
        "sys.modules['torch'] = None; sys.modules['stable_baselines3'] = None\n"
        "from api._modelos import AlmacenModelos\n"
        "from envs import make_env\n"
        "almacen = AlmacenModelos()\n"
        "m = almacen.obtener('m1b-i1-seed1-best')\n"
        "env = make_env(True, m.manifiesto['layout_path'], 3, m.manifiesto['reward_overrides'])\n"
        "obs, _ = env.reset(seed=10000); fin = False\n"
        "while not fin:\n"
        "    obs, _, a, b, info = env.step(m.politica.action(obs, env)); fin = a or b\n"
        "e = almacen.estado()\n"
        "print(info['success'], info['steps'], e['decisiones'], e['casi_empates'])\n")
    salida = subprocess.run([sys.executable, "-c", codigo_py], cwd=REPO, capture_output=True, text=True, timeout=120)
    assert salida.returncode == 0, salida.stderr[-500:]
    exito, pasos, decisiones, empates = salida.stdout.split()
    assert (exito, pasos, decisiones, empates) == ("True", "107", "107", "0")  # = evaluación congelada (legacy-18)


# --- Episodios (heurística, sin pesos) -------------------------------------------------------------

def test_episodios_caducan_y_respetan_el_maximo():
    reloj = [0.0]
    gestor = GestorEpisodios(AlmacenModelos(REPO), ttl_s=1800, maximo=2, reloj=lambda: reloj[0])
    primero = gestor.crear(politica="heuristic")
    segundo = gestor.crear(politica="random")
    assert codigo(lambda: gestor.crear(politica="heuristic")) == (429, "demasiados_episodios")
    gestor.correr(primero["episodio_id"])  # terminado: es el que se descarta
    gestor.crear(politica="heuristic")
    assert codigo(gestor.obtener, primero["episodio_id"]) == (404, "episodio_no_encontrado")
    reloj[0] += 1801
    assert codigo(gestor.obtener, segundo["episodio_id"]) == (404, "episodio_no_encontrado")


# --- App HTTP sobre el repositorio real (sin precargar modelos) ------------------------------------

@pytest.fixture
def cliente(monkeypatch):
    monkeypatch.setenv("CORS_ORIGINS", ORIGEN)
    monkeypatch.delenv("CORS_ORIGIN_REGEX", raising=False)
    with TestClient(create_app(REPO, precargar=False)) as c:
        yield c


def test_health_version_y_cabeceras(cliente):
    assert cliente.get("/health").json()["status"] == "ok"
    respuesta = cliente.get("/version")
    version = respuesta.json()
    aliases = json.loads((REPO / "manifests/aliases.json").read_text())["ranuras"]["produccion"]
    servido = json.loads((REPO / f"manifests/{aliases['actual']}.json").read_text())
    assert (version["run_id"], version["model_sha256"]) == (servido["run_id"], servido["model_sha256"])
    assert version["environment_version"] == "warehouse-v10"
    assert version["catalogo"]["al_dia"] is True
    assert respuesta.headers["x-modelo-servido"] == f"{servido['run_id']}@{servido['model_sha256'][:12]}"
    assert respuesta.headers["x-git-commit"]


def test_catalogo_filtra_y_ficha(cliente):
    recomendados = cliente.get("/catalogo", params={"estado": "recomendado"}).json()["modelos"]
    assert {m["run_id"] for m in recomendados} == {"m1-c3-seed0", "m1b-i1-seed1-best"}
    ficha = cliente.get("/catalogo/m1-c3-seed0").json()
    assert ficha["manifiesto"]["model_sha256"] == ficha["modelo"]["model_sha256"]
    assert cliente.get("/catalogo/no-existe").status_code == 404


def test_errores_tienen_una_sola_forma(cliente):
    for respuesta, estado, cod in ((cliente.get("/no-existe"), 404, "ruta_no_encontrada"),
                                   (cliente.put("/version"), 405, "metodo_no_permitido"),
                                   (cliente.post("/episodios", json={"seed": "5"}), 422, "parametro_invalido"),
                                   (cliente.post("/episodios", json={"extra": 1}), 422, "parametro_invalido"),
                                   (cliente.post("/modelos/m1o-e4l-seed0/cargar"), 409, "modelo_incompatible")):
        assert respuesta.status_code == estado
        assert set(respuesta.json()["error"]) == {"codigo", "mensaje", "detalle"}
        assert respuesta.json()["error"]["codigo"] == cod


def test_cors_solo_para_el_origen_configurado(cliente):
    permitido = cliente.options("/episodios", headers={"Origin": ORIGEN, "Access-Control-Request-Method": "POST",
                                                       "Access-Control-Request-Headers": "content-type"})
    assert permitido.status_code == 200
    assert permitido.headers["access-control-allow-origin"] == ORIGEN
    assert "access-control-allow-credentials" not in permitido.headers
    otro = cliente.options("/episodios", headers={"Origin": "https://otro.example",
                                                  "Access-Control-Request-Method": "POST"})
    assert "access-control-allow-origin" not in otro.headers
    assert "X-Modelo-Servido" in cliente.get("/version", headers={"Origin": ORIGEN}).headers["access-control-expose-headers"]


def test_evaluaciones_rechazan_suites_reservadas_o_de_otra_familia(cliente):
    for cuerpo, estado in (({"suite_id": "test-final-m1-v1"}, 404), ({"suite_id": "../manifests/schema"}, 404),
                           ({"suite_id": "suite-n1-v1"}, 409),
                           ({"suite_id": "suite-m1-v1", "politica": "heuristic", "run_id": "m1-c3-seed0"}, 400)):
        assert cliente.post("/evaluaciones", json=cuerpo).status_code == estado, cuerpo


def evaluar_y_esperar(cliente, cuerpo: dict, limite_s: float = 300) -> dict:
    """POST /evaluaciones (202) y consulta GET /evaluaciones/trabajos/{id} hasta que termine."""
    import time

    respuesta = cliente.post("/evaluaciones", json=cuerpo)
    assert respuesta.status_code == 202, respuesta.json()
    trabajo = respuesta.json()
    assert trabajo["estado"] in ("en_cola", "en_curso") and trabajo["sondeo"].endswith(trabajo["evaluacion_id"])
    fin = time.monotonic() + limite_s
    while trabajo["estado"] in ("en_cola", "en_curso"):
        assert time.monotonic() < fin, trabajo
        time.sleep(0.2)
        trabajo = cliente.get(trabajo["sondeo"]).json()
    assert trabajo["estado"] == "terminada", trabajo.get("error")
    assert trabajo["progreso"] == {"episodios_hechos": trabajo["episodios"], "episodios_total": trabajo["episodios"]}
    return trabajo


def test_evaluacion_de_la_heuristica_en_suite_fija(cliente):
    trabajo = evaluar_y_esperar(cliente, {"suite_id": "dev-m1-v1", "politica": "heuristic"})
    assert trabajo["episodios"] == 10 and trabajo["semillas"] == [1000, 1009]
    assert trabajo["certificado"] is True and trabajo["catalog_version"] == "legacy-18"
    assert trabajo["resultado"]["resumen"]["success_rate"] == 1.0
    assert len(trabajo["resultado"]["por_episodio"]) == 10
    monitoreo = cliente.get("/monitoreo").json()
    fila = next(f for f in monitoreo["exito_por_escenario"] if f["quien"] == "heuristic")
    assert (fila["escenario"], fila["episodios"], fila["origen"]) == ("m1/abierto", 10, {"evaluacion": 10})


def test_episodio_de_referencia_y_manual_por_http(cliente):
    creado = cliente.post("/episodios", json={"politica": "heuristic", "nivel": "m1b"})
    assert creado.status_code == 201 and creado.json()["modo"] == "referencia"
    episodio = creado.json()["episodio_id"]
    final = cliente.post(f"/episodios/{episodio}/correr").json()["final"]
    assert final["done"] and final["info"]["success"] and final["bloqueado"]
    assert cliente.post(f"/episodios/{episodio}/paso").json()["error"]["codigo"] == "episodio_terminado"

    manual = cliente.post("/episodios", json={"politica": "manual"}).json()["episodio_id"]
    assert cliente.post(f"/episodios/{manual}/paso", json={"accion": 1}).json()["last_action"]["name"] == "GIRAR_IZQUIERDA"
    assert cliente.post(f"/episodios/{manual}/paso", json={"accion": "1"}).status_code == 422
    assert cliente.post(f"/episodios/{manual}/paso").status_code == 400
    assert cliente.post(f"/episodios/{manual}/correr").status_code == 400
    assert cliente.delete(f"/episodios/{manual}").json()["cerrado"] is True
    assert cliente.get(f"/episodios/{manual}").status_code == 404


def test_layout_del_nivel(cliente):
    layout = cliente.get("/layout", params={"nivel": "m1b"}).json()
    assert layout["layout_path"] == "configs/layout_v0.4.json" and layout["bloqueado_por_defecto"] is True
    # el catálogo del ambiente de los episodios (web: trendy-27-v1), no el de las suites certificadas (legacy-18)
    assert (layout["catalog_version"], len(layout["catalog"])) == ("trendy-27-v1", 27)
    assert layout["catalogo_evaluaciones"] == "legacy-18"
    assert cliente.get("/layout", params={"nivel": "n1"}).status_code == 422


def test_episodios_usan_el_catalogo_de_la_web(cliente):
    from envs.inventory import CATALOGS

    episodio = cliente.post("/episodios", json={"politica": "heuristic", "seed": 10_000}).json()
    assert episodio["catalog_version"] == "trendy-27-v1"
    assert all(linea["sku"] in CATALOGS["trendy-27-v1"] for linea in episodio["state"]["order"]["lines"])


# --- Modelos de producción (NumPy) frente a las evaluaciones congeladas ----------------------------

def test_evaluacion_por_api_reproduce_las_congeladas(cliente):
    produccion = evaluar_y_esperar(cliente, {"suite_id": "suite-m1b-v1", "run_id": "m1b-i1-seed1-best"})
    assert produccion["inferencia"] == "numpy" and produccion["catalog_version"] == "legacy-18"
    esperado = json.loads((REPO / "manifests/m1b-i1-seed1-best.json").read_text())
    esperado = esperado["evaluation"]["by_scenario"]["suite-m1b-v1 (paso (6,14) cerrado)"]["ppo"]
    resumen = produccion["resultado"]["resumen"]
    assert resumen["success_rate"] == esperado["success_rate"] == 1.0
    assert resumen["mean_steps"] == pytest.approx(esperado["mean_steps"])

    rollback = evaluar_y_esperar(cliente, {"suite_id": "suite-m1b-v1", "run_id": "m1-c3-seed0"})
    congelada = json.loads((REPO / "docs/resultados/eval/incidente-m1-c3-seed0/evaluation.json").read_text())
    por_semilla = {e["seed"]: e for e in congelada["episodes"] if e["policy"] == "ppo" and e["scenario"] == "blocked"}
    congelada = next(s for s in congelada["summary"] if s["policy"] == "ppo" and s["scenario"] == "blocked")
    resumen = rollback["resultado"]["resumen"]
    assert resumen["success_rate"] == congelada["success_rate"] == 0.0
    assert resumen["mean_collisions"] == pytest.approx(congelada["mean_collisions"])
    assert resumen["end_reasons"] == congelada["end_reasons"]
    for e in rollback["resultado"]["por_episodio"]:  # episodio a episodio, con la política NumPy
        c = por_semilla[e["seed"]]
        assert (e["steps"], e["collisions"], e["end_reason"]) == (c["steps"], c["collisions"], c["end_reason"])
    monitoreo = cliente.get("/monitoreo").json()
    assert monitoreo["evaluaciones"]["por_estado"]["terminada"] >= 2
    assert monitoreo["latencia_decision"]["m1-c3-seed0"]["n"] > 0


def test_rollback_pierde_el_escenario_del_incidente(cliente):
    """docs/rollback.md («Con el catálogo de la web»): con trendy-27-v1, m1-c3-seed0 completa con el paso abierto y no
    completa con el paso cerrado (semilla 10000; medir_rollback.py da lo mismo); el modelo de producción sí."""
    def jugar(**cuerpo):
        episodio = cliente.post("/episodios", json={"seed": 10_000, **cuerpo}).json()
        assert episodio["modo"] == "evaluacion" and episodio["catalog_version"] == "trendy-27-v1"
        return cliente.post(f"/episodios/{episodio['episodio_id']}/correr").json()["final"]["info"]

    abierto = jugar(run_id="m1-c3-seed0", nivel="m1", bloqueado=False)
    cerrado = jugar(run_id="m1-c3-seed0", nivel="m1b", bloqueado=True)
    produccion = jugar(bloqueado=True)  # sin run_id: el modelo de producción
    medido = json.loads((REPO / "docs/resultados/eval/catalogo-trendy-27/rollback_m1-c3-seed0.json").read_text())["casos"]
    for info, caso in ((abierto, "trendy-27-v1 | abierto"), (cerrado, "trendy-27-v1 | cerrado")):
        esperado = medido[caso]["episodios"][0]  # semilla 10000
        assert (info["success"], info["end_reason"], info["steps"], info["collisions"]) == \
            (esperado["success"], esperado["end_reason"], esperado["steps"], esperado["collisions"])
    assert abierto["success"] and not cerrado["success"]
    assert produccion["success"] and produccion["collisions"] == 0


# --- Cola de evaluaciones ---------------------------------------------------------------------------

def test_cola_de_evaluaciones_limite_fallos_y_caducidad():
    import threading
    import time

    from api._app import TrabajosEvaluacion

    reloj = [0.0]
    trabajos = TrabajosEvaluacion(cola_max=3, ttl_s=1800, reloj=lambda: reloj[0])
    soltar = threading.Event()
    primero = trabajos.encolar({"episodios": 1}, lambda: soltar.wait(5) and {"ok": True})
    for _ in range(50):  # el hilo toma el primero
        if trabajos.ver(primero["evaluacion_id"])["estado"] == "en_curso":
            break
        time.sleep(0.02)
    en_cola = [trabajos.encolar({"episodios": 1}, lambda: {"ok": True}) for _ in range(3)]
    assert [t["posicion_en_cola"] for t in en_cola] == [1, 2, 3]
    with pytest.raises(ErrorModelo) as exc:
        trabajos.encolar({"episodios": 1}, lambda: {"ok": True})
    assert (exc.value.estado_http, exc.value.codigo) == (429, "cola_llena")

    def falla():
        raise RuntimeError("se rompió")

    soltar.set()
    for t in en_cola:
        while trabajos.ver(t["evaluacion_id"])["estado"] != "terminada":
            time.sleep(0.02)
    fallida = trabajos.encolar({"episodios": 1}, falla)
    while (vista := trabajos.ver(fallida["evaluacion_id"]))["estado"] in ("en_cola", "en_curso"):
        time.sleep(0.02)
    assert vista["estado"] == "fallida" and vista["error"]["codigo"] == "error_interno"
    assert trabajos.ver(primero["evaluacion_id"])["resultado"] == {"ok": True}
    reloj[0] += 1801  # 30 min sin consultar: caducan
    with pytest.raises(ErrorModelo) as exc:
        trabajos.ver(primero["evaluacion_id"])
    assert (exc.value.estado_http, exc.value.codigo) == (404, "evaluacion_no_encontrada")

