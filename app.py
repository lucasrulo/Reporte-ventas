import streamlit as st
import requests
import pandas as pd
from datetime import datetime
import time as time_lib
import io
import json

# 1. Configuración de la página + estilo
st.set_page_config(page_title="Distrinando · Reportes", page_icon="📦", layout="centered")

ESTILO = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700;800&display=swap');

:root{
  --violeta:#6D28D9; --violeta-2:#8B5CF6; --indigo:#312E81; --turquesa:#14B8A6;
  --tinta:#1E1B2E; --gris:#6B6880; --linea:#E7E5F0; --fondo:#F6F5FB; --blanco:#FFFFFF;
}
html, body, [class*="css"], .stApp, button, input, textarea { font-family:'Plus Jakarta Sans', sans-serif !important; }
.stApp { background: radial-gradient(1200px 500px at 10% -10%, #EDE9FE 0%, transparent 60%),
                     radial-gradient(900px 400px at 110% 0%, #CCFBF1 0%, transparent 55%), var(--fondo); }
#MainMenu, footer, header { visibility:hidden; }
.block-container { padding-top:2rem; padding-bottom:4rem; max-width:860px; }

/* ---------- Hero ---------- */
.hero { position:relative; overflow:hidden; border-radius:28px; padding:2.2rem 2.2rem 1.8rem;
  background: linear-gradient(135deg, #1E1B4B 0%, #4C1D95 55%, #0F766E 120%); color:#fff;
  box-shadow: 0 20px 50px -20px rgba(76,29,149,.55); margin-bottom:1.6rem; }
.hero:before { content:""; position:absolute; width:340px; height:340px; right:-90px; top:-120px;
  background: radial-gradient(circle, rgba(139,92,246,.75), transparent 65%); filter:blur(10px); }
.hero:after { content:""; position:absolute; width:260px; height:260px; left:-80px; bottom:-140px;
  background: radial-gradient(circle, rgba(20,184,166,.55), transparent 65%); filter:blur(8px); }
.hero .kicker { display:inline-block; font-size:.75rem; font-weight:700; letter-spacing:.12em; text-transform:uppercase;
  background:rgba(255,255,255,.14); border:1px solid rgba(255,255,255,.25); padding:.3rem .75rem; border-radius:999px; }
.hero h1 { color:#fff !important; font-size:2.35rem; line-height:1.1; font-weight:800; margin:.9rem 0 .5rem; color:#fff; letter-spacing:-.02em; }
.hero h1 span { background:linear-gradient(90deg,#C4B5FD,#5EEAD4); -webkit-background-clip:text; background-clip:text; color:transparent; }
.hero p { color:rgba(255,255,255,.82); font-size:1rem; margin:0; max-width:560px; }
.hero .chips { display:flex; gap:.5rem; flex-wrap:wrap; margin-top:1.2rem; position:relative; z-index:1; }
.hero .chip { font-size:.8rem; font-weight:600; padding:.35rem .8rem; border-radius:999px;
  background:rgba(255,255,255,.12); border:1px solid rgba(255,255,255,.22); color:#fff; }
.hero .chip b { color:#5EEAD4; }

/* ---------- Pasos ---------- */
.paso { display:flex; align-items:center; gap:.7rem; margin:.2rem 0 .6rem; }
.paso .num { width:30px; height:30px; border-radius:10px; display:grid; place-items:center; font-weight:800; font-size:.9rem;
  color:#fff; background:linear-gradient(135deg,var(--violeta),var(--turquesa)); box-shadow:0 6px 14px -6px rgba(109,40,217,.7); }
.paso .tit { font-weight:700; color:var(--tinta); font-size:1.02rem; }
.paso .sub { color:var(--gris); font-size:.82rem; }

/* Tarjetas (st.container(border=True)) */
div[data-testid="stVerticalBlockBorderWrapper"] { background:var(--blanco); border:1px solid var(--linea) !important;
  border-radius:22px !important; box-shadow:0 10px 30px -18px rgba(30,27,46,.25); }

/* ---------- Radios como pastillas (compatible con versiones nuevas y viejas de Streamlit) ---------- */
div[data-testid="stRadio"] [role="radiogroup"] { gap:.5rem !important; flex-wrap:wrap; }
[data-testid="stRadioOption"], div[data-testid="stRadio"] [role="radiogroup"] > label {
  margin:0 !important; padding:.55rem 1.05rem !important; border-radius:14px; background:var(--fondo);
  border:1.5px solid var(--linea); cursor:pointer; transition:all .18s ease; }
[data-testid="stRadioOption"]:hover { border-color:var(--violeta-2); transform:translateY(-1px); }
[data-testid="stRadioOption"] > div > div:first-child:not([data-testid]),
div[data-testid="stRadio"] [role="radiogroup"] > label > div:first-child:not([data-testid]) { display:none !important; }
[data-testid="stRadioOption"] p { font-weight:600; color:var(--tinta); font-size:.92rem; }
[data-testid="stRadioOption"][data-selected="true"], [data-testid="stRadioOption"]:has(input:checked),
div[data-testid="stRadio"] [role="radiogroup"] > label:has(input:checked) {
  background:linear-gradient(135deg,var(--violeta),#4F46E5) !important; border-color:transparent;
  box-shadow:0 10px 20px -10px rgba(79,70,229,.8); }
[data-testid="stRadioOption"][data-selected="true"] p, [data-testid="stRadioOption"]:has(input:checked) p { color:#fff !important; }

/* ---------- Inputs ---------- */
div[data-baseweb="input"], div[data-baseweb="select"] > div, div[data-baseweb="textarea"] {
  border-radius:14px !important; border-color:var(--linea) !important; background:var(--fondo) !important; }
span[data-baseweb="tag"] { background:#EDE9FE !important; border-radius:999px !important; }
span[data-baseweb="tag"] span { color:#5B21B6 !important; font-weight:600; }
span[data-baseweb="tag"] svg { fill:#7C3AED !important; }
label[data-testid="stWidgetLabel"] p { font-weight:600; color:var(--tinta); }

/* ---------- Botones ---------- */
.stButton > button, .stLinkButton > a { border-radius:12px !important; font-weight:600 !important;
  border:1.5px solid var(--linea) !important; background:var(--blanco) !important; color:var(--tinta) !important;
  transition:all .18s ease; }
.stButton > button:hover, .stLinkButton > a:hover { border-color:var(--violeta-2) !important; color:var(--violeta) !important; }
.stButton > button[kind="primary"], button[data-testid="stBaseButton-primary"] { width:100%; padding:.95rem 1rem !important; font-size:1.05rem !important; font-weight:700 !important;
  color:#fff !important; border:none !important; border-radius:16px !important;
  background:linear-gradient(110deg,#6D28D9 0%,#4F46E5 45%,#0D9488 100%) !important; background-size:200% 100% !important;
  box-shadow:0 18px 30px -16px rgba(79,70,229,.9); }
.stButton > button[kind="primary"]:hover, button[data-testid="stBaseButton-primary"]:hover { background-position:100% 0 !important; transform:translateY(-1px); color:#fff !important; }
div[data-testid="stDownloadButton"] button { width:100%; padding:.95rem 1rem; border-radius:16px; border:none;
  font-weight:700; font-size:1.05rem; color:#0B3B36; background:linear-gradient(110deg,#5EEAD4,#A7F3D0);
  box-shadow:0 16px 28px -16px rgba(13,148,136,.9); }
div[data-testid="stDownloadButton"] button:hover { color:#0B3B36; filter:brightness(1.04); transform:translateY(-1px); }

button[data-testid="stBaseButton-primary"] p, div[data-testid="stDownloadButton"] button p { font-weight:700 !important; font-size:1.05rem !important; }
.hero h1, .hero h1 * { color:#fff; }
.hero h1 span { color:transparent !important; }

/* Botones de atajos de fecha (más chicos) */
[class*="st-key-atajo_"] button { padding:.3rem .2rem !important; font-size:.8rem !important; border-radius:999px !important; }

/* ---------- Expanders, alerts, progreso ---------- */
div[data-testid="stExpander"] details { border-radius:18px !important; border:1px solid var(--linea) !important; background:var(--blanco); }
div[data-testid="stExpander"] summary p { font-weight:600; }
div[data-testid="stAlert"] { border-radius:16px; }
div[data-testid="stProgress"] div[role="progressbar"] > div > div { background:linear-gradient(90deg,#8B5CF6,#14B8A6) !important; }

/* ---------- KPIs y resultados ---------- */
.kpis { display:grid; grid-template-columns:repeat(4,minmax(0,1fr)); gap:.8rem; margin:1rem 0 1.1rem; }
@media (max-width:640px){ .kpis{ grid-template-columns:repeat(2,minmax(0,1fr)); } .hero h1{font-size:1.8rem;} }
.kpi { background:var(--blanco); border:1px solid var(--linea); border-radius:20px; padding:1rem 1.1rem;
  box-shadow:0 10px 24px -18px rgba(30,27,46,.35); }
.kpi .lbl { font-size:.75rem; font-weight:700; letter-spacing:.06em; text-transform:uppercase; color:var(--gris); }
.kpi .val { font-size:1.45rem; font-weight:800; color:var(--tinta); margin-top:.2rem; letter-spacing:-.02em; }
.kpi.destacado { background:linear-gradient(135deg,#1E1B4B,#4C1D95); border:none; }
.kpi.destacado .lbl { color:rgba(255,255,255,.7); } .kpi.destacado .val { color:#fff; }
.listo { display:flex; align-items:center; gap:.7rem; padding:.9rem 1.1rem; border-radius:18px;
  background:linear-gradient(90deg,#ECFDF5,#F0FDFA); border:1px solid #A7F3D0; color:#065F46; font-weight:600; margin-top:1rem; }
.marcas-res { display:flex; flex-wrap:wrap; gap:.45rem; margin:.6rem 0 0; }
.marca-res { font-size:.8rem; padding:.35rem .75rem; border-radius:999px; background:var(--blanco); border:1px solid var(--linea); color:var(--tinta); }
.marca-res.ok:before { content:"●"; color:#10B981; margin-right:.4rem; }
.marca-res.err:before { content:"●"; color:#EF4444; margin-right:.4rem; }
.cuenta { display:flex; align-items:center; gap:.6rem; font-weight:600; color:var(--tinta); }
.cuenta .dot { width:10px; height:10px; border-radius:50%; }
</style>
"""
st.markdown(ESTILO, unsafe_allow_html=True)

try:
    STORES = st.secrets["stores"]
except Exception:
    STORES = {}

API_VERSION = "2024-01"


def graphql_url(store_info):
    return f"https://{store_info['url']}/admin/api/{API_VERSION}/graphql.json"


def graphql_headers(store_info):
    return {
        "X-Shopify-Access-Token": store_info["token"],
        "Content-Type": "application/json",
    }


def run_bulk_query(store_info, inner_query):
    """
    Lanza un Bulk Operation: Shopify arma en background un archivo JSONL
    con TODOS los pedidos + líneas + tags de producto + transacciones en
    una sola exportación, sin que tengamos que pedir uno por uno.
    """
    escaped_query = json.dumps(inner_query)  # escapa comillas/saltos de línea para incrustarla en la mutation
    mutation = f"""
    mutation {{
      bulkOperationRunQuery(query: {escaped_query}) {{
        bulkOperation {{ id status }}
        userErrors {{ field message }}
      }}
    }}
    """
    resp = requests.post(graphql_url(store_info), headers=graphql_headers(store_info), json={"query": mutation})
    resp.raise_for_status()
    data = resp.json()

    if "errors" in data:
        raise RuntimeError(f"Error GraphQL: {data['errors']}")

    result = data["data"]["bulkOperationRunQuery"]
    if result["userErrors"]:
        raise RuntimeError(f"Error iniciando bulk operation: {result['userErrors']}")

    return result["bulkOperation"]["id"]


def wait_for_bulk_operation(store_info, status_placeholder, marca):
    """Consulta el estado del bulk operation cada 2 seg hasta que termine."""
    check_query = """
    {
      currentBulkOperation {
        id
        status
        errorCode
        objectCount
        url
      }
    }
    """
    while True:
        resp = requests.post(graphql_url(store_info), headers=graphql_headers(store_info), json={"query": check_query})
        resp.raise_for_status()
        op = resp.json()["data"]["currentBulkOperation"]

        if op is None:
            time_lib.sleep(2)
            continue

        status_placeholder.text(
            f"{marca}: exportando pedidos... estado: {op['status']} ({op.get('objectCount', 0)} objetos)"
        )

        if op["status"] == "COMPLETED":
            return op.get("url")
        if op["status"] in ("FAILED", "CANCELED"):
            raise RuntimeError(f"Bulk operation terminó en estado {op['status']} ({op.get('errorCode')})")

        time_lib.sleep(2)


def download_jsonl(download_url):
    """Descarga el archivo JSONL resultante y lo parsea línea por línea."""
    if not download_url:
        return []
    resp = requests.get(download_url)
    resp.raise_for_status()
    rows = []
    for line in resp.text.splitlines():
        line = line.strip()
        if line:
            rows.append(json.loads(line))
    return rows


def build_orders_from_bulk(rows):
    """
    El JSONL de Shopify viene 'aplanado': cada pedido es una fila, y cada
    línea de producto es OTRA fila con '__parentId' apuntando al pedido.
    Acá los reagrupamos.
    """
    orders = {}
    line_items_by_order = {}

    for row in rows:
        parent_id = row.get("__parentId")
        node_id = row.get("id", "")

        if parent_id is None:
            orders[node_id] = row
        else:
            # lineItems es la única conexión anidada en esta consulta,
            # así que cualquier fila con __parentId es una línea de producto.
            line_items_by_order.setdefault(parent_id, []).append(row)

    for order_id, order in orders.items():
        order["_line_items"] = line_items_by_order.get(order_id, [])

    return list(orders.values())


def process_orders_bulk(orders, marca):
    """Arma las filas finales del reporte a partir de los pedidos ya reagrupados."""
    rows = []
    for order in orders:
        created_at = datetime.fromisoformat(order["createdAt"].replace("Z", "+00:00"))
        shipping_address = order.get("shippingAddress") or {}
        provincia = shipping_address.get("province", "") or ""

        customer = order.get("customer") or {}
        nombre_apellido = f"{(customer.get('firstName') or '')} {(customer.get('lastName') or '')}".strip()
        email = order.get("email", "") or ""

        gateways = order.get("paymentGatewayNames") or []
        gateways_raw = ", ".join(gateways).lower()
        if "mercado" in gateways_raw:
            metodo_pago = "Mercado Pago"
        elif "mobbex" in gateways_raw:
            metodo_pago = "Mobbex"
        elif "reversso" in gateways_raw:
            metodo_pago = "Reversso"
        else:
            metodo_pago = ", ".join(gateways).title()

        estado_cancelacion = "Cancelado" if order.get("cancelledAt") else "Activo"

        fulfillment_status = (order.get("displayFulfillmentStatus") or "").upper()
        mapa_prep = {
            "FULFILLED": "Preparado",
            "PARTIALLY_FULFILLED": "Preparación Parcial",
            "UNFULFILLED": "No requiere preparación",
        }
        estado_preparacion = mapa_prep.get(fulfillment_status, fulfillment_status.replace("_", " ").title())

        # --- ID de pago: viene directo en 'transactions', sin llamadas extra ---
        id_pago = ""
        transacciones = order.get("transactions") or []
        candidatas = [
            t for t in transacciones
            if (t.get("status") or "").upper() == "SUCCESS" and (t.get("kind") or "").upper() in ("SALE", "CAPTURE")
        ]
        if not candidatas:
            candidatas = transacciones
        for t in candidatas:
            id_pago = t.get("paymentId") or t.get("authorizationCode") or ""
            if id_pago:
                break

        shipping_line = order.get("shippingLine") or {}
        total_price = (order.get("totalPriceSet") or {}).get("shopMoney", {}).get("amount", 0) or 0

        for line in order.get("_line_items", []):
            producto = line.get("product") or {}
            tags_producto = ", ".join(producto.get("tags") or [])

            precio_raw = (line.get("originalUnitPriceSet") or {}).get("shopMoney", {}).get("amount", 0) or 0
            try:
                precio = float(precio_raw)
            except (TypeError, ValueError):
                precio = 0.0

            row = {
                "NOMBRE Y APELLIDO": nombre_apellido,
                "EMAIL": email,
                "MARCA": marca,
                "PEDIDO": order.get("name", ""),
                "FECHA": created_at.strftime("%d/%m/%Y"),
                "HORA": created_at.strftime("%H:%M:%S"),
                "PROVINCIA": provincia,
                "SKU": line.get("sku") or "",
                "TAGS PRODUCTO": tags_producto,
                "MODELO / COLOR": line.get("variantTitle") or "",
                "DESCRIPCION": line.get("title") or "",
                "CANTIDAD": line.get("quantity", 0),
                "PRECIO UNITARIO": precio,
                "TOTAL PEDIDO": float(total_price),
                "ESTADO DEL PAGO": order.get("displayFinancialStatus", ""),
                "ESTADO": fulfillment_status or "UNFULFILLED",
                "ENVIO": shipping_line.get("title", ""),
                "METODO DE PAGO": metodo_pago,
                "ESTADO CANCELACION": estado_cancelacion,
                "ESTADO PREPARACION": estado_preparacion,
                "ID DE PAGO": id_pago,
            }
            rows.append(row)
    return rows


def test_query_permissions(store_info, start_str, end_str):
    """
    Corre la misma consulta pero como GraphQL normal (no bulk), pidiendo un
    solo pedido. Si falta algún scope, Shopify devuelve acá el detalle exacto
    (campo + scope requerido) en vez del genérico ACCESS_DENIED del bulk.
    """
    test_query = f"""
    {{
      orders(first: 1, query: "created_at:>='{start_str}' AND created_at:<='{end_str}' AND status:any") {{
        edges {{
          node {{
            id
            name
            createdAt
            cancelledAt
            email
            displayFinancialStatus
            displayFulfillmentStatus
            paymentGatewayNames
            customer {{ firstName lastName }}
            shippingAddress {{ province }}
            shippingLine {{ title }}
            totalPriceSet {{ shopMoney {{ amount }} }}
            transactions {{
              kind
              status
              paymentId
              authorizationCode
            }}
            lineItems(first: 5) {{
              edges {{
                node {{
                  sku
                  title
                  variantTitle
                  quantity
                  originalUnitPriceSet {{ shopMoney {{ amount }} }}
                  product {{ tags }}
                }}
              }}
            }}
          }}
        }}
      }}
    }}
    """
    resp = requests.post(graphql_url(store_info), headers=graphql_headers(store_info), json={"query": test_query})
    if resp.status_code != 200:
        raise RuntimeError(f"HTTP {resp.status_code} — {resp.text[:300]}")
    data = resp.json()
    if "errors" in data:
        mensajes = "; ".join(e.get("message", "") for e in data["errors"])
        raise RuntimeError(mensajes)


def build_inner_query(start_str, end_str):
    return f"""
    {{
      orders(query: "created_at:>='{start_str}' AND created_at:<='{end_str}' AND status:any") {{
        edges {{
          node {{
            id
            name
            createdAt
            cancelledAt
            email
            displayFinancialStatus
            displayFulfillmentStatus
            paymentGatewayNames
            customer {{ firstName lastName }}
            shippingAddress {{ province }}
            shippingLine {{ title }}
            totalPriceSet {{ shopMoney {{ amount }} }}
            transactions {{
              kind
              status
              paymentId
              authorizationCode
            }}
            lineItems {{
              edges {{
                node {{
                  sku
                  title
                  variantTitle
                  quantity
                  originalUnitPriceSet {{ shopMoney {{ amount }} }}
                  product {{ tags }}
                }}
              }}
            }}
          }}
        }}
      }}
    }}
    """


# ==============================================================================
# 🟡 MERCADOLIBRE (100% autónomo: no depende de ningún otro repo)
# ==============================================================================
# - Usa una app de MeLi PROPIA para este reporte (distinta de la del dashboard),
#   así sus tokens no se cruzan con los del pipeline.
# - El refresh_token de MeLi es de UN SOLO USO: cada renovación devuelve uno nuevo.
#   Por eso se guarda CIFRADO (Fernet) en la rama 'meli-tokens' de ESTE repo.
#   Streamlit solo despliega 'main', así que escribir en esa rama no reinicia la app.
import base64
import threading
from datetime import timedelta, timezone
from concurrent.futures import ThreadPoolExecutor
from urllib.parse import urlencode

from cryptography.fernet import Fernet, InvalidToken

MELI_API = "https://api.mercadolibre.com"
MELI_AUTH = "https://auth.mercadolibre.com.ar/authorization"
ZONA_AR = timezone(timedelta(hours=-3))

try:
    MELI_CFG = dict(st.secrets.get("meli", {}))
except Exception:
    MELI_CFG = {}

MELI_APP_ID = str(MELI_CFG.get("app_id", ""))
MELI_CLIENT_SECRET = MELI_CFG.get("client_secret", "")
MELI_REDIRECT = MELI_CFG.get("redirect_uri", "https://reporte-ventas-distrinando.streamlit.app")
MELI_FERNET_KEY = MELI_CFG.get("fernet_key", "")
GH_TOKEN = MELI_CFG.get("github_token", "")
GH_REPO = MELI_CFG.get("repo", "lucasrulo/reporte-ventas")
GH_BRANCH = MELI_CFG.get("branch", "meli-tokens")
GH_FILE = "meli_tokens.enc"
MELI_CUENTAS = list(MELI_CFG.get("cuentas", ["Reebok", "Crocs", "Kappa", "Columbia"]))

MELI_FALTANTES = [k for k in ("app_id", "client_secret", "fernet_key", "github_token") if not MELI_CFG.get(k)]


# ---------- Almacén de tokens (memoria + archivo cifrado en GitHub) ----------
@st.cache_resource
def _estado_tokens():
    # Compartido por todas las sesiones del mismo servidor
    return {"lock": threading.Lock(), "tokens": None, "sha": None}


def _gh_headers():
    return {"Authorization": f"Bearer {GH_TOKEN}", "Accept": "application/vnd.github+json"}


def _gh_url():
    return f"https://api.github.com/repos/{GH_REPO}/contents/{GH_FILE}"


def _asegurar_rama():
    r = requests.get(f"https://api.github.com/repos/{GH_REPO}/git/ref/heads/{GH_BRANCH}", headers=_gh_headers(), timeout=20)
    if r.status_code == 200:
        return
    repo = requests.get(f"https://api.github.com/repos/{GH_REPO}", headers=_gh_headers(), timeout=20)
    repo.raise_for_status()
    base = repo.json()["default_branch"]
    ref = requests.get(f"https://api.github.com/repos/{GH_REPO}/git/ref/heads/{base}", headers=_gh_headers(), timeout=20)
    ref.raise_for_status()
    c = requests.post(f"https://api.github.com/repos/{GH_REPO}/git/refs", headers=_gh_headers(), timeout=20,
                      json={"ref": f"refs/heads/{GH_BRANCH}", "sha": ref.json()["object"]["sha"]})
    if c.status_code not in (201, 422):  # 422 = ya existe
        raise RuntimeError(f"No pude crear la rama {GH_BRANCH}: HTTP {c.status_code} {c.text[:200]}")


def _cargar_tokens(estado):
    """Lee el archivo cifrado desde GitHub (solo la primera vez por servidor)."""
    if estado["tokens"] is not None:
        return estado["tokens"]
    r = requests.get(_gh_url(), headers=_gh_headers(), params={"ref": GH_BRANCH}, timeout=20)
    if r.status_code == 404:
        estado["tokens"], estado["sha"] = {}, None
        return estado["tokens"]
    if r.status_code != 200:
        raise RuntimeError(f"GitHub HTTP {r.status_code} leyendo tokens: {r.text[:200]}")
    d = r.json()
    try:
        plano = Fernet(MELI_FERNET_KEY.encode()).decrypt(base64.b64decode(d["content"]))
    except InvalidToken:
        raise RuntimeError("No pude descifrar los tokens: cambió la fernet_key. Volvé a conectar las cuentas.")
    estado["tokens"], estado["sha"] = json.loads(plano), d["sha"]
    return estado["tokens"]


def _guardar_tokens(estado):
    _asegurar_rama()
    cifrado = Fernet(MELI_FERNET_KEY.encode()).encrypt(json.dumps(estado["tokens"]).encode())
    body = {"message": "tokens meli", "branch": GH_BRANCH, "content": base64.b64encode(cifrado).decode()}
    if estado["sha"]:
        body["sha"] = estado["sha"]
    r = requests.put(_gh_url(), headers=_gh_headers(), json=body, timeout=20)
    if r.status_code == 409 or (r.status_code == 422 and "sha" in r.text):
        # sha desactualizado: tomamos el actual y reintentamos una vez
        actual = requests.get(_gh_url(), headers=_gh_headers(), params={"ref": GH_BRANCH}, timeout=20)
        if actual.status_code == 200:
            body["sha"] = actual.json()["sha"]
            r = requests.put(_gh_url(), headers=_gh_headers(), json=body, timeout=20)
    if r.status_code not in (200, 201):
        raise RuntimeError(f"No pude guardar los tokens en GitHub: HTTP {r.status_code} {r.text[:200]}")
    estado["sha"] = r.json()["content"]["sha"]


def _pedir_token(data):
    r = requests.post(f"{MELI_API}/oauth/token", timeout=30, data=data,
                      headers={"accept": "application/json", "content-type": "application/x-www-form-urlencoded"})
    if r.status_code != 200:
        raise RuntimeError(f"MeLi rechazó el pedido de token (HTTP {r.status_code}): {r.text[:200]}")
    d = r.json()
    if "refresh_token" not in d:
        raise RuntimeError("MeLi no devolvió refresh_token: en la app de MeLi activá 'offline_access' / Refresh Token.")
    return d


def conectar_cuenta(marca, code):
    """Canjea el code del login de MeLi y guarda los tokens de esa marca."""
    d = _pedir_token({"grant_type": "authorization_code", "client_id": MELI_APP_ID,
                      "client_secret": MELI_CLIENT_SECRET, "code": code, "redirect_uri": MELI_REDIRECT})
    nick = ""
    try:
        me = requests.get(f"{MELI_API}/users/me", headers={"Authorization": f"Bearer {d['access_token']}"}, timeout=20)
        nick = me.json().get("nickname", "")
    except Exception:
        pass
    estado = _estado_tokens()
    with estado["lock"]:
        tokens = _cargar_tokens(estado)
        tokens[marca] = {"access_token": d["access_token"], "refresh_token": d["refresh_token"],
                         "expires_at": int(time_lib.time()) + int(d.get("expires_in", 21600)),
                         "user_id": d["user_id"], "nickname": nick}
        _guardar_tokens(estado)
    return nick


def token_vigente(marca, forzar=False):
    """Devuelve un access_token válido; renueva solo si le quedan < 30 min."""
    estado = _estado_tokens()
    with estado["lock"]:
        tokens = _cargar_tokens(estado)
        tok = tokens.get(marca)
        if not tok:
            raise RuntimeError("Cuenta no conectada. Conectala en '⚙️ Cuentas de MercadoLibre'.")
        if not forzar and tok["expires_at"] - time_lib.time() > 1800:
            return tok
        d = _pedir_token({"grant_type": "refresh_token", "client_id": MELI_APP_ID,
                          "client_secret": MELI_CLIENT_SECRET, "refresh_token": tok["refresh_token"]})
        tokens[marca] = {**tok, "access_token": d["access_token"],
                         "refresh_token": d.get("refresh_token", tok["refresh_token"]),
                         "expires_at": int(time_lib.time()) + int(d.get("expires_in", 21600))}
        # El refresh viejo ya no sirve: se guarda el nuevo inmediatamente
        _guardar_tokens(estado)
        return tokens[marca]


# ---------- Reporte ----------
ESTADO_ORDEN_MELI = {
    "paid": "Pagada",
    "confirmed": "Confirmada",
    "payment_required": "Pago pendiente",
    "payment_in_process": "Pago en proceso",
    "partially_paid": "Pago parcial",
    "partially_refunded": "Reembolso parcial",
    "pending_cancel": "Cancelación pendiente",
    "cancelled": "Cancelada",
    "invalid": "Inválida",
}

FALLA_ENTREGA = {"receiver_absent", "not_visited", "delivery_failed", "bad_address", "not_localized",
                 "unvisited_address", "dangerous_area", "contact_with_carrier", "rescheduled_by_meli"}


def estado_envio_meli(status, sub):
    status, sub = (status or "").lower(), (sub or "").lower()
    if status in ("", "pending", "handling"):
        return "Pendiente"
    if status == "ready_to_ship":
        return "Despachado" if sub in ("dropped_off", "in_hub", "picked_up", "in_packing_list", "at_the_door") else "Listo para despachar"
    if status == "shipped":
        if sub == "out_for_delivery":
            return "En reparto"
        if sub in ("waiting_for_withdrawal", "ready_to_pickup"):
            return "Listo para retirar"
        if sub in FALLA_ENTREGA:
            return "Intento fallido"
        return "En camino"
    if status == "delivered":
        return "Entregado"
    if status == "not_delivered":
        return "Devolución" if "return" in sub else "No entregado"
    if status == "cancelled":
        return "Cancelado"
    return "Pendiente"


def num(v):
    try:
        return float(v or 0)
    except (TypeError, ValueError):
        return 0.0


class MeliReporte:
    def __init__(self, marca, tok):
        self.marca = marca
        self.tok = tok
        self.s = requests.Session()
        self.s.headers["Authorization"] = f"Bearer {tok['access_token']}"
        self._renovado = False
        self._lock = threading.Lock()

    def get(self, path, params=None):
        r = None
        for intento in range(5):
            try:
                r = self.s.get(f"{MELI_API}{path}", params=params, timeout=30)
            except requests.RequestException:
                time_lib.sleep(2 * (intento + 1))
                continue
            if r.status_code == 401:
                with self._lock:
                    if not self._renovado:
                        self.tok = token_vigente(self.marca, forzar=True)
                        self.s.headers["Authorization"] = f"Bearer {self.tok['access_token']}"
                        self._renovado = True
                        continue
                return r
            if r.status_code == 429 or r.status_code >= 500:
                time_lib.sleep(2 * (intento + 1))
                continue
            return r
        return r

    def buscar_ordenes(self, desde, hasta, status_placeholder, campo="order.date_created"):
        """Órdenes por fecha (creación o última actualización), en ventanas de 3 días
        (el search no pagina más allá de ~10k)."""
        ordenes, ini = [], desde
        while ini < hasta:
            fin = min(ini + timedelta(days=3), hasta)
            offset = 0
            while True:
                params = {
                    "seller": self.tok["user_id"],
                    f"{campo}.from": ini.strftime("%Y-%m-%dT%H:%M:%S.000-03:00"),
                    f"{campo}.to": fin.strftime("%Y-%m-%dT%H:%M:%S.000-03:00"),
                    "sort": "date_asc", "limit": 50, "offset": offset,
                }
                r = self.get("/orders/search", params)
                if r is None or r.status_code != 200:
                    raise RuntimeError(f"/orders/search HTTP {getattr(r, 'status_code', '?')} {getattr(r, 'text', '')[:200]}")
                d = r.json()
                res = d.get("results", [])
                ordenes.extend(res)
                offset += len(res)
                status_placeholder.text(f"{self.marca}: {len(ordenes)} órdenes descargadas...")
                if not res or offset >= d.get("paging", {}).get("total", 0) or offset >= 9950:
                    break
            ini = fin
        return list({o["id"]: o for o in ordenes}.values())

    def envio(self, shipping_id):
        """Estado del envío + costo que paga el vendedor."""
        if not shipping_id:
            return {}
        out = {}
        r = self.get(f"/shipments/{shipping_id}")
        if r is not None and r.status_code == 200:
            s = r.json()
            out["estado_envio"] = estado_envio_meli(s.get("status"), s.get("substatus"))
            out["tracking"] = str(s.get("tracking_number") or "")
            recv = s.get("receiver_address") or ((s.get("destination") or {}).get("shipping_address")) or {}

            def _nombre(x):
                return x.get("name") if isinstance(x, dict) else (x or "")
            calle = recv.get("address_line") or " ".join(
                str(v) for v in (recv.get("street_name"), recv.get("street_number")) if v)
            out["dest"] = {
                "nombre": recv.get("receiver_name") or (s.get("destination") or {}).get("receiver_name") or "",
                "direccion": calle or "",
                "localidad": _nombre(recv.get("city")),
                "provincia": _nombre(recv.get("state")),
                "cp": recv.get("zip_code") or "",
            }
            opcion = s.get("shipping_option") or {}
            out["costo_opcion"] = num(opcion.get("cost"))
            out["_raw_opcion"] = {k: opcion.get(k) for k in ("cost", "list_cost", "currency_id", "name")}
            out["status_raw"] = (s.get("status") or "").lower()
            out["substatus_raw"] = (s.get("substatus") or "").lower()
            hist = s.get("status_history") or {}
            out["fecha_no_entrega"] = (hist.get("date_not_delivered") or hist.get("date_returned")
                                       or hist.get("date_cancelled") or s.get("last_updated"))
        c = self.get(f"/shipments/{shipping_id}/costs")
        if c is not None and c.status_code == 200:
            cj = c.json()
            out["_raw_costs"] = cj
            senders = cj.get("senders") or []
            out["costo_vendedor"] = sum(num(x.get("cost")) for x in senders)
            # Lo que pagó el comprador por el envío (en ME2 no siempre viene en el pago)
            receiver = cj.get("receiver") or {}
            if isinstance(receiver, list):
                out["costo_comprador"] = sum(num(x.get("cost")) for x in receiver)
            else:
                out["costo_comprador"] = num(receiver.get("cost"))
        return out

    def a_filas(self, o, env, envio_ya_contado):
        pagos = [p for p in (o.get("payments") or []) if p]
        aprobados = [p for p in pagos if p.get("status") in ("approved", "refunded", "charged_back", "partially_refunded")]
        id_pago = ", ".join(str(p.get("id")) for p in (aprobados or pagos) if p.get("id"))

        shipping_id = (o.get("shipping") or {}).get("id")
        envio_comprador = importe_envio_comprador(o, env, shipping_id, envio_ya_contado)

        reembolso = 0.0
        for p in pagos:
            ref = num(p.get("transaction_amount_refunded"))
            if not ref and p.get("status") in ("refunded", "charged_back"):
                ref = num(p.get("total_paid_amount")) or num(p.get("transaction_amount"))
            reembolso += ref

        fecha = pd.Timestamp(o["date_created"]).tz_convert(ZONA_AR)
        estado_pedido = env.get("estado_envio", "S/D") if shipping_id else "Sin envío (acordar)"

        filas = []
        for i, oi in enumerate(o.get("order_items") or [{}]):
            item = oi.get("item") or {}
            cant = int(num(oi.get("quantity")))
            primera = i == 0
            filas.append({
                "MARCA": self.marca,
                "PACK ID": str(o.get("pack_id") or o["id"]),
                "ORDEN MELI": str(o["id"]),
                "ORDER ID MP (ID PAGO)": id_pago,
                "FECHA": fecha.strftime("%d/%m/%Y"),
                "ESTADO": ESTADO_ORDEN_MELI.get(o.get("status"), o.get("status", "")),
                "ESTADO DEL PEDIDO": estado_pedido,
                "SKU": str(item.get("seller_sku") or item.get("seller_custom_field") or item.get("id") or ""),
                "DESCRIPCION": item.get("title", ""),
                "CANTIDAD": cant,
                "VALOR ARTICULO": num(oi.get("unit_price")) * cant,
                # Importes a nivel orden/envío: solo en la primera línea, para no duplicar al sumar
                "IMPORTE DEL ENVIO": envio_comprador if primera else 0.0,
                "COSTO ENVIO VENDEDOR": (env.get("costo_vendedor", 0.0)
                                         if primera and shipping_id and shipping_id not in envio_ya_contado else 0.0),
                "ANULACIONES Y REEMBOLSOS": reembolso if primera else 0.0,
                "NUMERO DE SEGUIMIENTO": env.get("tracking", "") if shipping_id else "",
                "_item_id": str(item.get("id") or ""),
                "_unit_price": num(oi.get("unit_price")),
            })
            if primera and shipping_id:
                envio_ya_contado.add(shipping_id)
        return filas


def importe_envio_comprador(o, env, shipping_id, envio_ya_contado):
    """Lo que pagó el comprador por el envío. Va UNA sola vez por envío (un pack = un envío).
    Fuentes, en orden: pagos de todas las órdenes del envío -> shipping_cost de la orden ->
    costo del receptor en /shipments/{id}/costs -> costo de la opción de envío elegida."""
    pagos = [p for p in (o.get("payments") or []) if p and p.get("status") in
             ("approved", "refunded", "charged_back", "partially_refunded")]
    pagos_orden = sum(num(p.get("shipping_cost")) for p in pagos)
    if not shipping_id:
        return pagos_orden
    if shipping_id in envio_ya_contado:
        return 0.0
    return (env.get("pagos_envio_total", pagos_orden) or num(o.get("shipping_cost"))
            or env.get("costo_comprador", 0.0) or env.get("costo_opcion", 0.0))


def parse_billing(d):
    """Datos de facturación del comprador (formato nuevo y viejo de la API de MeLi)."""
    if not isinstance(d, dict):
        return {}
    bi = (d.get("buyer") or {}).get("billing_info") or d.get("billing_info") or d
    extra = {x.get("type"): x.get("value") for x in (bi.get("additional_info") or []) if isinstance(x, dict)}
    ident = bi.get("identification") or {}
    addr = bi.get("address") or {}

    def _n(x):
        return x.get("name") if isinstance(x, dict) else (x or "")
    nombre = " ".join(str(v) for v in (bi.get("name") or extra.get("FIRST_NAME"),
                                        bi.get("last_name") or extra.get("LAST_NAME")) if v)
    razon = bi.get("business_name") or extra.get("BUSINESS_NAME") or ""
    calle = " ".join(str(v) for v in (addr.get("street_name") or extra.get("STREET_NAME"),
                                       addr.get("street_number") or extra.get("STREET_NUMBER")) if v)
    taxes = bi.get("taxes") or {}
    cond = ((taxes.get("taxpayer_type") or {}).get("description") if isinstance(taxes, dict) else "") \
        or extra.get("TAXPAYER_TYPE_ID") or ""
    return {
        "tipo_doc": ident.get("type") or bi.get("doc_type") or extra.get("DOC_TYPE") or "",
        "doc": str(ident.get("number") or bi.get("doc_number") or extra.get("DOC_NUMBER") or ""),
        "nombre": razon or nombre,
        "direccion": calle,
        "localidad": addr.get("city_name") or _n(addr.get("city")) or extra.get("CITY_NAME") or "",
        "provincia": _n(addr.get("state")) or addr.get("state_name") or extra.get("STATE_NAME") or "",
        "cp": addr.get("zip_code") or extra.get("ZIP_CODE") or "",
        "condicion_iva": cond,
    }


def billing_crudo(rep, o):
    """Pide los datos de facturación de una orden (endpoint nuevo y, si no, el viejo)."""
    bid = ((o.get("buyer") or {}).get("billing_info") or {}).get("id")
    if bid:
        for headers in ({"x-version": "2"}, {}):
            try:
                r = rep.s.get(f"{MELI_API}/orders/billing-info/MLA/{bid}", timeout=30, headers=headers)
                if r.status_code == 200:
                    return r.json()
            except requests.RequestException:
                pass
    r = rep.get(f"/orders/{o['id']}/billing_info")
    if r is not None and r.status_code == 200:
        return r.json()
    return {}


def datos_cliente(o, billing, env):
    """Combina facturación + domicilio de entrega (respaldo cuando falta algún dato)."""
    b = parse_billing(billing)
    dest = env.get("dest") or {}
    comprador = o.get("buyer") or {}
    nombre_buyer = " ".join(str(v) for v in (comprador.get("first_name"), comprador.get("last_name")) if v)
    return {
        "TIPO DOC": b.get("tipo_doc", ""),
        "DNI / CUIT": b.get("doc", ""),
        "NOMBRE Y APELLIDO": b.get("nombre") or nombre_buyer or dest.get("nombre", ""),
        "CONDICION IVA": b.get("condicion_iva", ""),
        "DIRECCION": b.get("direccion") or dest.get("direccion", ""),
        "LOCALIDAD": b.get("localidad") or dest.get("localidad", ""),
        "PROVINCIA": b.get("provincia") or dest.get("provincia", ""),
        "CODIGO POSTAL": b.get("cp") or dest.get("cp", ""),
    }


COLUMNAS_CLIENTE = ["TIPO DOC", "DNI / CUIT", "NOMBRE Y APELLIDO", "CONDICION IVA", "DIRECCION", "LOCALIDAD",
                    "PROVINCIA", "CODIGO POSTAL"]


def generar_meli(marca, start_date, end_date, status_placeholder):
    rep = MeliReporte(marca, token_vigente(marca))
    desde = datetime.combine(start_date, datetime.min.time()).replace(tzinfo=ZONA_AR)
    hasta = datetime.combine(end_date, datetime.max.time()).replace(tzinfo=ZONA_AR)

    ordenes = rep.buscar_ordenes(desde, hasta, status_placeholder)

    ship_ids = sorted({(o.get("shipping") or {}).get("id") for o in ordenes} - {None})
    envios = {}
    status_placeholder.text(f"{marca}: consultando {len(ship_ids)} envíos...")
    with ThreadPoolExecutor(max_workers=8) as ex:
        for sid, env in zip(ship_ids, ex.map(rep.envio, ship_ids)):
            envios[sid] = env

    # Envío pagado por el comprador sumando los pagos de TODAS las órdenes del mismo envío
    for o in ordenes:
        sid = (o.get("shipping") or {}).get("id")
        if sid in envios:
            pagos = [p for p in (o.get("payments") or []) if p and p.get("status") in
                     ("approved", "refunded", "charged_back", "partially_refunded")]
            envios[sid]["pagos_envio_total"] = (envios[sid].get("pagos_envio_total", 0.0)
                                                + sum(num(p.get("shipping_cost")) for p in pagos))

    # Datos del cliente (DNI, nombre, domicilio): una consulta por orden
    status_placeholder.text(f"{marca}: leyendo datos de facturación de {len(ordenes)} órdenes...")
    with ThreadPoolExecutor(max_workers=8) as ex:
        billings = dict(zip([o["id"] for o in ordenes], ex.map(lambda o: billing_crudo(rep, o), ordenes)))

    filas, contados = [], set()
    for o in sorted(ordenes, key=lambda x: x.get("date_created", "")):
        sid = (o.get("shipping") or {}).get("id")
        env = envios.get(sid, {})
        cliente = datos_cliente(o, billings.get(o["id"], {}), env)
        for f in rep.a_filas(o, env, contados):
            f.update(cliente)
            filas.append(f)
    return ordenes, filas


def diagnosticar_envio(marca, id_txt):
    """Muestra de dónde sale (o por qué no sale) el importe del envío de un pack u orden."""
    rep = MeliDevoluciones(marca, token_vigente(marca))
    ordenes = rep.ordenes_de(None, id_txt)
    if not ordenes:
        return None
    detalle, envios = [], {}
    for o in ordenes:
        sid = (o.get("shipping") or {}).get("id")
        if sid and sid not in envios:
            envios[sid] = rep.envio(sid)
        detalle.append({
            "orden": o.get("id"), "pack": o.get("pack_id"), "envio_id": sid,
            "total_orden": o.get("total_amount"), "shipping_cost_orden": o.get("shipping_cost"),
            "pagos": [{k: p.get(k) for k in ("id", "status", "transaction_amount", "shipping_cost",
                                              "total_paid_amount", "coupon_amount")}
                      for p in (o.get("payments") or []) if p],
        })
    for sid, env in envios.items():
        env["pagos_envio_total"] = sum(
            num(p.get("shipping_cost")) for o in ordenes if (o.get("shipping") or {}).get("id") == sid
            for p in (o.get("payments") or []) if p and p.get("status") in
            ("approved", "refunded", "charged_back", "partially_refunded"))
    contados, filas = set(), []
    for o in ordenes:
        sid = (o.get("shipping") or {}).get("id")
        filas.extend(rep.a_filas(o, envios.get(sid, {}), contados))
    resumen = {
        "IMPORTE DEL ENVIO que sale en el reporte": sum(f["IMPORTE DEL ENVIO"] for f in filas),
        "COSTO ENVIO VENDEDOR": sum(f["COSTO ENVIO VENDEDOR"] for f in filas),
        "VALOR ARTICULOS": sum(f["VALOR ARTICULO"] for f in filas),
    }
    crudo = {"facturacion": {str(o["id"]): {"leido": datos_cliente(o, billing_crudo(rep, o),
                                                                    envios.get((o.get("shipping") or {}).get("id"), {})),
                                             "crudo": billing_crudo(rep, o)} for o in ordenes},
             "ordenes": detalle,
             "envios": {str(k): {"costo_comprador(costs.receiver)": v.get("costo_comprador"),
                                 "costo_opcion(shipping_option)": v.get("costo_opcion"),
                                 "pagos_envio_total": v.get("pagos_envio_total"),
                                 "shipping_option": v.get("_raw_opcion"), "costs": v.get("_raw_costs")}
                        for k, v in envios.items()}}
    return resumen, crudo


# ---------- Reporte contable (liquidaciones de Mercado Pago) ----------
MP_API = "https://api.mercadopago.com"
COLUMNAS_CONTABLE = [
    "MARCA", "NUMERO DE PEDIDO", "PACK ID", "ID PAGO MP", "FECHA", "FECHA LIBERACION", "MOVIMIENTO",
    "DESCRIPCION", "MONTO BRUTO DE LA OPERACION", "COMISION MERCADO LIBRE (INCLUYE IVA)",
    "COMISION POR OFRECER CUOTAS SIN INTERES", "COSTO DE ENVIO", "IMPUESTOS", "MONTO NETO",
]


def _mp_token_extra(marca):
    """Opcional: token propio de Mercado Pago por marca en secrets [meli.mp_tokens]."""
    try:
        return dict(MELI_CFG.get("mp_tokens", {})).get(marca, "")
    except Exception:
        return ""


def clasificar_cargo(nombre, tipo=""):
    n = f"{nombre} {tipo}".lower()
    if tipo == "tax" or any(k in n for k in ("tax", "iibb", "sirtac", "impuesto", "retenc", "percep", "ganancia",
                                             "debitos_creditos", "withholding")):
        return "IMPUESTOS"
    if any(k in n for k in ("financ", "cuota", "installment", "interest")):
        return "COMISION POR OFRECER CUOTAS SIN INTERES"
    if any(k in n for k in ("ship", "envio", "envío")):
        return "COSTO DE ENVIO"
    return "COMISION MERCADO LIBRE (INCLUYE IVA)"


def desglose_pago(p):
    """Del pago de Mercado Pago saca: bruto, comisiones, envío, impuestos y neto (cobro y devolución)."""
    cargos = {k: 0.0 for k in ("COMISION MERCADO LIBRE (INCLUYE IVA)", "COMISION POR OFRECER CUOTAS SIN INTERES",
                               "COSTO DE ENVIO", "IMPUESTOS")}
    devueltos = dict(cargos)
    hay_impuestos = False
    detalles = p.get("charges_details") or []
    if detalles:
        for c in detalles:
            cuentas = c.get("accounts") or {}
            if cuentas.get("from") and cuentas.get("from") != "collector":
                continue  # lo paga el comprador, no el vendedor
            cat = clasificar_cargo(c.get("name") or "", c.get("type") or "")
            montos = c.get("amounts") or {}
            cargos[cat] += num(montos.get("original"))
            devueltos[cat] += num(montos.get("refunded"))
            hay_impuestos = hay_impuestos or cat == "IMPUESTOS"
    else:
        for f in p.get("fee_details") or []:
            if f.get("fee_payer") and f.get("fee_payer") != "collector":
                continue
            cat = clasificar_cargo(f.get("type") or "")
            cargos[cat] += num(f.get("amount"))
            hay_impuestos = hay_impuestos or cat == "IMPUESTOS"
    if not hay_impuestos:
        cargos["IMPUESTOS"] += num(p.get("taxes_amount"))
    bruto = num(p.get("transaction_amount"))
    neto = num((p.get("transaction_details") or {}).get("net_received_amount"))
    if not neto:
        neto = bruto - sum(cargos.values())
    return bruto, cargos, devueltos, neto


class MeliContable(MeliReporte):
    def pago_mp(self, payment_id):
        token = _mp_token_extra(self.marca) or self.tok["access_token"]
        for intento in range(4):
            try:
                r = requests.get(f"{MP_API}/v1/payments/{payment_id}", timeout=30,
                                 headers={"Authorization": f"Bearer {token}"})
            except requests.RequestException:
                time_lib.sleep(2 * (intento + 1))
                continue
            if r.status_code == 429 or r.status_code >= 500:
                time_lib.sleep(2 * (intento + 1))
                continue
            if r.status_code != 200:
                return {"_error": f"HTTP {r.status_code} {r.text[:150]}"}
            return r.json()
        return {"_error": "sin respuesta"}

    def filas_orden(self, o, pagos_mp, env, envios_contados):
        titulos = " | ".join((oi.get("item") or {}).get("title", "") for oi in (o.get("order_items") or []))
        base = {"MARCA": self.marca, "NUMERO DE PEDIDO": str(o["id"]), "PACK ID": str(o.get("pack_id") or o["id"]),
                "DESCRIPCION": titulos}
        filas, envio_en_pago = [], False
        for p in pagos_mp:
            if p.get("_error") or p.get("status") not in ("approved", "refunded", "charged_back",
                                                          "partially_refunded", "in_mediation"):
                continue
            bruto, cargos, devueltos, neto = desglose_pago(p)
            envio_en_pago = envio_en_pago or cargos["COSTO DE ENVIO"] > 0
            fecha = _fecha_corta(p.get("date_approved") or p.get("date_created"))
            liberacion = _fecha_corta(p.get("money_release_date"))
            fila = {**base, "ID PAGO MP": str(p.get("id")), "FECHA": fecha, "FECHA LIBERACION": liberacion,
                    "MOVIMIENTO": "Pago", "MONTO BRUTO DE LA OPERACION": bruto, "MONTO NETO": neto}
            for k, v in cargos.items():
                fila[k] = -v if v else 0.0
            filas.append(fila)
            reemb = num(p.get("transaction_amount_refunded"))
            if reemb:
                dev = {**base, "ID PAGO MP": str(p.get("id")), "FECHA": _fecha_corta(
                       ((p.get("refunds") or [{}])[-1] or {}).get("date_created") or p.get("date_last_updated")),
                       "FECHA LIBERACION": "", "MOVIMIENTO": "Devolución de dinero",
                       "MONTO BRUTO DE LA OPERACION": -reemb}
                for k, v in devueltos.items():
                    dev[k] = v
                dev["MONTO NETO"] = -reemb + sum(devueltos.values())
                filas.append(dev)
        # Tarifa de envío que MeLi cobra aparte (una vez por envío), si no vino dentro del pago
        sid = (o.get("shipping") or {}).get("id")
        costo = env.get("costo_vendedor", 0.0)
        if sid and costo and not envio_en_pago and sid not in envios_contados:
            envios_contados.add(sid)
            filas.append({**base, "ID PAGO MP": "", "FECHA": filas[0]["FECHA"] if filas else "",
                          "FECHA LIBERACION": "", "MOVIMIENTO": "Tarifa de envío",
                          "MONTO BRUTO DE LA OPERACION": 0.0, "COMISION MERCADO LIBRE (INCLUYE IVA)": 0.0,
                          "COMISION POR OFRECER CUOTAS SIN INTERES": 0.0, "COSTO DE ENVIO": -costo,
                          "IMPUESTOS": 0.0, "MONTO NETO": -costo})
        return filas


def generar_contable(marca, start_date, end_date, status_placeholder, ordenes=None):
    rep = MeliContable(marca, token_vigente(marca))
    if ordenes is None:
        desde = datetime.combine(start_date, datetime.min.time()).replace(tzinfo=ZONA_AR)
        hasta = datetime.combine(end_date, datetime.max.time()).replace(tzinfo=ZONA_AR)
        ordenes = rep.buscar_ordenes(desde, hasta, status_placeholder)

    pago_ids = sorted({str(p.get("id")) for o in ordenes for p in (o.get("payments") or []) if p and p.get("id")})
    status_placeholder.text(f"{marca}: leyendo {len(pago_ids)} cobros en Mercado Pago...")
    with ThreadPoolExecutor(max_workers=8) as ex:
        pagos = dict(zip(pago_ids, ex.map(rep.pago_mp, pago_ids)))
    errores = [v["_error"] for v in pagos.values() if v.get("_error")]
    if pago_ids and len(errores) == len(pago_ids):
        raise RuntimeError("Mercado Pago no devolvió el detalle de los cobros (" + errores[0] + "). "
                           "Puede que el token de MeLi no tenga acceso a Mercado Pago.")

    ship_ids = sorted({(o.get("shipping") or {}).get("id") for o in ordenes} - {None})
    status_placeholder.text(f"{marca}: consultando {len(ship_ids)} envíos...")
    with ThreadPoolExecutor(max_workers=8) as ex:
        envios = dict(zip(ship_ids, ex.map(rep.envio, ship_ids)))

    filas, contados = [], set()
    for o in sorted(ordenes, key=lambda x: x.get("date_created", "")):
        pagos_o = [pagos.get(str(p.get("id")), {}) for p in (o.get("payments") or []) if p and p.get("id")]
        filas.extend(rep.filas_orden(o, pagos_o, envios.get((o.get("shipping") or {}).get("id"), {}), contados))
    return ordenes, filas, errores


def diagnosticar_contable(marca, id_txt):
    rep = MeliContable(marca, token_vigente(marca))
    ordenes = MeliDevoluciones(marca, rep.tok).ordenes_de(None, id_txt)
    if not ordenes:
        return None
    _, filas, _ = generar_contable(marca, None, None, st.empty(), ordenes=ordenes)
    crudo = {}
    for o in ordenes:
        for p in o.get("payments") or []:
            if p and p.get("id"):
                d = rep.pago_mp(p["id"])
                crudo[str(p["id"])] = {k: d.get(k) for k in (
                    "_error", "status", "transaction_amount", "transaction_amount_refunded", "taxes_amount",
                    "transaction_details", "fee_details", "charges_details", "money_release_date")}
    return filas, crudo


# ---------- Devoluciones ----------
# Flujo: reclamos (claims) del vendedor -> los que tienen devolución -> orden original.
ESTADO_DEVOLUCION = {
    "pending": "Pendiente",
    "label_generated": "Devolución en preparación",
    "opened": "Abierta",
    "ready_to_ship": "Devolución en preparación",
    "shipped": "En camino al vendedor",
    "delivered": "Recibida",
    "not_delivered": "No entregada",
    "cancelled": "Cancelada",
    "failed": "Fallida",
    "expired": "Vencida",
    "closed": "Cerrada",
}
ESTADO_DINERO = {"retained": "Retenido", "refunded": "Reembolsado al comprador", "available": "Liberado al vendedor"}
DESTINO_DEV = {"seller_address": "Vendedor", "warehouse": "Depósito MeLi"}


def _fecha_corta(v):
    try:
        return pd.Timestamp(v).tz_convert(ZONA_AR).strftime("%d/%m/%Y") if v else ""
    except Exception:
        return str(v or "")[:10]


def estado_devolucion(dev):
    """'Devolución en preparación' = el comprador está armando el paquete para enviarlo de regreso."""
    envio = dev.get("shipping") or (dev.get("shipments") or [{}])[0] or {}
    env_st = (envio.get("status") or "").lower()
    st_ = (dev.get("status") or "").lower()
    if st_ in ("opened", "pending", "label_generated") and env_st in ("ready_to_ship", "pending", ""):
        return "Devolución en preparación"
    if env_st == "shipped" and st_ not in ("delivered", "closed", "cancelled"):
        return "En camino al vendedor"
    dinero = (dev.get("status_money") or "").lower()
    llego = st_ == "delivered" or env_st == "delivered"
    if st_ in ("delivered", "closed") or llego:
        if dinero == "refunded":
            return "Finalizada con reembolso al comprador"
        if dinero == "available":
            return "Finalizada, dinero liberado al vendedor"
        if llego:
            return "Recibida (reembolso pendiente)"
    return ESTADO_DEVOLUCION.get(st_, st_ or "S/D")


def fecha_recepcion_dev(dev):
    """Fecha en que el paquete devuelto llegó (si ya llegó)."""
    envio = dev.get("shipping") or (dev.get("shipments") or [{}])[0] or {}
    hist = envio.get("status_history") or []
    if isinstance(hist, dict):
        return _fecha_corta(hist.get("date_delivered"))
    for h in hist:
        if (h.get("status") or "").lower() == "delivered":
            return _fecha_corta(h.get("date"))
    return ""


PREFIJO_MOTIVO = {"PNR": "Producto no recibido", "PDD": "Producto defectuoso o distinto al publicado",
                  "CS": "Compra cancelada"}


@st.cache_resource
def _cache_motivos():
    return {}


class MeliDevoluciones(MeliReporte):
    def buscar_reclamos(self, desde, hasta, status_placeholder, resource_id=None, campo="date_created",
                        resource="order"):
        # MeLi exige al menos uno de estos pares de filtros:
        #   [resource + resource_id]  o  [player_role + player_user_id]
        vendedor = {"player_role": "respondent", "player_user_id": self.tok["user_id"]}
        rango = (f"{campo}:after:{desde.strftime('%Y-%m-%dT%H:%M:%S.000-03:00')},"
                 f"before:{hasta.strftime('%Y-%m-%dT%H:%M:%S.000-03:00')}")
        # Variantes por si MeLi rechaza algún parámetro (se usa la primera que responda 200)
        if resource_id:
            variantes = [
                {"resource": resource, "resource_id": resource_id},
                {**vendedor, "resource": resource, "resource_id": resource_id},
            ]
        else:
            variantes = [
                {**vendedor, "range": rango},
                vendedor,  # sin 'range': se filtra por fecha del lado de la app
            ]

        def fecha_reclamo(c):
            try:
                return pd.Timestamp(c.get(campo) or c.get("date_created")).tz_convert(ZONA_AR)
            except Exception:
                return None

        ultimo_error = ""
        for filtros in variantes:
            reclamos, offset, ok = [], 0, True
            while True:
                params = {**filtros, "limit": 50, "offset": offset, "sort": f"{campo}:desc"}
                r = self.get("/post-purchase/v1/claims/search", params)
                if r is None or r.status_code != 200:
                    ultimo_error = f"HTTP {getattr(r, 'status_code', '?')} {getattr(r, 'text', '')[:200]}"
                    ok = False
                    break
                d = r.json()
                res = d.get("data") or d.get("results") or []
                reclamos.extend(res)
                offset += len(res)
                status_placeholder.text(f"{self.marca}: {len(reclamos)} reclamos revisados...")
                if not res or offset >= (d.get("paging") or {}).get("total", 0):
                    break
                # Orden descendente: si ya pasamos el inicio del rango, cortamos
                f_ult = fecha_reclamo(res[-1])
                if not resource_id and f_ult is not None and f_ult < desde:
                    break
            if ok:
                if resource_id:
                    return reclamos
                # Filtro por fecha del lado de la app (por si MeLi ignoró el 'range')
                return [c for c in reclamos
                        if (f := fecha_reclamo(c)) is None or desde <= f <= hasta]
        raise RuntimeError(f"/claims/search {ultimo_error}")

    def motivo(self, reason_id):
        """Traduce el código (ej. PDD9939) al texto del motivo. Se cachea por servidor."""
        if not reason_id:
            return ""
        cache = _cache_motivos()
        if reason_id in cache:
            return cache[reason_id]
        texto = ""
        for path in (f"/marketplace/v2/claims/reasons/{reason_id}", f"/post-purchase/v1/claims/reasons/{reason_id}"):
            r = self.get(path)
            if r is not None and r.status_code == 200:
                d = r.json()
                texto = d.get("detail") or d.get("name") or ""
                if texto:
                    break
        if not texto:
            texto = PREFIJO_MOTIVO.get(str(reason_id)[:3], "")
        cache[reason_id] = texto
        return texto

    def obtener_reclamo(self, claim_id):
        for path in (f"/post-purchase/v1/claims/{claim_id}", f"/marketplace/v2/claims/{claim_id}"):
            r = self.get(path)
            if r is not None and r.status_code == 200 and r.json():
                return r.json()
        return None

    @staticmethod
    def mediaciones_de(o):
        """IDs de reclamos que la propia orden informa (campo 'mediations')."""
        out = []
        for m in o.get("mediations") or []:
            mid = m.get("id") if isinstance(m, dict) else m
            if mid:
                out.append(mid)
        return out

    def devolucion(self, claim_id):
        r = self.get(f"/post-purchase/v2/claims/{claim_id}/returns")
        if r is None or r.status_code != 200:
            return None
        d = r.json()
        return d if d else None

    def ordenes_de(self, resource, resource_id):
        """El reclamo puede estar sobre una orden o sobre un pack (carrito)."""
        if not resource_id:
            return []
        r = self.get(f"/orders/{resource_id}")
        if r is not None and r.status_code == 200:
            return [r.json()]
        p = self.get(f"/packs/{resource_id}")
        if p is not None and p.status_code == 200:
            out = []
            for o in p.json().get("orders") or []:
                ro = self.get(f"/orders/{o.get('id')}")
                if ro is not None and ro.status_code == 200:
                    out.append(ro.json())
            return out
        return []

    def filas_reclamo(self, claim):
        dev = self.devolucion(claim["id"])
        if not dev:
            return []
        ordenes = self.ordenes_de(claim.get("resource"), claim.get("resource_id") or dev.get("resource_id"))
        # Si la devolución informa las órdenes incluidas (pack con varios productos), traerlas todas
        ids_dev = [str(x.get("order_id")) for x in (dev.get("orders") or []) if x.get("order_id")]
        ya = {str(o.get("id")) for o in ordenes}
        for oid in ids_dev:
            if oid not in ya:
                ordenes += self.ordenes_de("order", oid)
                ya.add(oid)
        envio_dev = dev.get("shipping") or (dev.get("shipments") or [{}])[0] or {}
        # Cantidades devueltas por ítem (si MeLi las informa; si no, se toma la cantidad vendida)
        cant_dev = {}
        for x in dev.get("orders") or []:
            q = x.get("return_quantity") or x.get("total_quantity")
            if x.get("item_id") and q:
                cant_dev[str(x["item_id"])] = int(num(q))

        filas, contados = [], set()
        for o in ordenes:
            env = self.envio((o.get("shipping") or {}).get("id"))
            if no_fue_entregado(o, env):
                # El paquete nunca llegó al comprador: no es devolución, va a "Cancelados / No entregados"
                continue
            for f in self.a_filas(o, env, contados):
                if cant_dev and f["_item_id"] not in cant_dev:
                    continue  # devolución parcial: ese ítem no se devolvió
                if f["_item_id"] in cant_dev:
                    f["CANTIDAD"] = cant_dev[f["_item_id"]]
                    f["VALOR ARTICULO"] = f["_unit_price"] * f["CANTIDAD"]
                f.update({
                    "ID RECLAMO": str(claim["id"]),
                    "FECHA RECLAMO": _fecha_corta(claim.get("date_created")),
                    "ULTIMA ACTUALIZACION": _fecha_corta(dev.get("last_updated") or claim.get("last_updated")),
                    "ESTADO DEVOLUCION": estado_devolucion(dev),
                    "ESTADO DINERO": ESTADO_DINERO.get(dev.get("status_money"), dev.get("status_money") or ""),
                    "DESTINO DEVOLUCION": DESTINO_DEV.get((envio_dev.get("destination") or {}).get("name"), ""),
                    "TRACKING DEVOLUCION": str(envio_dev.get("tracking_number") or ""),
                    "MOTIVO": self.motivo(claim.get("reason_id")),
                    "CODIGO MOTIVO": claim.get("reason_id", ""),
                    "FECHA RECEPCION": fecha_recepcion_dev(dev),
                    "FECHA CIERRE": _fecha_corta(dev.get("date_closed")),
                })
                filas.append(f)
        return filas


def _ts(v):
    try:
        t = pd.Timestamp(v)
        return t.tz_convert(ZONA_AR) if t.tzinfo else t.tz_localize(ZONA_AR)
    except Exception:
        return None


def diagnosticar_devolucion(marca, id_txt, rango, status_placeholder):
    """Busca un pack u orden en una marca y explica qué pasa con su devolución.
    Devuelve None si el ID no pertenece a esa cuenta."""
    rep = MeliDevoluciones(marca, token_vigente(marca))
    ordenes = rep.ordenes_de(None, id_txt)
    if not ordenes:
        return None
    ids = {id_txt} | {str(o["id"]) for o in ordenes} | {str(o["pack_id"]) for o in ordenes if o.get("pack_id")}
    hoy = datetime.now(ZONA_AR)
    reclamos = {}
    ids_orden = {str(o["id"]) for o in ordenes}
    tecnico = {"ordenes": [{"id": o.get("id"), "pack_id": o.get("pack_id"), "status": o.get("status"),
                            "tags": o.get("tags"), "mediations": o.get("mediations"),
                            "cancel_detail": o.get("cancel_detail")} for o in ordenes],
               "busquedas": []}
    errores, intentos = [], 0
    for rid in ids:
        # El reclamo puede estar sobre la orden o sobre el pack/compra
        tipos = ["order"] if rid in ids_orden else ["purchase", "pack", "order"]
        for tipo in tipos:
            intentos += 1
            try:
                encontrados = rep.buscar_reclamos(hoy, hoy, status_placeholder, resource_id=rid, resource=tipo)
                for c in encontrados:
                    reclamos[c["id"]] = c
                tecnico["busquedas"].append(f"{tipo}={rid}: {len(encontrados)} reclamo(s)")
            except RuntimeError as e:
                errores.append(str(e))
                tecnico["busquedas"].append(f"{tipo}={rid}: {str(e)[:150]}")
    # Reclamos que la orden informa directamente (no siempre aparecen en la búsqueda)
    for o in ordenes:
        for mid in rep.mediaciones_de(o):
            if mid in reclamos or str(mid) in {str(k) for k in reclamos}:
                continue
            c = rep.obtener_reclamo(mid)
            tecnico["busquedas"].append(f"mediation {mid} de la orden {o['id']}: {'OK' if c else 'no accesible'}")
            if c:
                reclamos[c["id"]] = c
    if not reclamos and errores and len(errores) == intentos:
        raise RuntimeError(errores[0])

    filas, notas = [], []
    if not reclamos:
        for o in ordenes:
            env = rep.envio((o.get("shipping") or {}).get("id"))
            if env.get("status_raw") == "not_delivered":
                notas.append(f"Orden {o['id']}: no tiene reclamo. El envío figura como **no entregado** "
                             f"({env.get('estado_envio')}), así que vuelve sin reclamo de devolución → "
                             "aparece en el reporte **Cancelados / No entregados**.")
            elif es_devolucion(rep, o, env):
                notas.append(f"Orden {o['id']}: cancelada **después de entregada** (devolución con reembolso). "
                             "MeLi no expone el reclamo, pero entra igual en el reporte de **Devoluciones** "
                             "(por la fecha de cancelación).")
                filas.extend(filas_devolucion_sin_reclamo(rep, o, env, set()))
            elif o.get("status") == "cancelled":
                notas.append(f"Orden {o['id']}: cancelada antes de entregarse, sin devolución → "
                             "aparece en el reporte **Cancelados / No entregados**.")
            else:
                notas.append(f"Orden {o['id']}: MeLi no registra reclamos ni devoluciones "
                             f"(estado del envío: {env.get('estado_envio', 'S/D')}).")
        return filas, notas, tecnico

    for c in reclamos.values():
        fr = rep.filas_reclamo(c)
        abierto = _ts(c.get("date_created"))
        actualizado = _ts(c.get("last_updated"))
        txt = (f"Reclamo {c['id']} ({c.get('reason_id', '')}): abierto el "
               f"{abierto.strftime('%d/%m/%Y') if abierto is not None else '?'}, última actualización "
               f"{actualizado.strftime('%d/%m/%Y') if actualizado is not None else '?'}.")
        if not fr and any(no_fue_entregado(o, rep.envio((o.get("shipping") or {}).get("id"))) for o in ordenes):
            txt += (" El envío figura como **no entregado** (el paquete nunca llegó al comprador): no es una "
                    "devolución → aparece en el reporte **Cancelados / No entregados**.")
        elif not fr:
            txt += " **No tiene devolución asociada** (es una mediación/reclamo sin envío de vuelta)."
        elif rango:
            d0 = datetime.combine(rango[0], datetime.min.time()).replace(tzinfo=ZONA_AR)
            d1 = datetime.combine(rango[1], datetime.max.time()).replace(tzinfo=ZONA_AR)
            if abierto is not None and not (d0 <= abierto <= d1):
                txt += (" ⚠️ Se abrió **fuera del rango** seleccionado: con 'Fecha de apertura del reclamo' no "
                        "aparece; probá con 'Última actualización'.")
            else:
                txt += " ✅ Debería aparecer en el reporte del rango seleccionado."
        notas.append(txt)
        filas.extend(fr)
    return filas, notas, tecnico


def no_fue_entregado(o, env):
    """El paquete no llegó al comprador (vuelve o volvió al vendedor sin entregarse)."""
    return env.get("status_raw") == "not_delivered" or "not_delivered" in (o.get("tags") or [])


def es_devolucion(rep, o, env):
    """Orden cancelada que en realidad es una devolución: se entregó y después se canceló/reembolsó,
    o tiene un reclamo con devolución asociada."""
    if o.get("status") != "cancelled":
        return False
    if env.get("status_raw") == "delivered" or "delivered" in (o.get("tags") or []):
        return True
    return any(rep.devolucion(mid) for mid in rep.mediaciones_de(o))


def filas_devolucion_sin_reclamo(rep, o, env, contados):
    """Devolución que MeLi no expone como reclamo: se arma con los datos de la cancelación."""
    cd = o.get("cancel_detail") or {}
    reembolsado = any((p or {}).get("status") in ("refunded", "partially_refunded", "charged_back")
                      for p in (o.get("payments") or []))
    filas = []
    for f in rep.a_filas(o, env, contados):
        f.update({
            "ID RECLAMO": "",
            "FECHA RECLAMO": "",
            "ULTIMA ACTUALIZACION": _fecha_corta(o.get("date_last_updated")),
            "ESTADO DEVOLUCION": ("Finalizada con reembolso al comprador" if reembolsado
                                  else "Cancelada después de la entrega"),
            "ESTADO DINERO": "Reembolsado al comprador" if reembolsado else "",
            "DESTINO DEVOLUCION": "",
            "TRACKING DEVOLUCION": "",
            "MOTIVO": cd.get("description") or "Devolución (sin reclamo visible en la API)",
            "CODIGO MOTIVO": cd.get("code") or "",
            "FECHA RECEPCION": "",
            "FECHA CIERRE": _fecha_corta(cd.get("date") or o.get("date_closed")),
        })
        filas.append(f)
    return filas


def generar_devoluciones(marca, start_date, end_date, status_placeholder, resource_id=None, campo="date_created"):
    rep = MeliDevoluciones(marca, token_vigente(marca))
    desde = datetime.combine(start_date, datetime.min.time()).replace(tzinfo=ZONA_AR)
    hasta = datetime.combine(end_date, datetime.max.time()).replace(tzinfo=ZONA_AR)
    reclamos = rep.buscar_reclamos(desde, hasta, status_placeholder, resource_id, campo=campo)
    ordenes = []
    if not resource_id:
        # Complemento: órdenes con movimiento desde el inicio del rango que informan reclamos
        # (algunas devoluciones, ej. arrepentimiento, no aparecen en la búsqueda de reclamos)
        ya = {str(c.get("id")) for c in reclamos}
        ordenes = rep.buscar_ordenes(desde, max(hasta, datetime.now(ZONA_AR)), status_placeholder,
                                     campo="order.date_last_updated")
        nuevos = [mid for o in ordenes for mid in rep.mediaciones_de(o) if str(mid) not in ya]
        nuevos = list(dict.fromkeys(nuevos))
        status_placeholder.text(f"{marca}: revisando {len(nuevos)} reclamos informados por las órdenes...")
        with ThreadPoolExecutor(max_workers=6) as ex:
            for c in ex.map(rep.obtener_reclamo, nuevos):
                if not c:
                    continue
                f = _ts(c.get(campo) or c.get("date_created"))
                if f is None or desde <= f <= hasta:
                    reclamos.append(c)
    status_placeholder.text(f"{marca}: revisando {len(reclamos)} reclamos con posible devolución...")
    filas = []
    with ThreadPoolExecutor(max_workers=6) as ex:
        for res in ex.map(rep.filas_reclamo, reclamos):
            filas.extend(res)

    # Órdenes canceladas después de entregadas = devoluciones aunque no haya reclamo visible
    cubiertas = {str(f["ORDEN MELI"]) for f in filas}
    pendientes = [o for o in ordenes if o.get("status") == "cancelled" and str(o["id"]) not in cubiertas]
    if pendientes:
        status_placeholder.text(f"{marca}: revisando {len(pendientes)} órdenes canceladas...")
        ship_ids = sorted({(o.get("shipping") or {}).get("id") for o in pendientes} - {None})
        with ThreadPoolExecutor(max_workers=8) as ex:
            envios = dict(zip(ship_ids, ex.map(rep.envio, ship_ids)))
        contados = set()
        for o in pendientes:
            env = envios.get((o.get("shipping") or {}).get("id"), {})
            if no_fue_entregado(o, env) or not es_devolucion(rep, o, env):
                continue
            cd = o.get("cancel_detail") or {}
            f_ev = _ts(cd.get("date")) or _ts(o.get("date_last_updated"))
            if f_ev is not None and desde <= f_ev <= hasta:
                filas.extend(filas_devolucion_sin_reclamo(rep, o, env, contados))
    return reclamos, filas


COLUMNAS_DEVOLUCION = [
    "MARCA", "PACK ID", "ORDEN MELI", "ORDER ID MP (ID PAGO)", "ID RECLAMO", "FECHA", "FECHA RECLAMO", "ULTIMA ACTUALIZACION",
    "ESTADO", "ESTADO DEL PEDIDO", "ESTADO DEVOLUCION", "ESTADO DINERO", "DESTINO DEVOLUCION",
    "TRACKING DEVOLUCION", "MOTIVO", "CODIGO MOTIVO", "SKU", "DESCRIPCION", "CANTIDAD", "VALOR ARTICULO",
    "IMPORTE DEL ENVIO", "COSTO ENVIO VENDEDOR", "ANULACIONES Y REEMBOLSOS", "FECHA RECEPCION", "FECHA CIERRE",
]


# ---------- Cancelados y no entregados ----------
QUIEN_CANCELA = {"buyer": "Comprador", "seller": "Vendedor", "mediator": "MercadoLibre",
                 "meli": "MercadoLibre", "shipment": "Logística MeLi", "fraud": "MercadoLibre (fraude)"}
MOTIVO_NO_ENTREGA = {
    "returning_to_sender": "Volviendo al vendedor",
    "returned_to_sender": "Devuelto al vendedor",
    "returned": "Devuelto al vendedor",
    "receiver_absent": "Comprador ausente",
    "bad_address": "Dirección incorrecta",
    "not_visited": "Domicilio no visitado",
    "damaged": "Paquete dañado",
    "lost": "Paquete perdido",
    "stolen": "Paquete robado",
    "refused_delivery": "Entrega rechazada por el comprador",
    "to_review": "En revisión",
    "unclaimed": "No retirado por el comprador",
    "delivery_failed": "Entrega fallida",
}
COLUMNAS_CANCELADOS = [
    "MARCA", "TIPO", "PACK ID", "ORDEN MELI", "ORDER ID MP (ID PAGO)", "FECHA", "FECHA EVENTO",
    "ESTADO", "ESTADO DEL PEDIDO", "MOTIVO", "QUIEN CANCELA", "SKU", "DESCRIPCION", "CANTIDAD",
    "VALOR ARTICULO", "IMPORTE DEL ENVIO", "COSTO ENVIO VENDEDOR", "ANULACIONES Y REEMBOLSOS",
]


def generar_cancelados(marca, start_date, end_date, status_placeholder):
    """Órdenes canceladas o con envío no entregado cuyo evento ocurrió en el rango.
    Se buscan por fecha de ÚLTIMA ACTUALIZACIÓN (desde el inicio del rango hasta hoy), porque la
    cancelación o la no entrega pasan después de la venta; luego se filtra por la fecha del evento."""
    rep = MeliDevoluciones(marca, token_vigente(marca))
    desde = datetime.combine(start_date, datetime.min.time()).replace(tzinfo=ZONA_AR)
    hasta = datetime.combine(end_date, datetime.max.time()).replace(tzinfo=ZONA_AR)
    ahora = datetime.now(ZONA_AR)

    ordenes = rep.buscar_ordenes(desde, max(hasta, ahora), status_placeholder, campo="order.date_last_updated")

    def fue_pagada(o):
        return any((p or {}).get("status") in ("approved", "refunded", "charged_back", "partially_refunded",
                                                  "in_mediation")
                   for p in (o.get("payments") or []))

    # Candidatas: canceladas (pagadas) + todo lo que no figura como entregado
    candidatas = [o for o in ordenes
                  if fue_pagada(o) and (o.get("status") == "cancelled" or "delivered" not in (o.get("tags") or []))]
    ship_ids = sorted({(o.get("shipping") or {}).get("id") for o in candidatas} - {None})
    envios = {}
    status_placeholder.text(f"{marca}: revisando {len(ship_ids)} envíos...")
    with ThreadPoolExecutor(max_workers=8) as ex:
        for sid, env in zip(ship_ids, ex.map(rep.envio, ship_ids)):
            envios[sid] = env

    filas, contados = [], set()
    for o in sorted(candidatas, key=lambda x: x.get("date_created", "")):
        sid = (o.get("shipping") or {}).get("id")
        env = envios.get(sid, {})
        no_entregado = no_fue_entregado(o, env)
        cancelado = o.get("status") == "cancelled"
        if not (no_entregado or cancelado):
            continue
        # Si es una devolución (cancelada después de entregada, o con devolución asociada) va al
        # reporte de Devoluciones, no acá -> evita cargar dos veces la misma NC
        if not no_entregado and es_devolucion(rep, o, env):
            continue

        cd = o.get("cancel_detail") or {}
        if no_entregado:
            tipo = "No entregado" + (" (cancelado)" if cancelado else "")
            fecha_ev = _ts(env.get("fecha_no_entrega")) or _ts(o.get("date_last_updated"))
            motivo = MOTIVO_NO_ENTREGA.get(env.get("substatus_raw"), env.get("substatus_raw") or "No entregado")
            quien = ""
        else:
            tipo = "Cancelado"
            fecha_ev = _ts(cd.get("date")) or _ts(o.get("date_closed")) or _ts(o.get("date_last_updated"))
            motivo = cd.get("description") or cd.get("code") or ""
            quien = QUIEN_CANCELA.get(str(cd.get("requested_by") or cd.get("group") or "").lower(),
                                      cd.get("requested_by") or cd.get("group") or "")

        if fecha_ev is None or not (desde <= fecha_ev <= hasta):
            continue

        for f in rep.a_filas(o, env, contados):
            f.update({
                "TIPO": tipo,
                "FECHA EVENTO": fecha_ev.strftime("%d/%m/%Y"),
                "MOTIVO": motivo,
                "QUIEN CANCELA": quien,
            })
            filas.append(f)
    return candidatas, filas


def _pesos(x):
    try:
        return "$ " + f"{float(x):,.0f}".replace(",", ".")
    except Exception:
        return "$ 0"


def _miles(x):
    return f"{int(x):,}".replace(",", ".")


def calcular_kpis(df, tipo):
    """Cuatro indicadores para mostrar arriba de la descarga, según el tipo de reporte."""
    def col(c):
        return df[c] if c in df.columns else pd.Series(dtype=float)

    marcas = col("MARCA").nunique()
    if tipo == "shopify":
        pedidos = col("PEDIDO").nunique()
        unidades = pd.to_numeric(col("CANTIDAD"), errors="coerce").sum()
        total = (df.drop_duplicates(["MARCA", "PEDIDO"])["TOTAL PEDIDO"].sum()
                 if {"MARCA", "PEDIDO", "TOTAL PEDIDO"} <= set(df.columns) else 0)
        return [("Facturación", _pesos(total), True), ("Pedidos", _miles(pedidos), False),
                ("Unidades", _miles(unidades), False), ("Marcas", _miles(marcas), False)]
    pedidos = col("PACK ID").nunique()
    unidades = pd.to_numeric(col("CANTIDAD"), errors="coerce").sum()
    valor = pd.to_numeric(col("VALOR ARTICULO"), errors="coerce").sum()
    if tipo == "contable":
        def suma(c):
            return pd.to_numeric(col(c), errors="coerce").sum()
        comisiones = suma("COMISION MERCADO LIBRE (INCLUYE IVA)") + suma("COMISION POR OFRECER CUOTAS SIN INTERES")
        return [("Monto neto", _pesos(suma("MONTO NETO")), True), ("Bruto", _pesos(suma("MONTO BRUTO DE LA OPERACION"))
                 , False), ("Comisiones", _pesos(comisiones), False),
                ("Envío + impuestos", _pesos(suma("COSTO DE ENVIO") + suma("IMPUESTOS")), False)]
    if tipo == "ventas":
        # El envío se repite en cada fila del pack: se cuenta una sola vez por pack
        envio = (pd.to_numeric(df.drop_duplicates(["MARCA", "PACK ID"])["IMPORTE DEL ENVIO"], errors="coerce").sum()
                 if {"MARCA", "PACK ID", "IMPORTE DEL ENVIO"} <= set(df.columns) else 0)
        total = valor + envio
        return [("Facturación", _pesos(total), True), ("Pedidos", _miles(pedidos), False),
                ("Unidades", _miles(unidades), False), ("Marcas", _miles(marcas), False)]
    reemb = pd.to_numeric(col("ANULACIONES Y REEMBOLSOS"), errors="coerce").sum()
    etiqueta = "Devoluciones" if tipo == "devoluciones" else "Casos"
    return [("Valor de mercadería", _pesos(valor), True), (etiqueta, _miles(pedidos), False),
            ("Unidades", _miles(unidades), False), ("Reembolsado", _pesos(reemb), False)]


def descargar_excel(df, nombre_hoja, file_name, start_time, tipo="ventas"):
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name=nombre_hoja)

    elapsed = time_lib.time() - start_time
    st.markdown(f'<div class="listo">✨ Reporte listo en {elapsed:.0f} segundos · {_miles(len(df))} filas</div>',
                unsafe_allow_html=True)
    kpis = calcular_kpis(df, tipo)
    st.markdown('<div class="kpis">' + "".join(
        f'<div class="kpi{" destacado" if dest else ""}"><div class="lbl">{lbl}</div><div class="val">{val}</div></div>'
        for lbl, val, dest in kpis) + "</div>", unsafe_allow_html=True)

    st.download_button(
        label=f"⬇️  Descargar Excel  ·  {file_name}",
        data=output.getvalue(),
        file_name=file_name,
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        use_container_width=True,
    )
    with st.expander("👀 Vista previa (primeras 50 filas)"):
        st.dataframe(df.head(50), use_container_width=True, hide_index=True)


def paso(n, titulo, sub=""):
    st.markdown(f'<div class="paso"><div class="num">{n}</div><div><div class="tit">{titulo}</div>'
                f'<div class="sub">{sub}</div></div></div>', unsafe_allow_html=True)


def chips_marcas(resultados):
    if resultados:
        st.markdown('<div class="marcas-res">' + "".join(
            f'<span class="marca-res {"ok" if ok else "err"}">{txt}</span>' for ok, txt in resultados) + "</div>",
            unsafe_allow_html=True)


# ---------- Vuelta del login de MeLi (?code=...&state=Marca) ----------
_qp = st.query_params
if "code" in _qp and "state" in _qp and not MELI_FALTANTES:
    _marca_cb = _qp.get("state")
    _code_cb = _qp.get("code")
    st.query_params.clear()
    if _marca_cb in MELI_CUENTAS:
        try:
            _nick = conectar_cuenta(_marca_cb, _code_cb)
            st.success(f"✅ {_marca_cb} conectada a MercadoLibre ({_nick}).")
        except Exception as e:
            st.error(f"No se pudo conectar {_marca_cb}: {e}")


# --- Interfaz de Usuario ---
conectadas = {}
if not MELI_FALTANTES:
    try:
        _estado_tk = _estado_tokens()
        with _estado_tk["lock"]:
            conectadas = dict(_cargar_tokens(_estado_tk))
    except Exception:
        conectadas = {}

st.markdown(f"""
<div class="hero">
  <span class="kicker">Distrinando · E-commerce</span>
  <h1>Tus ventas, <span>en un clic.</span></h1>
  <p>Ventas, devoluciones y cancelaciones de Shopify y MercadoLibre, listas para cargar en SAP.</p>
  <div class="chips">
    <span class="chip">🛍️ Shopify · <b>{len(STORES)}</b> tiendas</span>
    <span class="chip">🤝 MercadoLibre · <b>{len(conectadas)}/{len(MELI_CUENTAS)}</b> cuentas</span>
    <span class="chip">📊 Excel listo para ERP</span>
  </div>
</div>
""", unsafe_allow_html=True)

# ---- Paso 1: canal y tipo de reporte ----
with st.container(border=True):
    paso(1, "¿Qué querés descargar?", "Elegí el canal y el tipo de reporte")
    canal = st.radio("Canal", ["🛍️ Shopify", "🤝 MercadoLibre"], horizontal=True, label_visibility="collapsed")
    canal = "Shopify" if "Shopify" in canal else "MercadoLibre"

    tipo_meli = "Ventas"
    campo_dev = "date_created"
    if canal == "MercadoLibre":
        if MELI_FALTANTES:
            st.error("Faltan en los secrets, sección [meli]: " + ", ".join(MELI_FALTANTES))
            if "fernet_key" in MELI_FALTANTES:
                st.caption("fernet_key: podés usar esta (generada recién, copiala a los secrets):")
                st.code(Fernet.generate_key().decode())
            st.stop()

        opciones_tipo = {"💰 Ventas": "Ventas", "↩️ Devoluciones": "Devoluciones",
                         "🚫 Cancelados / No entregados": "Cancelados / No entregados",
                         "🧾 Contable": "Contable"}
        tipo_meli = opciones_tipo[st.radio("Reporte", list(opciones_tipo), horizontal=True,
                                           label_visibility="collapsed")]
        if tipo_meli == "Contable":
            st.caption("Detalle de cada cobro en Mercado Pago (bruto, comisiones, cuotas sin interés, envío, "
                       "impuestos y neto) de las ventas del período, más devoluciones de dinero y tarifas de envío.")
        if tipo_meli == "Cancelados / No entregados":
            st.caption("Ventas pagadas que se cancelaron antes de entregarse o cuyo envío no llegó al comprador, "
                       "según la fecha en que pasó.")
        if tipo_meli == "Devoluciones":
            st.caption("Filtrar devoluciones por:")
            fecha_dev = st.radio("Filtrar devoluciones por", ["📬 Apertura del reclamo", "🔄 Última actualización"],
                                 horizontal=True, label_visibility="collapsed")
            campo_dev = "date_created" if "Apertura" in fecha_dev else "last_updated"
            st.caption("'Última actualización' suma reclamos abiertos antes que tuvieron movimiento en el rango "
                       "(se preparó, llegó o se reembolsó).")

        with st.expander(f"⚙️ Cuentas de MercadoLibre · {len(conectadas)}/{len(MELI_CUENTAS)} conectadas"):
            st.caption("Para conectar: iniciá sesión en mercadolibre.com.ar con la cuenta de esa marca "
                       "en este navegador y tocá su botón. Se hace una sola vez por cuenta.")
            for m in MELI_CUENTAS:
                c1, c2 = st.columns([3, 2])
                info = conectadas.get(m)
                color = "#10B981" if info else "#EF4444"
                detalle = (info.get("nickname") or info.get("user_id")) if info else "sin conectar"
                c1.markdown(f'<div class="cuenta"><span class="dot" style="background:{color}"></span>{m}'
                            f'<span style="color:#6B6880;font-weight:500">· {detalle}</span></div>',
                            unsafe_allow_html=True)
                url = f"{MELI_AUTH}?" + urlencode({"response_type": "code", "client_id": MELI_APP_ID,
                                                   "redirect_uri": MELI_REDIRECT, "state": m})
                c2.link_button("Reconectar" if info else "Conectar", url, use_container_width=True)

# ---- Paso 2: período y marcas ----
hoy_ar = datetime.now(ZONA_AR).date()
if "rango_fechas" not in st.session_state:
    st.session_state["rango_fechas"] = ()


def _set_rango(d0, d1):
    st.session_state["rango_fechas"] = (d0, d1)


_ini_mes = hoy_ar.replace(day=1)
_fin_mes_ant = _ini_mes - timedelta(days=1)
ATAJOS = [
    ("Hoy", hoy_ar, hoy_ar),
    ("Ayer", hoy_ar - timedelta(days=1), hoy_ar - timedelta(days=1)),
    ("7 días", hoy_ar - timedelta(days=6), hoy_ar),
    ("Este mes", _ini_mes, hoy_ar),
    ("Mes pasado", _fin_mes_ant.replace(day=1), _fin_mes_ant),
]

with st.container(border=True):
    paso(2, "¿De qué período y marcas?", "Usá un atajo o elegí las fechas a mano")
    cols_at = st.columns(len(ATAJOS))
    for c, (txt, d0, d1) in zip(cols_at, ATAJOS):
        c.button(txt, key=f"atajo_{txt}", on_click=_set_rango, args=(d0, d1), use_container_width=True)

    col1, col2 = st.columns(2)
    with col1:
        date_range = st.date_input("📅 Rango de fechas", key="rango_fechas", format="DD/MM/YYYY")
    with col2:
        available_brands = list(STORES.keys()) if canal == "Shopify" else MELI_CUENTAS
        selected_brands = st.multiselect("🏷️ Marcas", available_brands, default=available_brands,
                                         key=f"marcas_{canal}")

if canal == "MercadoLibre" and tipo_meli == "Ventas":
    with st.expander("🔎 Revisar importes de un pack / orden puntual"):
        ids_v = st.text_area("Pack IDs u órdenes de MeLi (uno por línea)", key="ids_venta", height=80)
        if st.button("Revisar", key="btn_revisar_venta") and ids_v.strip():
            for id_x in dict.fromkeys(x.strip() for x in ids_v.replace(",", "\n").splitlines() if x.strip()):
                encontrado = False
                for m in MELI_CUENTAS:
                    try:
                        res = diagnosticar_envio(m, id_x)
                    except Exception as e:
                        if "no conectada" not in str(e):
                            st.warning(f"{id_x} / {m}: {e}")
                        continue
                    if res is None:
                        continue
                    encontrado = True
                    resumen, crudo = res
                    st.markdown(f"**{id_x}** — {m}")
                    st.markdown("\n".join(f"- {k}: **{_pesos(v)}**" for k, v in resumen.items()))
                    st.json(crudo, expanded=False)
                    break
                if not encontrado:
                    st.markdown(f"**{id_x}** — no lo encontré en ninguna de las cuentas conectadas.")

if canal == "MercadoLibre" and tipo_meli == "Contable":
    with st.expander("🔎 Revisar el detalle contable de un pack / orden puntual"):
        ids_c = st.text_area("Pack IDs u órdenes de MeLi (uno por línea)", key="ids_cont", height=80)
        if st.button("Revisar", key="btn_revisar_cont") and ids_c.strip():
            for id_x in dict.fromkeys(x.strip() for x in ids_c.replace(",", "\n").splitlines() if x.strip()):
                encontrado = False
                for m in MELI_CUENTAS:
                    try:
                        res = diagnosticar_contable(m, id_x)
                    except Exception as e:
                        if "no conectada" not in str(e):
                            st.warning(f"{id_x} / {m}: {e}")
                        continue
                    if res is None:
                        continue
                    encontrado = True
                    filas_c, crudo = res
                    st.markdown(f"**{id_x}** — {m}")
                    if filas_c:
                        df_c = pd.DataFrame(filas_c)
                        st.dataframe(df_c[[c for c in COLUMNAS_CONTABLE if c in df_c.columns]],
                                     use_container_width=True, hide_index=True)
                    st.json(crudo, expanded=False)
                    break
                if not encontrado:
                    st.markdown(f"**{id_x}** — no lo encontré en ninguna de las cuentas conectadas.")

if canal == "MercadoLibre" and tipo_meli == "Devoluciones":
    with st.expander("🔎 Buscar devoluciones de packs / órdenes puntuales"):
        ids_txt = st.text_area("Pack IDs u órdenes de MeLi (uno por línea)", key="ids_dev", height=100)
        ver_tecnico = st.checkbox("Mostrar datos técnicos (para diagnóstico)", key="tec_dev")
        if st.button("Buscar", key="btn_buscar_dev") and ids_txt.strip():
            ph = st.empty()
            rango_sel = date_range if len(date_range) == 2 else None
            filas_b = []
            for id_x in dict.fromkeys(x.strip() for x in ids_txt.replace(",", "\n").splitlines() if x.strip()):
                encontrado = False
                for m in MELI_CUENTAS:
                    try:
                        res = diagnosticar_devolucion(m, id_x, rango_sel, ph)
                    except Exception as e:
                        if "no conectada" not in str(e):
                            st.warning(f"{id_x} / {m}: {e}")
                        continue
                    if res is None:
                        continue
                    encontrado = True
                    filas_x, notas, tecnico = res
                    st.markdown(f"**{id_x}** — {m}")
                    for n in notas:
                        st.markdown(f"- {n}")
                    if ver_tecnico:
                        st.json(tecnico, expanded=False)
                    filas_b += filas_x
                    break
                if not encontrado:
                    st.markdown(f"**{id_x}** — no lo encontré en ninguna de las cuentas conectadas.")
            ph.empty()
            if filas_b:
                df_b = pd.DataFrame(filas_b)
                st.dataframe(df_b[[c for c in COLUMNAS_DEVOLUCION if c in df_b.columns]],
                             use_container_width=True, hide_index=True)

st.write("")
_txt_boton = {"Ventas": "Generar reporte de ventas", "Devoluciones": "Generar reporte de devoluciones",
              "Contable": "Generar reporte contable",
              "Cancelados / No entregados": "Generar reporte de cancelados"}
if st.button(f"🚀  {_txt_boton[tipo_meli] if canal == 'MercadoLibre' else 'Generar reporte de Shopify'}",
             type="primary", use_container_width=True):
    if canal == "Shopify" and not STORES:
        st.error("Credenciales de Shopify no configuradas en st.secrets.")
    elif len(date_range) != 2:
        st.warning("📅 Elegí fecha de inicio y fin (o usá un atajo).")
    elif not selected_brands:
        st.warning("🏷️ Elegí al menos una marca.")
    else:
        start_date, end_date = date_range
        all_data = []
        resultados = []
        start_time = time_lib.time()
        progress_bar = st.progress(0)
        status_placeholder = st.empty()

        if canal == "Shopify":
            start_str = datetime.combine(start_date, datetime.min.time()).isoformat() + "-03:00"
            end_str = datetime.combine(end_date, datetime.max.time()).isoformat() + "-03:00"

            for i, marca in enumerate(selected_brands):
                store_info = STORES[marca]
                try:
                    status_placeholder.text(f"{marca}: verificando permisos...")
                    test_query_permissions(store_info, start_str, end_str)

                    status_placeholder.text(f"{marca}: iniciando exportación...")
                    inner_query = build_inner_query(start_str, end_str)
                    run_bulk_query(store_info, inner_query)

                    download_url = wait_for_bulk_operation(store_info, status_placeholder, marca)
                    raw_rows = download_jsonl(download_url)

                    orders = build_orders_from_bulk(raw_rows)
                    processed_rows = process_orders_bulk(orders, marca)
                    all_data.extend(processed_rows)
                    resultados.append((True, f"{marca} · {len(orders)} pedidos"))
                except RuntimeError as e:
                    resultados.append((False, f"{marca} · error"))
                    st.error(f"{marca}: error durante la exportación — {e}")

                progress_bar.progress((i + 1) / len(selected_brands))

        else:  # MercadoLibre
            for i, marca in enumerate(selected_brands):
                try:
                    status_placeholder.text(f"{marca}: verificando token...")
                    if tipo_meli == "Ventas":
                        ordenes, filas = generar_meli(marca, start_date, end_date, status_placeholder)
                        resultados.append((True, f"{marca} · {len(ordenes)} órdenes"))
                    elif tipo_meli == "Devoluciones":
                        reclamos, filas = generar_devoluciones(marca, start_date, end_date, status_placeholder,
                                                               campo=campo_dev)
                        resultados.append((True, f"{marca} · {len(filas)} filas"))
                    elif tipo_meli == "Contable":
                        ordenes, filas, errores_mp = generar_contable(marca, start_date, end_date, status_placeholder)
                        resultados.append((True, f"{marca} · {len(ordenes)} órdenes"))
                        if errores_mp:
                            st.warning(f"{marca}: {len(errores_mp)} cobros sin detalle de Mercado Pago "
                                       f"({errores_mp[0][:80]}).")
                    else:
                        candidatas, filas = generar_cancelados(marca, start_date, end_date, status_placeholder)
                        resultados.append((True, f"{marca} · {len(filas)} filas"))
                    all_data.extend(filas)
                except Exception as e:
                    resultados.append((False, f"{marca} · error"))
                    st.error(f"{marca}: error durante la exportación — {e}")

                progress_bar.progress((i + 1) / len(selected_brands))

        progress_bar.empty()
        status_placeholder.empty()
        chips_marcas(resultados)

        if all_data:
            df = pd.DataFrame(all_data)
            if canal == "Shopify":
                descargar_excel(df, "Ventas", f"Reporte_{start_date}_al_{end_date}.xlsx", start_time, "shopify")
            elif tipo_meli == "Ventas":
                df = df.drop(columns=["_item_id", "_unit_price"], errors="ignore")
                # Envío del pack repetido en todas sus filas (entra en la facturación)
                df["IMPORTE DEL ENVIO"] = df.groupby(["MARCA", "PACK ID"])["IMPORTE DEL ENVIO"].transform("sum")
                # Total del pedido = artículos del pack + envío del pack (se repite en cada fila)
                total_pack = (df.groupby(["MARCA", "PACK ID"])["VALOR ARTICULO"].transform("sum")
                              + df["IMPORTE DEL ENVIO"])
                df.insert(df.columns.get_loc("VALOR ARTICULO") + 1, "TOTAL SUMA VALOR PEDIDO", total_pack)
                # Datos del cliente justo después de la FECHA
                cols_cli = [c for c in COLUMNAS_CLIENTE if c in df.columns]
                resto = [c for c in df.columns if c not in cols_cli]
                pos = resto.index("FECHA") + 1 if "FECHA" in resto else len(resto)
                df = df[resto[:pos] + cols_cli + resto[pos:]]
                descargar_excel(df, "Ventas MeLi", f"Reporte_MeLi_{start_date}_al_{end_date}.xlsx", start_time,
                                "ventas")
            elif tipo_meli == "Devoluciones":
                df = df[[c for c in COLUMNAS_DEVOLUCION if c in df.columns]]
                descargar_excel(df, "Devoluciones MeLi",
                                f"Devoluciones_MeLi_{start_date}_al_{end_date}.xlsx", start_time, "devoluciones")
            elif tipo_meli == "Contable":
                df = df[[c for c in COLUMNAS_CONTABLE if c in df.columns]].fillna(0)
                descargar_excel(df, "Contable MeLi", f"Contable_MeLi_{start_date}_al_{end_date}.xlsx", start_time,
                                "contable")
            else:
                df = df[[c for c in COLUMNAS_CANCELADOS if c in df.columns]]
                descargar_excel(df, "Cancelados MeLi",
                                f"Cancelados_NoEntregados_MeLi_{start_date}_al_{end_date}.xlsx", start_time,
                                "cancelados")
        else:
            que = "ventas"
            if canal == "MercadoLibre" and tipo_meli == "Devoluciones":
                que = "devoluciones"
            elif canal == "MercadoLibre" and tipo_meli == "Contable":
                que = "cobros"
            elif canal == "MercadoLibre" and tipo_meli != "Ventas":
                que = "cancelaciones ni envíos no entregados"
            st.info(f"🌤️ No se registraron {que} en el período seleccionado.")
