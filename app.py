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

def process_orders(orders, marca):
    """Aplana el JSON y consolida los métodos de pago."""
    rows = []
    for order in orders:
        created_at = datetime.fromisoformat(order["created_at"].replace("Z", "+00:00"))
        shipping_address = order.get("shipping_address", {})
        provincia = shipping_address.get("province", "") if shipping_address else ""
        
        # 2. Lógica de consolidación de métodos de pago
        gateways_raw = ", ".join(order.get("payment_gateway_names", [])).lower()
        if "mercado" in gateways_raw or "mercadopago" in gateways_raw:
            metodo_pago = "Mercado Pago"
        elif "mobbex" in gateways_raw:
            metodo_pago = "Mobbex"
        elif "reversso" in gateways_raw:
            metodo_pago = "Reversso"
        else:
            # Fallback en caso de que sea otro método (ej: Transferencia, Custom)
            metodo_pago = ", ".join(order.get("payment_gateway_names", [])).title()
        
        for line in order.get("line_items", []):
            row = {
                "MARCA": marca,
                "PEDIDO": order.get("name", ""),
                "FECHA": created_at.strftime("%d/%m/%Y"),
                "HORA": created_at.strftime("%H:%M:%S"),
                "PROVINCIA": provincia,
                "SKU": line.get("sku", ""),
                "MODELO / COLOR": line.get("variant_title", ""),
                "DESCRIPCION": line.get("title", ""),
                "CANTIDAD": line.get("quantity", 0),
                "PRECIO UNITARIO": float(line.get("price", 0.00)),
                "TOTAL PEDIDO": float(order.get("total_price", 0.00)),
                "ESTADO DEL PAGO": order.get("financial_status", ""),
                "ESTADO": order.get("fulfillment_status", "unfulfilled") or "unfulfilled",
                "ENVIO": order.get("shipping_lines", [{}])[0].get("title", "") if order.get("shipping_lines") else "",
                "METODO DE PAGO": metodo_pago
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

st.write("") # Espaciador

if st.button("Generar Reporte", type="primary"):
    if len(date_range) != 2:
        st.warning("Seleccioná fecha de inicio y fin.")
    elif not selected_brands:
        st.warning("Seleccioná al menos una marca.")
    else:
        start_date, end_date = date_range
        all_data = []
        
        # 3. Inicio del cronómetro
        start_time = time_lib.time()
        
        progress_bar = st.progress(0)
        
        for i, marca in enumerate(selected_brands):
            raw_orders = fetch_orders(STORES[marca], start_date, end_date)
            processed_rows = process_orders(raw_orders, marca)
            all_data.extend(processed_rows)
            progress_bar.progress((i + 1) / len(selected_brands))
            
        # Fin del cronómetro
        end_time = time_lib.time()
        elapsed_time = round(end_time - start_time, 2)
        
        # Limpiar barra de progreso para mantener diseño limpio
        progress_bar.empty()
        
        if all_data:
            df = pd.DataFrame(all_data)
            
            output = io.BytesIO()
            with pd.ExcelWriter(output, engine='openpyxl') as writer:
                df.to_excel(writer, index=False, sheet_name='Ventas')
            processed_data = output.getvalue()
            
            # Mensaje de éxito limpio con el tiempo de ejecución
            st.success(f"Reporte procesado exitosamente en {elapsed_time} segundos.")
            
            # Vista previa contenida en un expander para no saturar la pantalla
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
