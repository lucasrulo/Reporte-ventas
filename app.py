import streamlit as st
import requests
import pandas as pd
from datetime import datetime, time
import io

# Configuración de la página
st.set_page_config(page_title="Consolidador de Ventas Multimarca", layout="wide")

# Mapeo dinámico de credenciales desde st.secrets
try:
    STORES = st.secrets["stores"]
except KeyError:
    st.error("No se encontraron las credenciales en st.secrets. Por favor, verifica la configuración.")
    st.stop()

def fetch_orders(store_info, start_date, end_date):
    """Obtiene los pedidos de la API de Shopify manejando la paginación."""
    api_version = "2024-01"
    headers = {"X-Shopify-Access-Token": store_info["token"]}
    
    # Formatear fechas para la API (ISO 8601 con zona horaria de Argentina -03:00)
    start_str = datetime.combine(start_date, time.min).isoformat() + "-03:00"
    end_str = datetime.combine(end_date, time.max).isoformat() + "-03:00"

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
            
            # Revisar si hay una página siguiente (Paginación de Shopify)
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
    """Aplana el JSON de Shopify para crear las filas del reporte a nivel de SKU."""
    rows = []
    for order in orders:
        created_at = datetime.fromisoformat(order["created_at"].replace("Z", "+00:00"))
        
        shipping_address = order.get("shipping_address", {})
        provincia = shipping_address.get("province", "") if shipping_address else ""
        
        gateways = ", ".join(order.get("payment_gateway_names", []))
        
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
                "METODO DE PAGO": gateways
            }
            rows.append(row)
    return rows

# --- Interfaz de Usuario de Streamlit ---
st.title("📦 Extractor Multimarca de Ventas Shopify")
st.markdown("Descargá el reporte consolidado de pedidos para todas las marcas seleccionadas.")

# Filtros
col1, col2 = st.columns(2)
with col1:
    date_range = st.date_input("Rango de Fechas", [])
with col2:
    # Toma las marcas disponibles dinámicamente desde lo configurado en los secrets
    available_brands = list(STORES.keys())
    selected_brands = st.multiselect("Marcas a extraer", available_brands, default=available_brands)

if st.button("Generar Reporte", type="primary"):
    if len(date_range) != 2:
        st.warning("Por favor selecciona una fecha de inicio y una fecha de fin.")
    elif not selected_brands:
        st.warning("Por favor selecciona al menos una marca.")
    else:
        start_date, end_date = date_range
        all_data = []
        
        progress_bar = st.progress(0)
        status_text = st.empty()
        
        for i, marca in enumerate(selected_brands):
            status_text.text(f"Extrayendo datos de {marca}...")
            raw_orders = fetch_orders(STORES[marca], start_date, end_date)
            processed_rows = process_orders(raw_orders, marca)
            all_data.extend(processed_rows)
            
            progress_bar.progress((i + 1) / len(selected_brands))
            
        status_text.text("¡Extracción completada!")
        
        if all_data:
            df = pd.DataFrame(all_data)
            
            st.subheader("Vista previa de los datos")
            st.dataframe(df.head(100), use_container_width=True)
            
            output = io.BytesIO()
            with pd.ExcelWriter(output, engine='openpyxl') as writer:
                df.to_excel(writer, index=False, sheet_name='Reporte Ventas')
            processed_data = output.getvalue()
            
            st.download_button(
                label="📥 Descargar Reporte en Excel (.xlsx)",
                data=processed_data,
                file_name=f"Reporte_Ventas_{start_date}_al_{end_date}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )
        else:
            st.info("No se encontraron pedidos en el rango de fechas seleccionado para estas marcas.")
