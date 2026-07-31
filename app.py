import streamlit as st
import requests
import pandas as pd
from datetime import datetime
import time as time_lib
import io
import json

# 1. Configuración Minimalista de la página
st.set_page_config(page_title="Descarga ventas Shopify", layout="centered")

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
except KeyError:
    st.error("Credenciales no configuradas en st.secrets.")
    st.stop()

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
        elif "LineItem" in node_id:
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


# --- Interfaz de Usuario ---
st.title("Consolidador Shopify")
st.write("---")

col1, col2 = st.columns(2)
with col1:
    date_range = st.date_input("Rango de Fechas", [])
with col2:
    available_brands = list(STORES.keys())
    selected_brands = st.multiselect("Marcas", available_brands, default=available_brands)

st.write("")

if st.button("Generar Reporte", type="primary"):
    if len(date_range) != 2:
        st.warning("Seleccioná fecha de inicio y fin.")
    elif not selected_brands:
        st.warning("Seleccioná al menos una marca.")
    else:
        start_date, end_date = date_range
        all_data = []

        start_str = datetime.combine(start_date, datetime.min.time()).isoformat() + "-03:00"
        end_str = datetime.combine(end_date, datetime.max.time()).isoformat() + "-03:00"

        start_time = time_lib.time()
        progress_bar = st.progress(0)
        status_placeholder = st.empty()

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

        progress_bar.empty()
        status_placeholder.empty()

        if all_data:
            df = pd.DataFrame(all_data)
            output = io.BytesIO()
            with pd.ExcelWriter(output, engine='openpyxl') as writer:
                df.to_excel(writer, index=False, sheet_name='Ventas')

            elapsed = time_lib.time() - start_time
            st.success(f"Reporte procesado en {elapsed:.0f} segundos.")

            with st.expander("Ver vista previa"):
                st.dataframe(df.head(50), use_container_width=True)

            st.download_button(
                label="Descargar Archivo",
                data=output.getvalue(),
                file_name=f"Reporte_{start_date}_al_{end_date}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )
        else:
            st.info("No se registraron ventas en el período seleccionado.")
