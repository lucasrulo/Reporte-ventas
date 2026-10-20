import streamlit as st
import requests
import pandas as pd
from datetime import datetime
import time as time_lib
import io
import json

# 1. Configuración Minimalista de la página
st.set_page_config(page_title="Descarga ventas Shopify + MeLi", layout="centered")

hide_st_style = """
            <style>
            #MainMenu {visibility: hidden;}
            footer {visibility: hidden;}
            header {visibility: hidden;}
            .stButton>button {width: 100%; border-radius: 4px;}
            </style>
            """
st.markdown(hide_st_style, unsafe_allow_html=True)

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
            out["status_raw"] = (s.get("status") or "").lower()
            out["substatus_raw"] = (s.get("substatus") or "").lower()
            hist = s.get("status_history") or {}
            out["fecha_no_entrega"] = (hist.get("date_not_delivered") or hist.get("date_returned")
                                       or hist.get("date_cancelled") or s.get("last_updated"))
        c = self.get(f"/shipments/{shipping_id}/costs")
        if c is not None and c.status_code == 200:
            cj = c.json()
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

        envio_comprador = sum(num(p.get("shipping_cost")) for p in aprobados)
        shipping_id = (o.get("shipping") or {}).get("id")
        if not envio_comprador and shipping_id and shipping_id not in envio_ya_contado:
            # Respaldo: costo del envío que figura para el comprador en /shipments/{id}/costs
            envio_comprador = env.get("costo_comprador", 0.0)

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
                "_item_id": str(item.get("id") or ""),
                "_unit_price": num(oi.get("unit_price")),
            })
            if primera and shipping_id:
                envio_ya_contado.add(shipping_id)
        return filas


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

    filas, contados = [], set()
    for o in sorted(ordenes, key=lambda x: x.get("date_created", "")):
        sid = (o.get("shipping") or {}).get("id")
        filas.extend(rep.a_filas(o, envios.get(sid, {}), contados))
    return ordenes, filas


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
    return ESTADO_DEVOLUCION.get(st_, st_ or "S/D")


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
    errores, intentos = [], 0
    for rid in ids:
        # El reclamo puede estar sobre la orden o sobre el pack/compra
        tipos = ["order"] if rid in ids_orden else ["purchase", "pack", "order"]
        for tipo in tipos:
            intentos += 1
            try:
                for c in rep.buscar_reclamos(hoy, hoy, status_placeholder, resource_id=rid, resource=tipo):
                    reclamos[c["id"]] = c
            except RuntimeError as e:
                errores.append(str(e))
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
            elif o.get("status") == "cancelled":
                notas.append(f"Orden {o['id']}: no tiene reclamo, la venta está **cancelada** → "
                             "aparece en el reporte **Cancelados / No entregados**.")
            else:
                notas.append(f"Orden {o['id']}: MeLi no registra reclamos ni devoluciones "
                             f"(estado del envío: {env.get('estado_envio', 'S/D')}).")
        return filas, notas

    for c in reclamos.values():
        fr = rep.filas_reclamo(c)
        abierto = _ts(c.get("date_created"))
        actualizado = _ts(c.get("last_updated"))
        txt = (f"Reclamo {c['id']} ({c.get('reason_id', '')}): abierto el "
               f"{abierto.strftime('%d/%m/%Y') if abierto is not None else '?'}, última actualización "
               f"{actualizado.strftime('%d/%m/%Y') if actualizado is not None else '?'}.")
        if not fr:
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
    return filas, notas


def generar_devoluciones(marca, start_date, end_date, status_placeholder, resource_id=None, campo="date_created"):
    rep = MeliDevoluciones(marca, token_vigente(marca))
    desde = datetime.combine(start_date, datetime.min.time()).replace(tzinfo=ZONA_AR)
    hasta = datetime.combine(end_date, datetime.max.time()).replace(tzinfo=ZONA_AR)
    reclamos = rep.buscar_reclamos(desde, hasta, status_placeholder, resource_id, campo=campo)
    status_placeholder.text(f"{marca}: revisando {len(reclamos)} reclamos con posible devolución...")
    filas = []
    with ThreadPoolExecutor(max_workers=6) as ex:
        for res in ex.map(rep.filas_reclamo, reclamos):
            filas.extend(res)
    return reclamos, filas


COLUMNAS_DEVOLUCION = [
    "MARCA", "PACK ID", "ORDEN MELI", "ORDER ID MP (ID PAGO)", "ID RECLAMO", "FECHA", "FECHA RECLAMO", "ULTIMA ACTUALIZACION",
    "ESTADO", "ESTADO DEL PEDIDO", "ESTADO DEVOLUCION", "ESTADO DINERO", "DESTINO DEVOLUCION",
    "TRACKING DEVOLUCION", "MOTIVO", "CODIGO MOTIVO", "SKU", "DESCRIPCION", "CANTIDAD", "VALOR ARTICULO",
    "IMPORTE DEL ENVIO", "COSTO ENVIO VENDEDOR", "ANULACIONES Y REEMBOLSOS", "FECHA CIERRE",
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
    rep = MeliReporte(marca, token_vigente(marca))
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
        no_entregado = env.get("status_raw") == "not_delivered"
        cancelado = o.get("status") == "cancelled"
        if not (no_entregado or cancelado):
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


def descargar_excel(df, nombre_hoja, file_name, start_time):
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name=nombre_hoja)

    elapsed = time_lib.time() - start_time
    st.success(f"Reporte procesado en {elapsed:.0f} segundos.")

    with st.expander("Ver vista previa"):
        st.dataframe(df.head(50), use_container_width=True)

    st.download_button(
        label="Descargar Archivo",
        data=output.getvalue(),
        file_name=file_name,
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )


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
st.title("Consolidador de Ventas")
st.write("---")

canal = st.radio("Canal", ["Shopify", "MercadoLibre"], horizontal=True)

if canal == "MercadoLibre":
    if MELI_FALTANTES:
        st.error("Faltan en los secrets, sección [meli]: " + ", ".join(MELI_FALTANTES))
        if "fernet_key" in MELI_FALTANTES:
            st.caption("fernet_key: podés usar esta (generada recién, copiala a los secrets):")
            st.code(Fernet.generate_key().decode())
        st.stop()

    with st.expander("⚙️ Cuentas de MercadoLibre"):
        st.caption("Para conectar: iniciá sesión en mercadolibre.com.ar con la cuenta de esa marca "
                   "en este navegador y tocá su botón. Se hace una sola vez por cuenta.")
        try:
            estado_tk = _estado_tokens()
            with estado_tk["lock"]:
                conectadas = dict(_cargar_tokens(estado_tk))
        except Exception as e:
            conectadas = {}
            st.error(str(e))
        for m in MELI_CUENTAS:
            c1, c2 = st.columns([3, 2])
            info = conectadas.get(m)
            c1.write(f"**{m}** — " + (f"✅ {info.get('nickname') or info.get('user_id')}" if info else "❌ sin conectar"))
            url = f"{MELI_AUTH}?" + urlencode({"response_type": "code", "client_id": MELI_APP_ID,
                                               "redirect_uri": MELI_REDIRECT, "state": m})
            c2.link_button("Reconectar" if info else "Conectar", url)

tipo_meli = "Ventas"
campo_dev = "date_created"
if canal == "MercadoLibre":
    tipo_meli = st.radio("Reporte", ["Ventas", "Devoluciones", "Cancelados / No entregados"], horizontal=True)
    if tipo_meli == "Cancelados / No entregados":
        st.caption("Trae las ventas pagadas que se cancelaron o cuyo envío no se entregó, "
                   "cuando la cancelación / no entrega ocurrió dentro del rango de fechas.")
    if tipo_meli == "Devoluciones":
        fecha_dev = st.radio("Filtrar devoluciones por", ["Fecha de apertura del reclamo", "Última actualización"],
                             horizontal=True,
                             help="'Última actualización' incluye reclamos abiertos antes del rango que "
                                  "tuvieron movimiento dentro del rango (ej. la devolución se preparó o llegó).")
        campo_dev = "date_created" if fecha_dev.startswith("Fecha de apertura") else "last_updated"

col1, col2 = st.columns(2)
with col1:
    date_range = st.date_input("Rango de Fechas", [])
with col2:
    available_brands = list(STORES.keys()) if canal == "Shopify" else MELI_CUENTAS
    selected_brands = st.multiselect("Marcas", available_brands, default=available_brands, key=f"marcas_{canal}")

if canal == "MercadoLibre" and tipo_meli == "Devoluciones":
    with st.expander("🔎 Buscar devoluciones de packs / órdenes puntuales"):
        ids_txt = st.text_area("Pack IDs u órdenes de MeLi (uno por línea)", key="ids_dev", height=100)
        if st.button("Buscar") and ids_txt.strip():
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
                    filas_x, notas = res
                    st.markdown(f"**{id_x}** — {m}")
                    for n in notas:
                        st.markdown(f"- {n}")
                    filas_b += filas_x
                    break
                if not encontrado:
                    st.markdown(f"**{id_x}** — no lo encontré en ninguna de las cuentas conectadas.")
            ph.empty()
            if filas_b:
                df_b = pd.DataFrame(filas_b)
                st.dataframe(df_b[[c for c in COLUMNAS_DEVOLUCION if c in df_b.columns]], use_container_width=True)

st.write("")

if st.button("Generar Reporte", type="primary"):
    if canal == "Shopify" and not STORES:
        st.error("Credenciales de Shopify no configuradas en st.secrets.")
    elif len(date_range) != 2:
        st.warning("Seleccioná fecha de inicio y fin.")
    elif not selected_brands:
        st.warning("Seleccioná al menos una marca.")
    else:
        start_date, end_date = date_range
        all_data = []
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

                    st.caption(
                        f"🔍 {marca}: {len(raw_rows)} objetos descargados del bulk, "
                        f"{len(orders)} pedidos reconocidos, {len(processed_rows)} filas generadas."
                    )
                except RuntimeError as e:
                    st.error(f"{marca}: error durante la exportación — {e}")

                progress_bar.progress((i + 1) / len(selected_brands))

        else:  # MercadoLibre
            for i, marca in enumerate(selected_brands):
                try:
                    status_placeholder.text(f"{marca}: verificando token...")
                    if tipo_meli == "Ventas":
                        ordenes, filas = generar_meli(marca, start_date, end_date, status_placeholder)
                        st.caption(f"🔍 {marca}: {len(ordenes)} órdenes, {len(filas)} filas generadas.")
                    elif tipo_meli == "Devoluciones":
                        reclamos, filas = generar_devoluciones(marca, start_date, end_date, status_placeholder,
                                                               campo=campo_dev)
                        st.caption(f"🔍 {marca}: {len(reclamos)} reclamos revisados, {len(filas)} filas de devolución.")
                    else:
                        candidatas, filas = generar_cancelados(marca, start_date, end_date, status_placeholder)
                        st.caption(f"🔍 {marca}: {len(candidatas)} órdenes revisadas, {len(filas)} filas canceladas / no entregadas.")
                    all_data.extend(filas)
                except Exception as e:
                    st.error(f"{marca}: error durante la exportación — {e}")

                progress_bar.progress((i + 1) / len(selected_brands))

        progress_bar.empty()
        status_placeholder.empty()

        if all_data:
            df = pd.DataFrame(all_data)
            if canal == "Shopify":
                descargar_excel(df, "Ventas", f"Reporte_{start_date}_al_{end_date}.xlsx", start_time)
            elif tipo_meli == "Ventas":
                df = df.drop(columns=["_item_id", "_unit_price"], errors="ignore")
                descargar_excel(df, "Ventas MeLi", f"Reporte_MeLi_{start_date}_al_{end_date}.xlsx", start_time)
            elif tipo_meli == "Devoluciones":
                df = df[[c for c in COLUMNAS_DEVOLUCION if c in df.columns]]
                descargar_excel(df, "Devoluciones MeLi",
                                f"Devoluciones_MeLi_{start_date}_al_{end_date}.xlsx", start_time)
            else:
                df = df[[c for c in COLUMNAS_CANCELADOS if c in df.columns]]
                descargar_excel(df, "Cancelados MeLi",
                                f"Cancelados_NoEntregados_MeLi_{start_date}_al_{end_date}.xlsx", start_time)
        else:
            que = "ventas"
            if canal == "MercadoLibre" and tipo_meli == "Devoluciones":
                que = "devoluciones"
            elif canal == "MercadoLibre" and tipo_meli != "Ventas":
                que = "cancelaciones ni envíos no entregados"
            st.info(f"No se registraron {que} en el período seleccionado.")
