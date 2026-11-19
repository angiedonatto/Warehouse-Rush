#!/usr/bin/env bash
# Publica la API de Warehouse Rush: imagen desde un commit → GHCR (privado) → deploy en Render → /version.
#
# Mide por separado: build, push a GHCR y el tiempo desde el deploy hook hasta que /version muestra el commit
# (ese total es el tiempo de redeploy/rollback que se reporta en docs/rollback.md). Deja la evidencia en
# docs/resultados/despliegues/<fecha>-<sha7>.json.
#
# Uso (desde cualquier carpeta del repo, con el árbol limpio y el commit ya subido a origin):
#   api/publicar.sh [--motivo "texto"] [--solo-imagen] [--sin-pruebas]
#     --solo-imagen   construye y sube la imagen, sin desplegar (no necesita el deploy hook)
#     --sin-pruebas   no corre las pruebas de la API antes de construir
#
# Variables (en .env o en el entorno; .env está fuera de Git):
#   RENDER_DEPLOY_HOOK   URL secreta del deploy hook del servicio (Render → Settings → Deploy Hook). NUNCA se imprime.
#   GHCR_TOKEN           opcional: si está, hace `docker login ghcr.io` (write:packages) leyendo el token por stdin.
#   GHCR_USUARIO         usuario de GHCR (por defecto mamezquita)
#   WAREHOUSE_IMAGEN     repositorio de la imagen (por defecto ghcr.io/mamezquita/warehouse-rush-api)
#   WAREHOUSE_API_URL    URL pública de la API (por defecto https://warehouse-rush-api.onrender.com)
#   WAREHOUSE_ESPERA_MAX segundos máximos esperando /version (por defecto 900)
set -euo pipefail
set +x  # nunca trazar: el deploy hook y el token son secretos

MOTIVO="" SOLO_IMAGEN=0 PRUEBAS=1
while [ $# -gt 0 ]; do
  case "$1" in
    --motivo) MOTIVO="${2:-}"; shift 2 ;;
    --solo-imagen) SOLO_IMAGEN=1; shift ;;
    --sin-pruebas) PRUEBAS=0; shift ;;
    -h|--help) sed -n '2,20p' "$0"; exit 0 ;;
    *) echo "opción desconocida: $1 (ver --help)" >&2; exit 2 ;;
  esac
done

RAIZ=$(git rev-parse --show-toplevel)
cd "$RAIZ"

# Lee una variable de .env sin imprimirla ni exportarla al resto de procesos.
leer_env() {
  local nombre="$1" valor="${!1:-}"
  if [ -z "$valor" ] && [ -f .env ]; then
    valor=$(grep -E "^${nombre}=" .env | tail -1 | cut -d= -f2- | tr -d '\r' | sed -e 's/^"//' -e 's/"$//') || true
  fi
  printf '%s' "$valor"
}
ahora() { date +%s.%N; }
dif() { python3 -c "print(round($2 - $1, 1))"; }

IMAGEN_BASE=$(leer_env WAREHOUSE_IMAGEN); IMAGEN_BASE=${IMAGEN_BASE:-ghcr.io/mamezquita/warehouse-rush-api}
API_URL=$(leer_env WAREHOUSE_API_URL); API_URL=${API_URL:-https://warehouse-rush-api.onrender.com}
ESPERA_MAX=$(leer_env WAREHOUSE_ESPERA_MAX); ESPERA_MAX=${ESPERA_MAX:-900}
GHCR_USUARIO=$(leer_env GHCR_USUARIO); GHCR_USUARIO=${GHCR_USUARIO:-mamezquita}

# --- 1. Comprobaciones: solo se publica lo que está en commit y en origin ----------------------------
if [ -n "$(git status --porcelain)" ]; then
  echo "error: el árbol tiene cambios sin commit; la imagen debe corresponder exactamente a un commit" >&2
  git status --short >&2
  exit 1
fi
SHA=$(git rev-parse HEAD); SHA7=${SHA:0:7}
git fetch -q origin
if ! git branch -r --contains "$SHA" | grep -q "origin/"; then
  echo "error: el commit $SHA7 no está en origin; haz push primero (trazabilidad: /version debe apuntar a un commit público)" >&2
  exit 1
fi
if [ "$PRUEBAS" = 1 ]; then
  echo "== pruebas de la API (tests/test_api.py, tests/test_requirements_api.py)"
  PYTHON=${PYTHON:-$( [ -x .venv/bin/python ] && echo .venv/bin/python || echo python3 )}
  MLFLOW_DISABLE_AGENT_HINT=1 "$PYTHON" -m pytest tests/test_api.py tests/test_requirements_api.py -q -p no:cacheprovider | tail -1
fi
IMAGEN="$IMAGEN_BASE:$SHA7"
echo "== commit $SHA7 → $IMAGEN"

# --- 2. Build desde git archive (solo lo versionado) + VERSION.json --------------------------------
CONTEXTO=$(mktemp -d)
trap 'rm -rf "$CONTEXTO"' EXIT
git archive "$SHA" | tar -x -C "$CONTEXTO"
CREADA=$(date -u +%Y-%m-%dT%H:%M:%SZ)
python3 -c "import json,sys; json.dump({'git_commit': sys.argv[1], 'imagen': sys.argv[2], 'construida_en': sys.argv[3]}, open(sys.argv[4], 'w'))" \
  "$SHA" "$IMAGEN" "$CREADA" "$CONTEXTO/VERSION.json"
T0=$(ahora)
docker build -q -f "$CONTEXTO/api/Dockerfile" \
  --label "org.opencontainers.image.revision=$SHA" --label "org.opencontainers.image.created=$CREADA" \
  --label "org.opencontainers.image.title=warehouse-rush-api" -t "$IMAGEN" "$CONTEXTO" >/dev/null
T_BUILD=$(dif "$T0" "$(ahora)")
echo "build: ${T_BUILD} s"

# --- 3. Push a GHCR (paquete privado) ---------------------------------------------------------------
TOKEN=$(leer_env GHCR_TOKEN)
if [ -n "$TOKEN" ]; then
  printf '%s' "$TOKEN" | docker login ghcr.io -u "$GHCR_USUARIO" --password-stdin >/dev/null 2>&1 \
    || { echo "error: docker login en ghcr.io falló (revisa GHCR_TOKEN, scope write:packages)" >&2; exit 1; }
fi
unset TOKEN
T0=$(ahora)
docker push -q "$IMAGEN" >/dev/null
T_PUSH=$(dif "$T0" "$(ahora)")
DIGEST=$(docker inspect --format '{{index .RepoDigests 0}}' "$IMAGEN")
echo "push: ${T_PUSH} s ($DIGEST)"

# --- 4. Deploy hook → /version muestra el commit -----------------------------------------------------
DEPLOY_ID="" HOOK_HTTP="" T_VERSION="" T_PRECARGA="" VERSION_JSON="{}"
if [ "$SOLO_IMAGEN" = 0 ]; then
  HOOK=$(leer_env RENDER_DEPLOY_HOOK)
  if [ -z "$HOOK" ]; then
    echo "error: falta RENDER_DEPLOY_HOOK en .env (Render → servicio → Settings → Deploy Hook)" >&2
    exit 1
  fi
  T0=$(ahora)
  # La URL va por stdin (-K -): no aparece en la línea de comandos ni en la salida. Solo se muestra el id del deploy.
  HOOK_HTTP=$(printf 'url = "%s"\n' "$HOOK" | curl -sS -K - -G --data-urlencode "imgURL=$IMAGEN" \
              -o "$CONTEXTO/hook.json" -w '%{http_code}' 2>"$CONTEXTO/hook.err") || true
  unset HOOK
  if [ "$HOOK_HTTP" != 200 ] && [ "$HOOK_HTTP" != 202 ]; then
    if [ "${HOOK_HTTP:-000}" = 000 ]; then
      echo "error: no se pudo conectar con el deploy hook (revisa la red o la URL en .env; no se muestra por ser secreta)" >&2
    else
      echo "error: el deploy hook respondió HTTP $HOOK_HTTP (401/404: hook inválido o regenerado; 400: imagen distinta de la del servicio; 409: servicio suspendido)" >&2
    fi
    exit 1
  fi
  DEPLOY_ID=$(python3 -c "import json,sys
try: print(json.load(open(sys.argv[1])).get('deploy', {}).get('id', ''))
except Exception: print('')" "$CONTEXTO/hook.json")
  echo "deploy hook: HTTP $HOOK_HTTP ${DEPLOY_ID:+(deploy $DEPLOY_ID)}; esperando /version = $SHA7 (máx. ${ESPERA_MAX} s)"
  while :; do
    TRANSCURRIDO=$(dif "$T0" "$(ahora)")
    if python3 -c "import sys; sys.exit(0 if $TRANSCURRIDO > $ESPERA_MAX else 1)"; then
      echo "error: /version no mostró $SHA7 en ${ESPERA_MAX} s" >&2
      exit 1
    fi
    VERSION_JSON=$(curl -s -m 30 "$API_URL/version" || echo '{}')
    if [ "$(printf '%s' "$VERSION_JSON" | python3 -c "import json,sys
try: print(json.load(sys.stdin).get('git_commit', ''))
except Exception: print('')")" = "$SHA" ]; then
      T_VERSION=$TRANSCURRIDO
      break
    fi
    sleep 5
  done
  echo "/version = $SHA7 a los ${T_VERSION} s del deploy hook"
  while :; do  # precarga de producción (modelos listos para episodios y evaluaciones)
    if curl -s -m 30 "$API_URL/health" | grep -q '"precarga":"ok"'; then T_PRECARGA=$(dif "$T0" "$(ahora)"); break; fi
    if python3 -c "import sys; sys.exit(0 if $(dif "$T0" "$(ahora)") > $ESPERA_MAX else 1)"; then break; fi
    sleep 2
  done
  echo "precarga ok a los ${T_PRECARGA:-?} s del deploy hook"
fi

# --- 5. Evidencia (sin secretos) -------------------------------------------------------------------
mkdir -p docs/resultados/despliegues
REGISTRO="docs/resultados/despliegues/$(date -u +%Y%m%dT%H%M%SZ)-$SHA7.json"
REGISTRO="$REGISTRO" SHA="$SHA" IMAGEN="$IMAGEN" DIGEST="$DIGEST" MOTIVO="$MOTIVO" API_URL="$API_URL" \
SOLO_IMAGEN="$SOLO_IMAGEN" HOOK_HTTP="$HOOK_HTTP" DEPLOY_ID="$DEPLOY_ID" T_BUILD="$T_BUILD" T_PUSH="$T_PUSH" \
T_VERSION="$T_VERSION" T_PRECARGA="$T_PRECARGA" VERSION_JSON="$VERSION_JSON" CREADA="$CREADA" python3 - <<'EOF'
import json, os
e = os.environ
num = lambda k: float(e[k]) if e.get(k) else None
try:
    version = json.loads(e.get("VERSION_JSON") or "{}")
except json.JSONDecodeError:
    version = {}
json.dump({"git_commit": e["SHA"], "imagen": e["IMAGEN"], "digest": e["DIGEST"], "motivo": e.get("MOTIVO", ""),
           "api_url": e["API_URL"], "solo_imagen": e["SOLO_IMAGEN"] == "1",
           "deploy": {"http": e.get("HOOK_HTTP") or None, "id": e.get("DEPLOY_ID") or None},
           "tiempos_s": {"build": num("T_BUILD"), "push": num("T_PUSH"),
                         "deploy_hook_hasta_version": num("T_VERSION"), "deploy_hook_hasta_precarga": num("T_PRECARGA")},
           "version_servida": {k: version.get(k) for k in ("run_id", "model_sha256", "environment_version", "git_commit")},
           "creado_en": e["CREADA"]}, open(e["REGISTRO"], "w"), indent=2, ensure_ascii=False)
EOF
echo "evidencia: $REGISTRO (añádela a un commit)"
