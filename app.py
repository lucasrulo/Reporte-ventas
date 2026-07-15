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
    """Consulta la API de productos para obtener los tags."""
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
    """Aplana el JSON y añade estados precisos de Shopify."""
    rows = []
    for order in orders:
        created_at = datetime.fromisoformat(order["created_at"].replace("Z", "+00:00"))
        
        # --- Lógica de Estados ---
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

        customer = order.get("customer", {})
        nombre_apellido = f"{customer.get('first_name', '')} {customer.get('last_name', '')}".strip()
        email = order.get("email", "") or order.get("contact_email", "")
        
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
                "SKU": line.get("sku", ""),
                "TAGS PRODUCTO": tags_producto,
                "MODELO / COLOR": line.get("variant_title", ""),
                "ESTADO CANCELACION": estado_cancelacion,
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

if st.button("Generar Reporte", type="primary"):
    if len(date_range) != 2:
        st.warning("Seleccioná fecha de inicio y fin.")
    elif not selected_brands:
        st.warning("Seleccioná al menos una marca.")
    else:
        start_date, end_date = date_range
        all_data = []
        product_cache = {}
        
        progress_bar = st.progress(0)
        for i, marca in enumerate(selected_brands):
            raw_orders = fetch_orders(STORES[marca], start_date, end_date)
            all_data.extend(process_orders(raw_orders, marca, STORES[marca], product_cache))
            progress_bar.progress((i + 1) / len(selected_brands))
            
        progress_bar.empty()
        
        if all_data:
            df = pd.DataFrame(all_data)
            output = io.BytesIO()
            with pd.ExcelWriter(output, engine='openpyxl') as writer:
                df.to_excel(writer, index=False, sheet_name='Ventas')
            
            st.success("Reporte generado.")
            st.download_button("Descargar Archivo", data=output.getvalue(), file_name="Reporte_Ventas.xlsx")
        else:
            st.info("No hay ventas en el período.")
