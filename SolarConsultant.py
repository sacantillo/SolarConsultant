import streamlit as st
import folium, math
from streamlit_folium import st_folium
from geopy.geocoders import Nominatim
import googlemaps
import datetime
from pynasapower.get_data import query_power
from pynasapower.geometry import point, bbox
import pandas as pd

def carga_paneles():
    paneles = {
        "JAM72D40 - 590/LB": {"Pmax":590, "Vmp": 43.4, "Imp":13.59, "Voc":52,
                              "Isc":14.35, "Area":2.65, "Altura":2.333, "Base":1.134,
                              "Ancho":0.03, "Degradacion":0.004,"Peso":32.5 },
    }
    return paneles

def carga_inversores():
    inversores = {
        "S5-GC60K-LV": {"VmaxMPP":1000, "VminMPP": 180, "Vnom":450, "PmaxWp":60,
                        "Pmax_kWp":60, "Vstart": 195, "NinMPPT":450, "Peso":89,
                        "ImaxMPPT": 256, "ImaxCC":320, "Poutmax":60000, "FPot":0.99,
                        "Freq":60, "Inomout": 157.5, "Ioutmax":157.5, "VnomAC":220}
    }
    return inversores

def geocode_address(address):
    gmaps = googlemaps.Client(key=st.secrets["API_KEY"])
    location = gmaps.geocode(address)
    if location:
        return location[0]['geometry']['location']['lat'], location[0]['geometry']['location']['lng']
    else:
        return None, None

def HSP(lat, lon):
    if lat is None and lon is None:
        st.warning("Ingrese la ubicación a revisar")
        return 0, 0, 0
    else:
        lat = float(lat)
        lon = float(lon)

        gpoint = point(lon, lat, "EPSG:4326")
        start = datetime.date(2023, 1, 1)
        end = datetime.date(2023, 12, 31)
        data = query_power(gpoint, start, end, True, "", "re", [], "daily", "point", "csv")
        data_MO = data[['ALLSKY_SFC_SW_DWN', 'MO']].groupby("MO")
        HSP_data = data_MO.describe()
        HSP_year_min = HSP_data[[('ALLSKY_SFC_SW_DWN', 'min')]].mean(axis=0)
        HSP_year_mean = HSP_data[[('ALLSKY_SFC_SW_DWN', 'mean')]].mean(axis=0)
        HSP_year_max = HSP_data[[('ALLSKY_SFC_SW_DWN', 'max')]].mean(axis=0)
        return HSP_year_min.values[0], HSP_year_mean.values[0], HSP_year_max.values[0]

def consumo_diario(consumo):
    prom = consumo["Consumo Pot. Activa (kWh)"].mean().round()/30
    return prom

def app():
    st.set_page_config(page_title="PV Consulter", layout="wide")
    st.title("Información Instalación SSFV")

    # Inicializar el mapa y las coordenadas en el estado de sesión si no existen
    if "map" not in st.session_state:
        st.session_state.map = folium.Map(location=[4.5709, -74.2973], zoom_start=6, control_scale=False, dragging=False, zoom_control=False)
    if "lat" not in st.session_state:
        st.session_state.lat = None  # Latitud inicial en Colombia
    if "lon" not in st.session_state:
        st.session_state.lon = None  # Longitud inicial en Colombia
    if "consumos_df" not in st.session_state:
        st.session_state.consumos_df = pd.DataFrame(columns=["Consumo Pot. Activa (kWh)"])

    with st.container(border=True):
        st.markdown('<h3 style="font-size: 16px;">Ubicación:</h3>', unsafe_allow_html=True)
        ca, cb = st.columns([3, 1])
        with ca:
            address = st.text_input("Dirección:",label_visibility="collapsed")
        with cb:
            buscar = st.button("Buscar", use_container_width=True)

    #st.markdown("<br>", unsafe_allow_html=True)
    if buscar:
        lat, lon = geocode_address(address)
        if lat and lon:
            st.session_state.lat = lat
            st.session_state.lon = lon
            # Crear un nuevo mapa centrado en la ubicación buscada
            st.session_state.map = folium.Map(location=[lat, lon], zoom_start=17, control_scale=False, dragging=False, zoom_control=False)
            folium.Marker([lat, lon], popup=address).add_to(st.session_state.map)
        else:
            st.warning("No se pudo encontrar la ubicación")

    min, med, max = HSP(st.session_state.lat,st.session_state.lon)

    with st.container(border=True):
         c1, c2 = st.columns([1, 4])
         with c2:
            st_folium(st.session_state.map, width=800, height=400)
         with c1:
            st.metric("HSP (max):", round(max,2))
            st.metric("HSP:", round(med,2))
            st.metric("HSP (min):", round(min,2))

    consumo = st.sidebar.text_input("Consumo (kWh)",key='consumo_input')

    if st.sidebar.button("Agregar Consumo",use_container_width=True):
      try:
      # Convertir el consumo a un valor numérico antes de agregar
        consumo_valor = float(consumo)
        # Agregar el valor como una nueva fila al DataFrame
        st.session_state.consumos_df = pd.concat([st.session_state.consumos_df, pd.DataFrame([[consumo_valor]], columns=["Consumo Pot. Activa (kWh)"])], ignore_index=True)
        st.sidebar.success("Valor de consumo agregado correctamente.")
      except ValueError:
        st.sidebar.warning("Por favor, ingresa un valor numérico válido.")

    st.sidebar.write("Histórico de Consumos:")
    st.sidebar.dataframe(st.session_state.consumos_df,use_container_width=True)
    if not st.session_state.consumos_df.empty:
      cons_prom = consumo_diario(st.session_state.consumos_df)
      with c1:
        st.metric("Consumo diario (kWh):", round(cons_prom,2))
    else:
      cons_prom = 0
    inyeccion = st.sidebar.slider('Inyección a la red (%)', 0, 100, 100)/100
    consumoHSP = st.sidebar.slider('Consumo en HSP (%)', 0, 100, 100)/100

    opciones = {"Mínimo": min, "Medio": med, "Máximo": max}
    # Selectbox con los nombres visibles
    escenario_seleccionado = st.selectbox('Seleccione escenario', list(opciones.keys()), index=0)
    escenario = opciones[escenario_seleccionado]
    with st.container(border=True):
      c3, c4 = st.columns([1,3])
      if escenario != 0:
        pot_pico = cons_prom*inyeccion/escenario
        c3.metric("Potencia pico a instalar (kWp):", round(cons_prom*consumoHSP*inyeccion/round(escenario,2),1))
        paneles = carga_paneles()
        panel_selec = c4.selectbox("Seleccione un panel", list(paneles.keys()))
        valores = paneles[panel_selec]
        c5, c6, c7= st.columns(3)
        paneles_f1 = 1000*pot_pico/valores['Pmax']
        c5.metric("Paneles a instalar:", round(1000*round(cons_prom*inyeccion/round(escenario,2),1)/valores['Pmax'],1))
        gen_mensual = round(valores['Pmax']*escenario*paneles_f1*30/1e6,1)
        c6.metric("Generación Mensual (MWh):",gen_mensual, str(round(-0.367*gen_mensual,2))+" Ton CO2/MWh",delta_color="inverse")
        c7.metric("Consumo Perfil de Carga (kWh):",round(cons_prom*consumoHSP,1))

    with st.container(border=True):
        st.markdown('<h3 style="font-size: 16px;">Área disponible (m<sup style=font-size:.8em;>2 </sup>) :</h3>', unsafe_allow_html=True)
        cc, cd = st.columns([3, 1])
        with cc:
            area = st.text_input("",label_visibility="collapsed")
        with cd:
            calc_PSFV = st.button("Calcular", use_container_width=True)

        if calc_PSFV:
            c8, c9, c10, c11 = st.columns(4)
            cant_pan_teo = float(area)/valores['Area']
            c8.metric("Cantidad Teórica de Paneles:", round(cant_pan_teo,2))
            area_capt = cant_pan_teo*valores['Area']
            c9.metric("Área de Captación ($m^{2})$:", round(area_capt,1))
            inclinacion = round(3.7 + (0.69 * st.session_state.lat + 4),0)
            c10.metric("Inclinación Optima (°):",inclinacion)
            dist_pan = 0.21/(math.atan(61 - st.session_state.lat))
            c11.metric("Distancia entre paneles (m):",round(dist_pan,2))

if __name__ == "__main__":
    app()
