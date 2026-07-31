import streamlit as st
import requests
import pandas as pd
from datetime import datetime
import time as time_lib
import io
import threading
import concurrent.futures

# 1. Configuración Minimalista de la página
st.set_page_config(page_title="Descarga ventas Shopify", layout="centered")

# CSS para ocultar elementos por defecto de Streamlit y dar aspecto limpio
hide_st_style = """
            <style>
            #MainMenu {visibility: hidden;}
            footer {visibility: hidden;}
            header {visibility: hidden;}
            .stButton>button {width: 100%; border-radius: 4px;}
            </style>
            """
st.markdown(hide_st_style, unsafe_allow_html=True)

# Mapeo dinámico de credenciales desde st.secrets
try:
    STORES = st.secrets["stores"]
except KeyError:
    st.error("Credenciales no configuradas en st.secrets.")
    st.stop()


class RateLimiter:
    """
    Limita la cantidad de llamados por segundo a la API de una tienda para
    evitar disparar el rate limit de Shopify (lo que generaba muchos 429
    y reintentos de 1 segundo en cascada, haciendo el reporte eterno).
    """
    def __init__(self, min_interval=0.55):
        self.min_interval = min_interval
        self.lock = threading.Lock()
        self.last_call = 0.0

    def wait(self):
        with self.lock:
            now = time_lib.time()
            elapsed = now - self.last_call
            if elapsed < self.min_interval:
                time_lib.sleep(self.min_interval - elapsed)
            self.last_call = time_lib.time()


def fetch_orders(store_info, start_date, end_date, rate_limiter):
    """Obtiene los pedidos de la API de Shopify manejando la paginación."""
    api_version = "2024-01"
    headers = {"X-Shopify-Access-Token": store_info["token"]}
    
    start_str = datetime.combine(start_date, datetime.min.time()).isoformat() + "-03:00"
    end_str = datetime.combine(end_date, datetime.max.time()).isoformat() + "-03:00"

    url = f"https://{store_info['url']}/admin/api/{api_version}/orders.json"
    params = {
        "created_at_min": start_str,
        "created_at_max": end_str,
        "status": "any",
        "limit": 250
    }

    all_orders = []
    
    try:
        rate_limiter.wait()
        response = requests.get(url, headers=headers, params=params)
        response.raise_for_status()
        
        while response.status_code == 200:
            data = response.json()
            all_orders.extend(data.get("orders", []))
            
            link_header = response.headers.get("Link")
            if link_header and 'rel="next"' in link_header:
                links = link_header.split(', ')
                next_link = [link for link in links if 'rel="next"' in link]
                if next_link:
                    next_url = next_link[0].split(';')[0].strip('<>')
                    rate_limiter.wait()
                    response = requests.get(next_url, headers=headers)
                else:
                    break
            else:
                break
                
    except Exception as e:
        st.error(f"Error conectando con {store_info['url']}: {e}")
        
    return all_orders


def get_product_tags(product_id, store_info, rate_limiter):
    """Consulta la API de productos para obtener los tags de un producto puntual."""
    if not product_id:
        return product_id, ""

    api_version = "2024-01"
    url = f"https://{store_info['url']}/admin/api/{api_version}/products/{product_id}.json?fields=tags"
    headers = {"X-Shopify-Access-Token": store_info["token"]}

    for intento in range(4):
        rate_limiter.wait()
        try:
            response = requests.get(url, headers=headers)
            if response.status_code == 200:
                tags = response.json().get("product", {}).get("tags", "")
                return product_id, tags
            elif response.status_code == 429:
                espera = float(response.headers.get("Retry-After", 1))
                time_lib.sleep(espera)
                continue
            else:
                return product_id, ""
        except Exception:
            return product_id, ""
    return product_id, ""


def get_payment_id(order_id, store_info, rate_limiter):
    """
    Consulta la API de transacciones del pedido para obtener el 'ID de pago'
    que se ve en el timeline de Shopify (ej: para Mobbex o Mercado Pago).

    Ese ID no viene en un campo estándar único: según la pasarela, puede
    estar en 'authorization' o dentro del diccionario 'receipt' con distintas
    claves. Probamos las más comunes en orden de prioridad.
    """
    if not order_id:
        return order_id, ""

    api_version = "2024-01"
    url = f"https://{store_info['url']}/admin/api/{api_version}/orders/{order_id}/transactions.json"
    headers = {"X-Shopify-Access-Token": store_info["token"]}

    for intento in range(4):
        rate_limiter.wait()
        try:
            response = requests.get(url, headers=headers)
            if response.status_code == 200:
                transactions = response.json().get("transactions", [])

                candidatas = [
                    t for t in transactions
                    if t.get("status") == "success" and t.get("kind") in ("sale", "capture")
                ]
                if not candidatas:
                    candidatas = transactions  # fallback: cualquier transacción

                for t in candidatas:
                    receipt = t.get("receipt") or {}
                    payment_id = (
                        t.get("authorization")
                        or receipt.get("id")
                        or receipt.get("payment_id")
                        or receipt.get("gateway_transaction_id")
                        or receipt.get("transaction_id")
                        or ""
                    )
                    if payment_id:
                        return order_id, payment_id
                return order_id, ""
            elif response.status_code == 429:
                espera = float(response.headers.get("Retry-After", 1))
                time_lib.sleep(espera)
                continue
            else:
                return order_id, ""
        except Exception:
            return order_id, ""
    return order_id, ""


def fetch_concurrently(items, worker_fn, store_info, rate_limiter, status_placeholder, label, max_workers=4):
    """
    Ejecuta worker_fn(item, store_info, rate_limiter) en paralelo para una lista
    de items, mostrando progreso en vivo. worker_fn debe devolver (clave, valor).
    Devuelve un diccionario {clave: valor}.
    """
    results = {}
    total = len(items)
    if total == 0:
        return results

    completado = 0
    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = [executor.submit(worker_fn, item, store_info, rate_limiter) for item in items]
        for future in concurrent.futures.as_completed(futures):
            clave, valor = future.result()
            results[clave] = valor
            completado += 1
            if completado % 5 == 0 or completado == total:
                status_placeholder.text(f"{label}: {completado}/{total}")

    return results


def process_orders(orders, marca, product_tags_cache, payment_ids_cache):
    """Aplana el JSON y arma cada fila usando los caches ya resueltos (sin llamadas a la API)."""
    rows = []
    for order in orders:
        created_at = datetime.fromisoformat(order["created_at"].replace("Z", "+00:00"))
        shipping_address = order.get("shipping_address", {})
        provincia = shipping_address.get("province", "") if shipping_address else ""
        
        customer = order.get("customer", {})
        nombre_cliente = customer.get("first_name", "") or ""
        apellido_cliente = customer.get("last_name", "") or ""
        nombre_apellido = f"{nombre_cliente} {apellido_cliente}".strip()
        email = order.get("email", "") or order.get("contact_email", "")
        
        gateways_raw = ", ".join(order.get("payment_gateway_names", [])).lower()
        if "mercado" in gateways_raw or "mercadopago" in gateways_raw:
            metodo_pago = "Mercado Pago"
        elif "mobbex" in gateways_raw:
            metodo_pago = "Mobbex"
        elif "reversso" in gateways_raw:
            metodo_pago = "Reversso"
        else:
            metodo_pago = ", ".join(order.get("payment_gateway_names", [])).title()
        
        # --- Lógica de estados nuevos ---
        estado_cancelacion = "Cancelado" if order.get("cancelled_at") else "Activo"
        
        fulfillment_status = order.get("fulfillment_status")
        if fulfillment_status == "fulfilled":
            estado_preparacion = "Preparado"
        elif fulfillment_status == "partial":
            estado_preparacion = "Preparación Parcial"
        elif fulfillment_status is None:
            estado_preparacion = "No requiere preparación" 
        else:
            estado_preparacion = fulfillment_status.replace("_", " ").title()

        id_pago = payment_ids_cache.get(order.get("id"), "")
        
        for line in order.get("line_items", []):
            product_id = line.get("product_id")
            tags_producto = product_tags_cache.get(product_id, "")
            
            row = {
                "NOMBRE Y APELLIDO": nombre_apellido,
                "EMAIL": email,
                "MARCA": marca,
                "PEDIDO": order.get("name", ""),
                "FECHA": created_at.strftime("%d/%m/%Y"),
                "HORA": created_at.strftime("%H:%M:%S"),
                "PROVINCIA": provincia,
                "SKU": line.get("sku", ""),
                "TAGS PRODUCTO": tags_producto,
                "MODELO / COLOR": line.get("variant_title", ""),
                "DESCRIPCION": line.get("title", ""),
                "CANTIDAD": line.get("quantity", 0),
                "PRECIO UNITARIO": float(line.get("price", 0.00)),
                "TOTAL PEDIDO": float(order.get("total_price", 0.00)),
                "ESTADO DEL PAGO": order.get("financial_status", ""),
                "ESTADO": order.get("fulfillment_status", "unfulfilled") or "unfulfilled",
                "ENVIO": order.get("shipping_lines", [{}])[0].get("title", "") if order.get("shipping_lines") else "",
                "METODO DE PAGO": metodo_pago,
                "ESTADO CANCELACION": estado_cancelacion,
                "ESTADO PREPARACION": estado_preparacion,
                "ID DE PAGO": id_pago
            }
            rows.append(row)
    return rows

# --- Interfaz de Usuario ---
st.title("Consolidador Shopify")
st.write("---")

col1, col2 = st.columns(2)
with col1:
    date_range = st.date_input("Rango de Fechas", [])
with col2:
    available_brands = list(STORES.keys())
    selected_brands = st.multiselect("Marcas", available_brands, default=available_brands)

incluir_pago = st.checkbox("Incluir ID de pago (agrega una llamada extra por pedido, más lento)", value=True)

st.write("") 

if st.button("Generar Reporte", type="primary"):
    if len(date_range) != 2:
        st.warning("Seleccioná fecha de inicio y fin.")
    elif not selected_brands:
        st.warning("Seleccioná al menos una marca.")
    else:
        start_date, end_date = date_range
        all_data = []
        
        start_time = time_lib.time()
        progress_bar = st.progress(0)
        status_placeholder = st.empty()
        
        for i, marca in enumerate(selected_brands):
            store_info = STORES[marca]
            rate_limiter = RateLimiter()

            status_placeholder.text(f"{marca}: descargando pedidos...")
            raw_orders = fetch_orders(store_info, start_date, end_date, rate_limiter)

            # IDs de producto únicos para no pedir tags repetidos
            product_ids = list({
                line.get("product_id")
                for order in raw_orders
                for line in order.get("line_items", [])
                if line.get("product_id")
            })
            product_tags_cache = fetch_concurrently(
                product_ids, get_product_tags, store_info, rate_limiter,
                status_placeholder, f"{marca}: obteniendo tags de productos"
            )

            payment_ids_cache = {}
            if incluir_pago:
                order_ids = [o.get("id") for o in raw_orders if o.get("id")]
                payment_ids_cache = fetch_concurrently(
                    order_ids, get_payment_id, store_info, rate_limiter,
                    status_placeholder, f"{marca}: obteniendo ID de pago"
                )

            processed_rows = process_orders(raw_orders, marca, product_tags_cache, payment_ids_cache)
            all_data.extend(processed_rows)
            progress_bar.progress((i + 1) / len(selected_brands))
            
        progress_bar.empty()
        status_placeholder.empty()
        
        if all_data:
            df = pd.DataFrame(all_data)
            output = io.BytesIO()
            with pd.ExcelWriter(output, engine='openpyxl') as writer:
                df.to_excel(writer, index=False, sheet_name='Ventas')
            
            elapsed = time_lib.time() - start_time
            st.success(f"Reporte procesado en {elapsed/60:.1f} minutos.")
            
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
