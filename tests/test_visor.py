"""Capa /api/* sobre Render (api/_visor.py): sesión del visor, fichas de modelo, almacén de sesiones y «Evaluar» rápido.

Usan el repositorio real (manifiestos, `models/numpy/`, mapas y catálogo); no necesitan DVC, torch ni red.
"""
import json
import subprocess
import sys
from pathlib import Path

import pytest

from api._episodios import Metricas
from api._modelos import AlmacenModelos, ErrorModelo
from api._visor import AlmacenSesiones, Contexto, ErrorSesion, SesionVisor, evaluar_diagnostico

REPO = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def ctx():
    return Contexto(AlmacenModelos(REPO), REPO, Metricas())


def correr(sesion: SesionVisor, limite: int = 500) -> dict:
    payload = sesion.payload()
    while not payload["done"] and limite:
        payload, limite = sesion.step(), limite - 1
    return payload


def codigo(fn, *args, **kwargs):
    with pytest.raises(ErrorModelo) as exc:
        fn(*args, **kwargs)
    return exc.value.estado_http, exc.value.codigo


# --- Modo libre (heurística, aleatoria, manual) -----------------------------------------------------

def test_sesion_por_defecto_es_la_misma_que_crea_vercel_sin_cookie(ctx):
    p = SesionVisor(ctx).payload()
    assert (p["policy"], p["makeup"], p["seed"], p["state"]["pasillo_bloqueado"]) == ("heuristic", True, 10_000, True)
    assert p["model"] is None and p["environment_version"] == "warehouse-v10" and p["sesion_id"] is None
    assert p["route_kind"] == "bfs_reference" and p["route"]
    assert p["state"]["inventory"]["catalog_version"] == "trendy-27-v1"


def test_inventario_compartido_entre_pedidos_de_la_misma_sesion(ctx):
    """«Generar pedido»: el stock baja pedido tras pedido y no se repone dentro de la sesión; otra sesión no lo ve."""
    sesion = SesionVisor(ctx, {"makeup": True, "orders": 1, "policy": "heuristic", "blocked": False, "seed": 1})
    inventario = sesion.inventory
    inicial = sum(inventario.total.values())
    unidades = sum(l["quantity"] for l in sesion.env.lines)
    assert correr(sesion)["info"]["success"]
    assert inicial - sum(inventario.total.values()) == unidades
    siguiente = sesion.reset({"makeup": True, "orders": 1, "policy": "heuristic", "blocked": False, "seed": 2})
    assert sesion.inventory is inventario  # el mismo libro de inventario
    assert sum(inventario.total.values()) == inicial - unidades  # sin reposición
    assert siguiente["sesion_id"] is None
    otra = SesionVisor(ctx, {"makeup": True, "orders": 1, "policy": "heuristic", "blocked": False, "seed": 1})
    assert sum(otra.inventory.total.values()) == inicial  # inventario propio


def test_pedido_por_semilla_es_reproducible(ctx):
    def lineas(semilla):
        s = SesionVisor(ctx, {"makeup": True, "orders": 1, "policy": "heuristic", "seed": semilla})
        return [(l["sku"], l["quantity"]) for l in s.env.lines]

    assert lineas(123) == lineas(123) and lineas(123) != lineas(124)


def test_modo_manual_aleatorio_y_acciones_invalidas(ctx):
    manual = SesionVisor(ctx, {"makeup": True, "orders": 1, "policy": "manual"})
    assert manual.step(1)["last_action"]["name"] == "GIRAR_IZQUIERDA"
    with pytest.raises(ValueError, match="manual"):
        SesionVisor(ctx, {"makeup": True, "orders": 1, "policy": "heuristic"}).step(1)
    with pytest.raises(ValueError):
        manual.step(99)
    aleatoria = SesionVisor(ctx, {"makeup": True, "orders": 1, "policy": "random", "seed": 7})
    assert aleatoria.step()["last_action"]["name"]


def test_modo_antiguo_sin_maquillaje_sigue_funcionando(ctx):
    """Decisión del equipo: se deja funcionando (el motor lo trae) hasta que Naomi decida si se quita."""
    sesion = SesionVisor(ctx, {"makeup": False, "orders": 2, "policy": "heuristic", "blocked": False, "seed": 10_000})
    p = correr(sesion)
    assert p["makeup"] is False and p["orders"] == 2 and p["info"]["success"]


def test_ppo_generico_ya_no_existe_y_un_reset_invalido_no_destruye_la_sesion(ctx):
    sesion = SesionVisor(ctx, {"makeup": True, "orders": 1, "policy": "heuristic", "seed": 5})
    antes = sesion.payload()
    for ajustes, mensaje in (({"policy": "ppo", "orders": 1}, "catálogo"), ({"policy": "magia"}, "Política"),
                             ({"orders": 7}, "orders"), ({"seed": -1}, "seed"), ({"blocked": "si"}, "blocked")):
        with pytest.raises(ValueError, match=mensaje):
            sesion.reset({"makeup": True, **ajustes})
    assert sesion.payload() == antes


# --- Modelos del catálogo ---------------------------------------------------------------------------

def test_modelo_de_produccion_completa_con_el_paso_cerrado_y_trae_su_ficha(ctx):
    sesion = SesionVisor(ctx)
    p = sesion.reset({"policy": "ppo", "model": "m1b-i1-seed1-best", "blocked": True, "seed": 10_000})
    assert p["policy"] == "ppo" and p["makeup"] and p["orders"] == 3 and p["model"]["id"] == "m1b-i1-seed1-best"
    final = correr(sesion)
    assert final["info"]["success"] and final["info"]["steps"] == 111 and final["info"]["collisions"] == 0  # = /episodios
    ficha = final["model"]
    assert ficha["estado"] == "recomendado" and ficha["nivel"] == "N3 · paso (6,14) cerrado"
    assert ficha["environment_version"] == "warehouse-v10" and len(ficha["model_sha256"]) == 64
    assert set(ficha["test_final"]["ppo"]) == {"abierto", "cerrado (6,14)"}  # lo que lee modelDetail() de la web
    assert ficha["test_final"]["ppo"]["cerrado (6,14)"]["success_rate"] == 1.0
    assert sesion.inventory.catalog_version == "trendy-27-v1"


def test_modelo_con_un_reset_de_otro_modelo_cambia_ficha_y_nivel(ctx):
    sesion = SesionVisor(ctx)
    sesion.reset({"policy": "ppo", "model": "m1b-i1-seed1-best", "blocked": True, "seed": 10_000})
    p = sesion.reset({"policy": "ppo", "model": "m1-c3-seed0", "blocked": False, "seed": 10_000})
    assert p["model"]["id"] == "m1-c3-seed0" and p["model"]["nivel"] == "N2 · mapa con muro"
    assert set(p["model"]["test_final"]["ppo"]) == {"abierto"}
    assert correr(sesion)["info"]["steps"] == 88  # = medir_rollback.py (trendy-27, paso abierto, semilla 10000)
    volver = sesion.reset({"makeup": True, "orders": 1, "policy": "heuristic", "seed": 3})
    assert volver["model"] is None  # vuelve a la misión libre con inventario nuevo


def test_modelo_desconocido_o_incompatible_no_destruye_la_sesion(ctx):
    sesion = SesionVisor(ctx)
    antes = sesion.payload()
    assert codigo(sesion.reset, {"policy": "ppo", "model": "no-existe"}) == (404, "modelo_no_encontrado")
    assert codigo(sesion.reset, {"policy": "ppo", "model": "m1o-e4l-seed0"}) == (409, "modelo_incompatible")
    with pytest.raises(ValueError, match="política ppo"):
        sesion.reset({"policy": "heuristic", "model": "m1-c3-seed0"})
    with pytest.raises(ValueError, match="model debe ser"):
        sesion.reset({"policy": "ppo", "model": 5})
    assert sesion.payload() == antes


def test_layout_lista_solo_los_dos_recomendados_sin_el_ppo_antiguo(ctx):
    layout = SesionVisor(ctx).layout_payload()
    assert [m["id"] for m in layout["models"]] == ["m1b-i1-seed1-best", "m1-c3-seed0"]  # producción primero
    assert layout["available_ppo"] == {"1": False, "2": False}
    assert (layout["catalog_version"], len(layout["catalog"])) == ("trendy-27-v1", 27)
    assert layout["environment_version"] == "0.4.0"  # igual que /api/layout de Vercel (versión del mapa)
    assert layout["layout_sha256"] and layout["layout"]["version"] == "0.4.0"


def test_todo_el_visor_funciona_sin_torch_ni_sb3():
    """Como en la imagen de Render: torch y SB3 bloqueados; layout, modelo y diagnóstico funcionan."""
    codigo_py = (
        "import sys\n"
        "sys.modules['torch'] = None; sys.modules['stable_baselines3'] = None\n"
        "from api._episodios import Metricas\n"
        "from api._modelos import AlmacenModelos\n"
        "from api._visor import Contexto, SesionVisor, evaluar_diagnostico\n"
        "ctx = Contexto(AlmacenModelos(), __import__('pathlib').Path('.').resolve(), Metricas())\n"
        "s = SesionVisor(ctx); lay = s.layout_payload()\n"
        "s.reset({'policy': 'ppo', 'model': 'm1b-i1-seed1-best', 'blocked': True, 'seed': 10000})\n"
        "while not s.done: s.step()\n"
        "d = evaluar_diagnostico(ctx, 'm1b-i1-seed1-best', True, 2, 10000)\n"
        "print(len(lay['models']), s.info['success'], d['summary']['success_rate'], d['certificado'])\n")
    salida = subprocess.run([sys.executable, "-c", codigo_py], cwd=REPO, capture_output=True, text=True, timeout=180)
    assert salida.returncode == 0, salida.stderr[-600:]
    assert salida.stdout.split() == ["2", "True", "1.0", "False"]


# --- Almacén de sesiones ----------------------------------------------------------------------------

def test_almacen_crea_con_id_busca_y_caduca_a_los_30_minutos(ctx):
    reloj = [0.0]
    almacen = AlmacenSesiones(ctx, reloj=lambda: reloj[0])
    sesion = almacen.crear({"makeup": True, "orders": 1, "policy": "heuristic", "seed": 1})
    assert sesion.sesion_id and sesion.payload()["sesion_id"] == sesion.sesion_id
    assert almacen.obtener(sesion.sesion_id) is sesion
    reloj[0] += 1500
    almacen.obtener(sesion.sesion_id)  # cada uso renueva
    reloj[0] += 1500
    assert almacen.obtener(sesion.sesion_id) is sesion
    reloj[0] += 1801
    assert codigo(almacen.obtener, sesion.sesion_id) == (404, "sesion_no_encontrada")
    assert almacen.estado()["sesiones"] == 0


def test_almacen_con_ajustes_invalidos_no_guarda_nada(ctx):
    almacen = AlmacenSesiones(ctx)
    with pytest.raises(ValueError):
        almacen.crear({"makeup": True, "orders": 9})
    assert almacen.estado()["sesiones"] == 0


def test_almacen_lleno_descarta_la_terminada_o_responde_429(ctx):
    almacen = AlmacenSesiones(ctx, maximo=2)
    ajustes = {"makeup": True, "orders": 1, "policy": "heuristic", "blocked": False, "seed": 1}
    a, b = almacen.crear(ajustes), almacen.crear(ajustes)
    assert codigo(almacen.crear, ajustes) == (429, "demasiadas_sesiones")  # ambas activas
    correr(a)  # a termina: es la que se descarta
    c = almacen.crear(ajustes)
    assert codigo(almacen.obtener, a.sesion_id) == (404, "sesion_no_encontrada")
    assert almacen.obtener(b.sesion_id) is b and almacen.obtener(c.sesion_id) is c


def test_layout_sin_sesion_no_guarda_sesiones_y_se_calcula_una_vez(ctx):
    almacen = AlmacenSesiones(ctx)
    primero = almacen.layout_defecto()
    assert almacen.layout_defecto() is primero and almacen.estado()["sesiones"] == 0
    assert len(primero["models"]) == 2


def test_fin_de_sesion_y_decisiones_alimentan_el_monitoreo():
    metricas = Metricas()
    contexto = Contexto(AlmacenModelos(REPO), REPO, metricas)
    sesion = SesionVisor(contexto)
    sesion.reset({"policy": "ppo", "model": "m1b-i1-seed1-best", "blocked": True, "seed": 10_000})
    correr(sesion)
    correr(sesion)  # ya terminada: no vuelve a contar
    resumen = metricas.resumen()
    fila = next(f for f in resumen["exito_por_escenario"] if f["quien"] == "m1b-i1-seed1-best")
    assert (fila["escenario"], fila["episodios"], fila["exitos"], fila["origen"]) == ("m1b/cerrado", 1, 1, {"visor": 1})
    assert resumen["latencia_decision"]["m1b-i1-seed1-best"]["n"] == 111


# --- «Evaluar» rápido (diagnóstico no certificado) --------------------------------------------------

def test_diagnostico_declara_que_no_es_certificado_y_usa_el_catalogo_de_la_web(ctx):
    r = evaluar_diagnostico(ctx, "m1b-i1-seed1-best", True, 3, 10_000)
    assert r["certificado"] is False and "NO certificado" in r["nota"] and "/evaluaciones" in r["nota"]
    assert r["catalog"] == "trendy-27-v1" and r["scenario"] == "cerrado" and r["seeds"] == [10_000, 10_002]
    assert r["mode"] == "evaluation" and r["model"]["id"] == "m1b-i1-seed1-best"
    assert [e["seed"] for e in r["episodes"]] == [10_000, 10_001, 10_002]
    assert r["summary"]["success_rate"] == 1.0 and r["summary"]["end_reasons"] == {"success": 3}
    assert set(r["monitoring"]) == {"inference_ms_mean", "inference_ms_p95", "steps", "errors", "served_sha256", "inferencia"}
    assert r["monitoring"]["served_sha256"] == r["model"]["model_sha256"] and r["monitoring"]["errors"] == 0
    assert set(r["episodes"][0]) == {"seed", "success", "steps", "collisions", "deliveries", "reward", "end_reason"}


def test_diagnostico_del_rollback_con_el_paso_cerrado_falla(ctx):
    r = evaluar_diagnostico(ctx, "m1-c3-seed0", True, 2, 10_000)  # = rollback_m1-c3-seed0.json, trendy-27, cerrado
    assert r["summary"]["success_rate"] == 0.0 and r["certificado"] is False
    esperado = json.loads((REPO / "docs/resultados/eval/catalogo-trendy-27/rollback_m1-c3-seed0.json").read_text())
    for fila in r["episodes"]:
        e = next(x for x in esperado["casos"]["trendy-27-v1 | cerrado"]["episodios"] if x["seed"] == fila["seed"])
        assert (fila["end_reason"], fila["steps"], fila["collisions"]) == (e["end_reason"], e["steps"], e["collisions"])


def test_diagnostico_valida_sus_parametros(ctx):
    for args, mensaje in (((None, False, 10, 1), "model debe ser"), (("m1-c3-seed0", "no", 10, 1), "booleano"),
                          (("m1-c3-seed0", False, 0, 1), "1 a 20"), (("m1-c3-seed0", False, 21, 1), "1 a 20"),
                          (("m1-c3-seed0", False, 10, -5), "seed")):
        with pytest.raises(ValueError, match=mensaje):
            evaluar_diagnostico(ctx, *args)
    assert codigo(evaluar_diagnostico, ctx, "no-existe") == (404, "modelo_no_encontrado")
    assert codigo(evaluar_diagnostico, ctx, "m1o-e4l-seed0") == (409, "modelo_incompatible")


def test_diagnostico_alimenta_el_monitoreo_como_diagnostico():
    metricas = Metricas()
    evaluar_diagnostico(Contexto(AlmacenModelos(REPO), REPO, metricas), "m1b-i1-seed1-best", False, 2, 10_000)
    fila = next(f for f in metricas.resumen()["exito_por_escenario"] if f["quien"] == "m1b-i1-seed1-best")
    assert fila["origen"] == {"diagnostico": 2} and fila["escenario"] == "m1b/abierto"


# --- Rutas /api/* por HTTP (mismas rutas y formatos que usa la web) -------------------------------------

from fastapi.testclient import TestClient  # noqa: E402

from api._app import create_app  # noqa: E402

ORIGEN = "https://warehouse-rush-psi.vercel.app"


@pytest.fixture
def cliente(monkeypatch):
    monkeypatch.setenv("CORS_ORIGINS", ORIGEN)
    monkeypatch.delenv("CORS_ORIGIN_REGEX", raising=False)
    with TestClient(create_app(REPO, precargar=False)) as c:
        yield c


def con_id(sesion_id):
    return {"X-Sesion": sesion_id}


def test_layout_sin_sesion_no_crea_ninguna_y_lista_los_dos_recomendados(cliente):
    r = cliente.get("/api/layout")
    assert r.status_code == 200 and "x-sesion" not in r.headers
    d = r.json()
    assert [m["id"] for m in d["models"]] == ["m1b-i1-seed1-best", "m1-c3-seed0"]
    assert d["available_ppo"] == {"1": False, "2": False} and (d["catalog_version"], len(d["catalog"])) == ("trendy-27-v1", 27)
    assert cliente.get("/monitoreo").json()["sesiones"]["sesiones"] == 0


def test_state_sin_cabecera_crea_una_sesion_y_con_ella_devuelve_la_misma(cliente):
    r = cliente.get("/api/state")
    assert r.status_code == 200
    sesion = r.json()["sesion_id"]
    assert sesion and r.headers["x-sesion"] == sesion
    assert (r.json()["policy"], r.json()["makeup"]) == ("heuristic", True)
    de_nuevo = cliente.get("/api/state", headers=con_id(sesion)).json()
    assert de_nuevo["sesion_id"] == sesion and de_nuevo["seed"] == r.json()["seed"]
    assert cliente.get("/monitoreo").json()["sesiones"]["sesiones"] == 1


def test_state_con_id_desconocido_responde_404_en_formato_vercel_con_codigo(cliente):
    r = cliente.get("/api/state", headers=con_id("no-existe"))
    assert r.status_code == 404
    cuerpo = r.json()
    assert isinstance(cuerpo["error"], str) and "reinicia la misión" in cuerpo["error"]  # la web hace new Error(result.error)
    assert cuerpo["codigo"] == "sesion_no_encontrada"


def test_reset_mantiene_el_id_y_sin_id_o_con_id_caducado_crea_una_sesion_nueva(cliente):
    cuerpo = {"orders": 1, "policy": "heuristic", "blocked": False, "seed": 7, "makeup": True}
    primera = cliente.post("/api/reset", json=cuerpo).json()
    assert primera["sesion_id"] and primera["seed"] == 7
    misma = cliente.post("/api/reset", json={**cuerpo, "seed": 8}, headers=con_id(primera["sesion_id"])).json()
    assert misma["sesion_id"] == primera["sesion_id"] and misma["seed"] == 8
    nueva = cliente.post("/api/reset", json=cuerpo, headers=con_id("caducada")).json()
    assert nueva["sesion_id"] not in (None, primera["sesion_id"])
    assert cliente.get("/monitoreo").json()["sesiones"]["sesiones"] == 2


def test_sesiones_aisladas_y_mision_completa_por_http(cliente):
    ajustes = {"orders": 1, "policy": "heuristic", "blocked": False, "seed": 11, "makeup": True}
    a = cliente.post("/api/reset", json=ajustes).json()["sesion_id"]
    b = cliente.post("/api/reset", json=ajustes).json()["sesion_id"]
    for _ in range(6):
        cliente.post("/api/step", json={}, headers=con_id(a))
    assert cliente.get("/api/state", headers=con_id(a)).json()["state"]["tiempo"] == 6
    assert cliente.get("/api/state", headers=con_id(b)).json()["state"]["tiempo"] == 0
    p = cliente.get("/api/state", headers=con_id(b)).json()
    while not p["done"]:
        p = cliente.post("/api/step", json={}, headers=con_id(b)).json()
    assert p["info"]["success"] and p["events"][-1]["kind"] == "end"
    assert cliente.post("/api/step", json={}, headers=con_id(b)).json()["error"].startswith("El episodio terminó")


def test_step_manual_sin_cabecera_y_con_acciones_invalidas(cliente):
    sin = cliente.post("/api/step", json={})
    assert (sin.status_code, sin.json()["codigo"]) == (400, "falta_sesion")
    s = cliente.post("/api/reset", json={"orders": 1, "policy": "manual", "makeup": True}).json()["sesion_id"]
    ok = cliente.post("/api/step", json={"action": 1}, headers=con_id(s))
    assert ok.status_code == 200 and ok.json()["last_action"]["name"] == "GIRAR_IZQUIERDA"
    mala = cliente.post("/api/step", json={"action": 99}, headers=con_id(s))
    assert mala.status_code == 400 and isinstance(mala.json()["error"], str)
    assert cliente.post("/api/step", json={"action": 1}, headers=con_id("x")).status_code == 404


def test_reset_con_modelo_trae_la_ficha_y_las_cabeceras_de_version(cliente):
    r = cliente.post("/api/reset", json={"policy": "ppo", "model": "m1b-i1-seed1-best", "blocked": True, "seed": 10_000})
    d = r.json()
    assert r.status_code == 200 and d["model"]["id"] == "m1b-i1-seed1-best" and d["orders"] == 3
    assert r.headers["x-modelo-servido"].startswith("m1b-i1-seed1-best@") and r.headers["x-git-commit"]
    assert r.headers["x-sesion"] == d["sesion_id"]
    desconocido = cliente.post("/api/reset", json={"policy": "ppo", "model": "no-existe"}, headers=con_id(d["sesion_id"]))
    assert (desconocido.status_code, desconocido.json()["codigo"]) == (404, "modelo_no_encontrado")
    assert isinstance(desconocido.json()["error"], str)
    incompatible = cliente.post("/api/reset", json={"policy": "ppo", "model": "m1o-e4l-seed0"})
    assert (incompatible.status_code, incompatible.json()["codigo"]) == (409, "modelo_incompatible")
    generico = cliente.post("/api/reset", json={"policy": "ppo", "orders": 1, "makeup": True})
    assert generico.status_code == 400 and "catálogo" in generico.json()["error"]
    assert cliente.get("/api/state", headers=con_id(d["sesion_id"])).json()["model"]["id"] == "m1b-i1-seed1-best"  # intacta


def test_modo_antiguo_sin_maquillaje_por_http(cliente):
    d = cliente.post("/api/reset", json={"orders": 2, "policy": "heuristic", "blocked": False, "seed": 10_000, "makeup": False}).json()
    assert d["makeup"] is False and d["orders"] == 2 and d["model"] is None


def test_errores_de_formato_siguen_el_estilo_de_vercel(cliente):
    cruda = cliente.post("/api/reset", content=b"no es json", headers={"Content-Type": "application/json"})
    assert cruda.status_code == 400 and isinstance(cruda.json()["error"], str)
    lista = cliente.post("/api/reset", content=b"[1]", headers={"Content-Type": "application/json"})
    assert lista.status_code == 400 and "objeto JSON" in lista.json()["error"]
    vacio = cliente.post("/api/reset", content=b"", headers={"Content-Type": "application/json"})
    assert vacio.status_code == 400
    grande = cliente.post("/api/reset", content=json.dumps({"x": "a" * 5000}).encode(), headers={"Content-Type": "application/json"})
    assert grande.status_code == 400
    texto = cliente.post("/api/reset", content=b"{}", headers={"Content-Type": "text/plain"})
    assert (texto.status_code, texto.json()["codigo"]) == (415, "tipo_no_soportado")
    desconocida = cliente.get("/api/nada")
    assert desconocida.status_code == 404 and desconocida.json() == {"error": "Ruta desconocida", "codigo": "ruta_no_encontrada"}
    # fuera de /api/* sigue el formato uniforme de la API nueva
    assert set(cliente.get("/nada").json()["error"]) == {"codigo", "mensaje", "detalle"}


def test_evaluate_declara_que_no_es_certificado(cliente):
    r = cliente.post("/api/evaluate", json={"model": "m1b-i1-seed1-best", "blocked": True, "episodes": 2})
    d = r.json()
    assert r.status_code == 200 and d["certificado"] is False and d["catalog"] == "trendy-27-v1"
    assert d["seeds"] == [10_000, 10_001] and d["summary"]["success_rate"] == 1.0 and d["scenario"] == "cerrado"
    assert d["monitoring"]["served_sha256"] == d["model"]["model_sha256"]
    for cuerpo in ({"model": "m1b-i1-seed1-best", "episodes": 21}, {"episodes": 3}, {"model": "m1b-i1-seed1-best", "blocked": "si"}):
        malo = cliente.post("/api/evaluate", json=cuerpo)
        assert malo.status_code == 400 and isinstance(malo.json()["error"], str)
    assert cliente.post("/api/evaluate", json={"model": "nada"}).status_code == 404


def test_evaluate_rapido_corre_de_a_uno(cliente):
    visor = cliente.app.state.visor
    assert visor._diagnostico.acquire(blocking=False)
    try:
        r = cliente.post("/api/evaluate", json={"model": "m1b-i1-seed1-best", "episodes": 1})
        assert (r.status_code, r.json()["codigo"]) == (429, "diagnostico_en_curso") and isinstance(r.json()["error"], str)
    finally:
        visor._diagnostico.release()
    assert cliente.post("/api/evaluate", json={"model": "m1b-i1-seed1-best", "episodes": 1}).status_code == 200


def test_api_health_alias_con_modelos_servidos_y_commit(cliente):
    d = cliente.get("/api/health").json()
    assert d["status"] == "ok" and d["environment_version"] == "warehouse-v10" and d["commit"]
    assert [m["id"] for m in d["served_models"]] == ["m1b-i1-seed1-best", "m1-c3-seed0"]
    assert d["servido"] == cliente.get("/version").json()["run_id"] and "X-Sesion" in d["session_mode"]


def test_cors_permite_y_expone_x_sesion_solo_al_origen_configurado(cliente):
    pre = cliente.options("/api/step", headers={"Origin": ORIGEN, "Access-Control-Request-Method": "POST",
                                                 "Access-Control-Request-Headers": "content-type,x-sesion"})
    assert pre.status_code == 200 and pre.headers["access-control-allow-origin"] == ORIGEN
    assert "x-sesion" in pre.headers["access-control-allow-headers"].lower()
    assert "access-control-allow-credentials" not in pre.headers
    r = cliente.post("/api/reset", json={"orders": 1, "policy": "heuristic", "makeup": True}, headers={"Origin": ORIGEN})
    expuestas = r.headers["access-control-expose-headers"]
    assert "X-Sesion" in expuestas and "X-Modelo-Servido" in expuestas and "X-Git-Commit" in expuestas
    otro = cliente.options("/api/step", headers={"Origin": "https://otro.example", "Access-Control-Request-Method": "POST",
                                                  "Access-Control-Request-Headers": "x-sesion"})
    assert "access-control-allow-origin" not in otro.headers


# --- Paridad con ViewerSession (/api de Vercel) y con el ambiente directo ---------------------------
# Adaptadas de tests/test_viewer.py y tests/test_served_models.py (Lis): el visor de Render debe hacer lo mismo
# que el visor de Vercel, con la política NumPy en lugar de torch.

import re  # noqa: E402

from api._viewer import ViewerSession  # noqa: E402
from envs import make_env  # noqa: E402
from envs.env import WarehouseRushEnv  # noqa: E402
from pipelines.baselines import HeuristicPolicy  # noqa: E402

UUID = re.compile(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}")


def normalizar(payload: dict) -> dict:
    """Quita lo que por diseño difiere entre dos sesiones iguales: el id de sesión y los UUID de los pedidos."""
    return json.loads(UUID.sub("<uuid>", json.dumps({k: v for k, v in payload.items() if k != "sesion_id"})))


@pytest.mark.parametrize("ajustes,acciones", [
    ({"makeup": True, "orders": 1, "policy": "heuristic", "blocked": False, "seed": 3}, [None] * 20),
    ({"makeup": True, "orders": 1, "policy": "heuristic", "blocked": True, "seed": 4}, [None] * 20),
    ({"makeup": True, "orders": 1, "policy": "random", "blocked": False, "seed": 9}, [None] * 15),
    ({"makeup": True, "orders": 1, "policy": "manual", "blocked": False, "seed": 5}, [1, 0, 0, 2, 3, 0, 4, 6, 7, 1]),
    ({"makeup": False, "orders": 2, "policy": "heuristic", "blocked": False, "seed": 10_000}, [None] * 20),
    ({"makeup": False, "orders": 1, "policy": "random", "blocked": True, "seed": 2}, [None] * 15),
])
def test_payload_identico_al_de_viewersession_paso_a_paso(ctx, ajustes, acciones):
    viejo, nuevo = ViewerSession(settings=ajustes), SesionVisor(ctx, ajustes)
    assert normalizar(nuevo.payload()) == normalizar(viejo.payload())
    for accion in acciones:
        assert normalizar(nuevo.step(accion)) == normalizar(viejo.step(accion))
    # mapa, catálogo y huella: se leen del ambiente del visor viejo porque su layout_payload() consulta SB3
    layout = nuevo.layout_payload()
    assert layout["layout"] == viejo.env.layout.data and layout["layout_sha256"] == viejo.env.layout.digest
    assert layout["catalog"] == list(viejo.inventory.catalog.values())
    assert layout["catalog_version"] == viejo.inventory.catalog_version


def test_inventario_compartido_identico_al_de_viewersession(ctx):
    """Dos pedidos seguidos en la misma sesión: el stock restante coincide con el de Vercel."""
    ajustes = {"makeup": True, "orders": 1, "policy": "heuristic", "blocked": False, "seed": 21}
    viejo, nuevo = ViewerSession(settings=ajustes), SesionVisor(ctx, ajustes)
    for sesion in (viejo, nuevo):
        correr(sesion)
        sesion.reset({**ajustes, "seed": 22})
        correr(sesion)
    assert normalizar(nuevo.payload()) == normalizar(viejo.payload())
    assert nuevo.inventory.total == viejo.inventory.total


@pytest.mark.parametrize("orders,blocked", [(1, False), (1, True), (2, False), (2, True)])
def test_pasos_identicos_al_ambiente_de_python_en_el_modo_antiguo(ctx, orders, blocked):
    sesion = SesionVisor(ctx)
    payload = sesion.reset({"orders": orders, "blocked": blocked, "policy": "heuristic"})
    referencia = WarehouseRushEnv(orders, blocked)
    observation, _ = referencia.reset(seed=10_000)
    politica = HeuristicPolicy()
    while not payload["done"]:
        accion = politica.action(observation, referencia)
        observation, recompensa, terminado, truncado, _ = referencia.step(accion)
        payload = sesion.step()
        assert payload["state"] == referencia.snapshot() and payload["last_action"]["code"] == accion
        assert payload["last_reward"] == recompensa and payload["observation"] == observation.tolist()
        assert payload["terminated"] == terminado and payload["truncated"] == truncado
    assert payload["info"]["success"] and payload["route"] == [] and payload["events"][-1]["text"] == "Misión completada"
    with pytest.raises(ValueError, match="terminó"):
        sesion.step()


def test_acciones_manuales_y_reset_invalido_conservan_el_estado_real(ctx):
    sesion = SesionVisor(ctx)
    sesion.reset({"policy": "manual", "orders": 1, "blocked": False})
    with pytest.raises(ValueError, match="manual"):
        sesion.step()
    payload = sesion.step(0)  # pared interior frente a BASE
    assert payload["state"]["colisiones"] == 1 and (payload["state"]["x"], payload["state"]["y"]) == (2, 11)
    antes = sesion.payload()
    with pytest.raises(ValueError):
        sesion.reset({"orders": 3})
    with pytest.raises(ValueError):
        sesion.step(1.5)
    assert sesion.payload() == antes


def test_ruta_de_referencia_respeta_el_mapa_y_el_cierre(ctx):
    sesion = SesionVisor(ctx)
    normal = sesion.reset({"orders": 1, "blocked": False})
    cerrada = sesion.reset({"orders": 1, "blocked": True})
    assert len(cerrada["route"]) > len(normal["route"])
    assert [4, 10] in normal["route"] and [4, 10] not in cerrada["route"]
    for celda in cerrada["route"]:
        assert sesion.env.layout.free(tuple(celda), True)
    assert tuple(cerrada["route"][-1]) in sesion.env.layout.approaches("P1", True)
    assert sesion.layout_payload()["layout_sha256"] == sesion.env.layout.digest and cerrada["route_kind"] == "bfs_reference"


CASOS_MODELO = [("m1b-i1-seed1-best", True, 10_000), ("m1b-i1-seed1-best", False, 10_001),
                ("m1-c3-seed0", False, 10_002), ("m1-c3-seed0", True, 10_000)]


@pytest.mark.parametrize("modelo,bloqueado,semilla", CASOS_MODELO)
def test_episodio_por_http_identico_a_la_evaluacion_directa(cliente, ctx, modelo, bloqueado, semilla):
    """Cada paso de /api/step reproduce el ambiente con la política NumPy fuera de la API (misma recompensa y celda)."""
    cargado = ctx.almacen.obtener(modelo)
    manifest = cargado.manifiesto
    env = make_env(bloqueado, str(REPO / manifest["layout_path"]), 3, manifest.get("reward_overrides") or None,
                   catalog="trendy-27-v1")
    obs, _ = env.reset(seed=semilla)
    directo, hecho = [], False
    while not hecho:
        obs, recompensa, terminado, truncado, info = env.step(cargado.politica.action(obs, env))
        directo.append((tuple(env.position), round(recompensa, 6)))
        hecho = terminado or truncado
    estado = cliente.post("/api/reset", json={"policy": "ppo", "model": modelo, "blocked": bloqueado, "seed": semilla}).json()
    sesion, visor = estado["sesion_id"], []
    assert estado["model"]["id"] == modelo and estado["environment_version"] == "warehouse-v10"
    while not estado["done"]:
        estado = cliente.post("/api/step", json={}, headers=con_id(sesion)).json()
        visor.append((tuple(estado["trail"][-1]), round(estado["last_reward"], 6)))
    assert [r for _, r in visor] == [r for _, r in directo] and visor[-1][0] == directo[-1][0]
    assert estado["info"]["success"] == info["success"] and estado["info"]["steps"] == info["steps"]


@pytest.mark.parametrize("modelo,bloqueado,semilla", CASOS_MODELO)
def test_visor_y_episodios_dan_el_mismo_resultado(cliente, modelo, bloqueado, semilla):
    """Las dos formas de jugar un modelo en la API (/api/* y /episodios) terminan igual."""
    visor = cliente.post("/api/reset", json={"policy": "ppo", "model": modelo, "blocked": bloqueado, "seed": semilla}).json()
    id_visor = visor["sesion_id"]
    while not visor["done"]:
        visor = cliente.post("/api/step", json={}, headers=con_id(id_visor)).json()
    episodio = cliente.post("/episodios", json={"run_id": modelo, "bloqueado": bloqueado, "seed": semilla}).json()
    final = cliente.post(f"/episodios/{episodio['episodio_id']}/correr").json()["final"]
    for clave in ("success", "end_reason", "steps", "collisions", "deliveries", "total_reward"):
        assert visor["info"][clave] == final["info"][clave], clave
    assert visor["state"]["order"]["lines"] == final["state"]["order"]["lines"]


def test_visor_con_numpy_da_las_mismas_acciones_que_sb3():
    """Si hay torch y los pesos de DVC: la sesión del visor (NumPy) decide igual que SB3 en todo el episodio."""
    pytest.importorskip("torch")
    pesos = REPO / "models/m1-c3-seed0/model.zip"
    if not pesos.is_file():
        pytest.skip("pesos de DVC no descargados (dvc pull models/m1-c3-seed0.dvc)")
    from pipelines.baselines import make_policy

    contexto = Contexto(AlmacenModelos(REPO), REPO, Metricas())
    sesion = SesionVisor(contexto)
    sesion.reset({"policy": "ppo", "model": "m1-c3-seed0", "blocked": True, "seed": 10_000})  # 400 pasos: el caso largo
    sb3 = make_policy("ppo", model_path=pesos)
    pasos = 0
    while not sesion.done:
        esperado = sb3.action(sesion.observation, sesion.env)
        assert sesion.step()["last_action"]["code"] == esperado
        pasos += 1
    assert pasos == 400
