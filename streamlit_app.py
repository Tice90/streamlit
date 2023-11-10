import requests
import pandas as pd
import cbsodata
import geopandas as gpd
import folium
import folium.plugins
from folium.features import GeoJsonPopup
import streamlit as st
from streamlit_folium import st_folium

#Streamlit data laden
@st.cache_data
def load_data():
    # gdf = gpd.read_file('cbsgebiedsindelingen2021.gpkg', layer='gemeente_gegeneraliseerd_2021')
    # gdf2 = gpd.read_file('cbsgebiedsindelingen2021.gpkg', layer='buurt_gegeneraliseerd_2021')
    # gdf3 = gpd.read_file('cbsgebiedsindelingen2021.gpkg', layer='wijk_gegeneraliseerd_2021')
    # gdf = pd.concat([gdf, gdf2, gdf3], ignore_index=True)
    # gdf = gdf.to_crs(epsg=4326)
    gdf = gpd.read_file('geodata_cbs.geojson')
    gdf = gdf.to_crs(epsg=4326)
    CBS2021 = pd.DataFrame(cbsodata.get_data('85039NED'))
    CBS2021 = CBS2021[CBS2021['SoortRegio_2'] != 'Land']
    CBS2021['Codering_3'] = CBS2021['Codering_3'].str.strip()
    CBS2021['SoortRegio_2'] = CBS2021['SoortRegio_2'].str.strip()
    CBS2021 = CBS2021.merge(gdf, left_on='Codering_3', right_on='statcode', how='left')
    geo_df_crs = {'init' : 'epsg:4326'}
    CBS2021 = gpd.GeoDataFrame(CBS2021, crs = geo_df_crs, geometry = CBS2021.geometry)
    
    return CBS2021

@st.cache_data
def geo_ams():
    # De URL voor het GeoJSON endpoint
    url = "https://api.data.amsterdam.nl/v1/aardgasvrijezones/buurt/?_format=geojson"

    # Verstuur een GET-verzoek naar de URL
    response = requests.get(url)

    # Controleer of het verzoek succesvol was
    if response.status_code == 200:
        # Laad de GeoJSON data in een variabele
        geojson_data = response.json()
    else:
        print(f"Fout bij het ophalen van de data: {response.status_code}")

    Ams_gdf = gpd.GeoDataFrame.from_features(geojson_data['features'])

    Ams_gdf['centroid'] = Ams_gdf['geometry'].centroid
    Ams_gdf['centroid_x'] = Ams_gdf['centroid'].x
    Ams_gdf['centroid_y'] = Ams_gdf['centroid'].y

    # Filter de GeoDataFrame op de 'toelichting' kolom
    Ams_gdf = Ams_gdf[Ams_gdf['toelichting'].str.contains('All electric:|Al \(bijna\) volledig op het warmtenet', na=False)]

    return Ams_gdf


CBS2021 = load_data()

@st.cache_data
def prepare_geojson(CBS2021):
    # Filter en converteer het DataFrame voor elk regio type naar GeoJSON
    gemeente_gdf = CBS2021[CBS2021['SoortRegio_2'] == 'Gemeente']
    gemeente_geo_json = gemeente_gdf.to_json()
    
    wijk_gdf = CBS2021[CBS2021['SoortRegio_2'] == 'Wijk']
    wijk_geo_json = wijk_gdf.to_json()
    
    buurt_gdf = CBS2021[CBS2021['SoortRegio_2'] == 'Buurt']
    buurt_geo_json = buurt_gdf.to_json()
    
    return gemeente_geo_json, wijk_geo_json, buurt_geo_json

gemeente_geo_json, wijk_geo_json, buurt_geo_json = prepare_geojson(CBS2021)
Ams_gdf = geo_ams()

#-----------------------------------------------------------------------------------#

#Folium Map Aardgasverbruik

# Bepaal het centrum van je kaart
center = [52.0907, 5.1214]

@st.cache_data
def create_map():
    # Maak een Folium kaartobject
    m_gas = folium.Map(location=center, tiles='cartodb positron', zoom_start=7)

    # Functie om popup toe te voegen aan een laag
    def add_choropleth(geo_json_data, name, columns, fill_color, legend_name):
        layer = folium.Choropleth(
            geo_data=geo_json_data,
            name=name,
            data=CBS2021,
            columns=columns,
            key_on='properties.Codering_3',
            fill_color=fill_color,
            fill_opacity=0.7,
            line_opacity=0.2,
            legend_name=legend_name,
            highlight=True,
            overlay=True,
            show=(name == 'Gemeenten')  # Alleen de 'Gemeenten' laag standaard tonen
        )

        # Maak een pop-up voor de laag en voeg deze toe
        popup = GeoJsonPopup(
            fields=['statnaam', columns[1]],
            aliases=['Locatie: ', 'Gem. Aardgasverbruik: '],
            localize=True,
            labels=True,
            style="background-color: white;"
        )
        
        # Voeg de pop-up toe aan de geojson laag van de Choropleth
        layer.geojson.add_child(popup)
        
        # Voeg de Choropleth laag toe aan de kaart
        layer.add_to(m_gas)

    # Voeg de GeoJSON van gemeenten toe aan de kaart met tooltips
    add_choropleth(gemeente_geo_json, 'Gemeenten', ['Codering_3', 'GemiddeldAardgasverbruikTotaal_55'], 'YlOrRd', 'Gemiddeld Aardgasverbruik per Gemeente in 2021')

    # Voeg de GeoJSON van wijken toe aan de kaart met tooltips
    add_choropleth(wijk_geo_json, 'Wijken', ['Codering_3', 'GemiddeldAardgasverbruikTotaal_55'], 'BuGn', 'Gemiddeld Aardgasverbruik per Wijk in 2021')

    # Voeg de GeoJSON van buurten toe aan de kaart met tooltips
    add_choropleth(buurt_geo_json, 'Buurten', ['Codering_3', 'GemiddeldAardgasverbruikTotaal_55'], 'YlGnBu', 'Gemiddeld Aardgasverbruik per Buurt in 2021')


    # Maak een FeatureGroup voor de markers
    markers_layer = folium.FeatureGroup(name='Gasvrij', show=False)


    # Loop door de rijen in je GeoDataFrame
    for idx, row in Ams_gdf.iterrows():
        # Voeg een marker toe aan de markers_layer
        folium.Marker(
            location=[row['centroid_y'], row['centroid_x']],  # Gebruik de x- en y-coördinaten
            tooltip=str(row['toelichting']),  # Zet de inhoud van 'Toelichting' om naar een string en gebruik als tooltip
            popup=folium.Popup(str(row['toelichting']), max_width=450),  # Voeg eventueel een popup toe
            show=False
        ).add_to(markers_layer)

    # Voeg de markers_layer toe aan de kaart
    markers_layer.add_to(m_gas)

    # Volledig scherm
    folium.plugins.Fullscreen(
        position="topright",
        title="Volledig scherm",
        title_cancel="Sluiten",
        force_separate_button=True,
    ).add_to(m_gas)

    # Voeg een laag controle toe om de choropleth aan of uit te zetten
    folium.LayerControl().add_to(m_gas)
    return m_gas

m_gas = create_map()


# Toon de kaart
st_folium(m_gas, width=725, height=600)

#-----------------------------------------------------------------------------------#

#Folium Map Elektriciteit

@st.cache_data
def create_map2():
    # Maak een Folium kaartobject
    m_ele = folium.Map(location=center, tiles='cartodb positron', zoom_start=7)

    # Functie om popup toe te voegen aan een laag
    def add_choropleth(geo_json_data, name, columns, fill_color, legend_name):
        layer = folium.Choropleth(
            geo_data=geo_json_data,
            name=name,
            data=CBS2021,
            columns=columns,
            key_on='properties.Codering_3',
            fill_color=fill_color,
            fill_opacity=0.7,
            line_opacity=0.2,
            legend_name=legend_name,
            highlight=True,
            overlay=True,
            show=(name == 'Gemeenten')  # Alleen de 'Gemeenten' laag standaard tonen
        )

        # Maak een pop-up voor de laag en voeg deze toe
        popup = GeoJsonPopup(
            fields=['statnaam', columns[1]],
            aliases=['Locatie: ', 'Gem. Elektriciteitsverbruik: '],
            localize=True,
            labels=True,
            style="background-color: white;"
        )
        
        # Voeg de pop-up toe aan de geojson laag van de Choropleth
        layer.geojson.add_child(popup)
        
        # Voeg de Choropleth laag toe aan de kaart
        layer.add_to(m_ele)

    # Voeg de GeoJSON van gemeenten toe aan de kaart met tooltips
    add_choropleth(gemeente_geo_json, 'Gemeenten', ['Codering_3', 'GemiddeldElektriciteitsverbruikTotaal_47'], 'YlOrRd', 'Gemiddeld Elektriciteitsverbruik per Gemeente in 2021')

    # Voeg de GeoJSON van wijken toe aan de kaart met tooltips
    add_choropleth(wijk_geo_json, 'Wijken', ['Codering_3', 'GemiddeldElektriciteitsverbruikTotaal_47'], 'BuGn', 'Gemiddeld Elektriciteitsverbruik per Wijk in 2021')

    # Voeg de GeoJSON van buurten toe aan de kaart met tooltips
    add_choropleth(buurt_geo_json, 'Buurten', ['Codering_3', 'GemiddeldElektriciteitsverbruikTotaal_47'], 'YlGnBu', 'Gemiddeld Elektriciteitsverbruik per Buurt in 2021')

    # Volledig scherm
    folium.plugins.Fullscreen(
        position="topright",
        title="Volledig scherm",
        title_cancel="Sluiten",
        force_separate_button=True,
    ).add_to(m_ele)

    # Voeg een laag controle toe om de choropleth aan of uit te zetten
    folium.LayerControl().add_to(m_ele)
    return m_ele

m_ele = create_map2()



# Toon de kaart
st_folium(m_ele, width=725, height=600)
