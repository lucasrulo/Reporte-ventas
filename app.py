import streamlit as st
import requests
import pandas as pd
from datetime import datetime
import time as time_lib
import io

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

def fetch_orders(store_info, start_date, end_date):
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
                    response = requests.get(next_url, headers=headers)
                else:
                    break
            else:
                break
                
    except Exception as e:
        st.error(f"Error conectando con {store_info['url']}: {e}")
        
    return all_orders

def get_product_tags(product_id, store_info, cache):
    """Consulta la API de productos para obtener los tags. Usa caché para optimizar velocidad."""
    if not product_id:
        return ""
    
    if product_id in cache:
        return cache[product_id]
        
    api_version = "2024-01"
    url = f"https://{store_info['url']}/admin/api/{api_version}/products/{product_id}.json?fields=tags"
    headers = {"X-Shopify-Access-Token": store_info["token"]}
    
    try:
        response = requests.get(url, headers=headers)
        if response.status_code == 200:
            tags = response.json().get("product", {}).get("tags", "")
            cache[product_id] = tags
            return tags
        elif response.status_code == 429:
            time_lib.sleep(1)
            return get_product_tags(product_id, store_info, cache)
        else:
            cache[product_id] = ""
            return ""
    except Exception:
        cache[product_id] = ""
        return ""

def process_orders(orders, marca, store_info, product_cache):
    """Aplana el JSON, consolida los métodos de pago y suma datos del cliente y tags."""
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
        
        # Lógica de estado de preparación
        fulfillment_status = order.get("fulfillment_status")
        if fulfillment_status == "fulfilled":
            estado_preparacion = "Preparado"
        elif fulfillment_status == "partial":
            estado_preparacion = "Preparación Parcial"
        else:
            estado_preparacion = "No preparado"
        
        for line in order.get("line_items", []):
            product_id = line.get("product_id")
            tags_producto = get_product_tags(product_id, store_info, product_cache)
            
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
                "ESTADO PREPARACION": estado_preparacion
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

st.write("") 

if st.button("Generar Reporte", type="primary"):
    if len(date_range) != 2:
        st.warning("Seleccioná fecha de inicio y fin.")
    elif not selected_brands:
        st.warning("Seleccioná al menos una marca.")
    else:
        start_date, end_date = date_range
        all_data = []
        product_cache = {}
        
        start_time = time_lib.time()
        
        st.info("Obteniendo pedidos y consultando etiquetas de productos. Esto puede demorar un poco más...")
        progress_bar = st.progress(0)
        
        for i, marca in enumerate(selected_brands):
            raw_orders = fetch_orders(STORES[marca], start_date, end_date)
            processed_rows = process_orders(raw_orders, marca, STORES[marca], product_cache)
            all_data.extend(processed_rows)
            progress_bar.progress((i + 1) / len(selected_brands))
            
        end_time = time_lib.time()
        elapsed_time = round(end_time - start_time, 2)
        
        progress_bar.empty()
        
        if all_data:
            df = pd.DataFrame(all_data)
            
            output = io.BytesIO()
            with pd.ExcelWriter(output, engine='openpyxl') as writer:
                df.to_excel(writer, index=False, sheet_name='Ventas')
            processed_data = output.getvalue()
            
            st.success(f"Reporte procesado exitosamente en {elapsed_time} segundos.")
            
            with st.expander("Ver vista previa de los datos"):
                st.dataframe(df.head(50), use_container_width=True)
            
            st.download_button(
                label="Descargar Archivo",
                data=processed_data,
                file_name=f"Reporte_{start_date}_al_{end_date}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )
        else:
            st.info("No se registraron ventas en el período seleccionado.")
