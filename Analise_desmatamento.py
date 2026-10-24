import customtkinter as ctk
from tkintermapview import TkinterMapView
from geopy.geocoders import Nominatim
import ee
import folium
import webbrowser
import math
import os
from dotenv import load_dotenv
from pathlib import Path
from tkinter import messagebox
import traceback
from filtro_ruido import (
    PIXELS_MINIMOS, OBSERVACOES_MINIMAS,
    mascarar_nuvens_scl, pixels_com_observacoes_suficientes,
    remover_ruido_conectado, calcular_areas,
)

# =============== 1: Inicialização do Earth Engine ========================
# Carrega as variáveis do arquivo .env
load_dotenv()

# Obtém o ID do projeto a partir do .env
PROJECT_ID = os.getenv("GEE_PROJECT_ID")

if not PROJECT_ID:
    raise ValueError(
        "GEE_PROJECT_ID não foi encontrado! Verifique se o arquivo .env existe na mesma pasta"
    )

try:
    ee.Initialize(project=PROJECT_ID)
except Exception:
    ee.Authenticate()
    ee.Initialize(project=PROJECT_ID)

# =============== 2: Criação de interface gráfica =========================
ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("blue")

class AppDesmatamento(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title("Sistema de Monitorização de Desmatamento por Satélite")
        self.geometry("1080x720")

        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        # Painel lateral
        self.frame_menu = ctk.CTkFrame(self, width=400, corner_radius=0)
        self.frame_menu.grid(row=0, column=0, sticky="nsew", padx=10, pady=10)

        self.label_titulo = ctk.CTkLabel(
            self.frame_menu,
            text="Parâmetros de Análise", 
            font=ctk.CTkFont(size=18, weight="bold")
        )
        self.label_titulo.pack(padx=10, pady=(15, 15))

        # Entradas
        self.label_local = ctk.CTkLabel(self.frame_menu, text="Cidade ou Local (Coordenadas):")
        self.label_local.pack(anchor="w", padx=15, pady=(5, 0))
        self.entry_local = ctk.CTkEntry(self.frame_menu, placeholder_text="Ex: Ribeirão Preto, SP")
        self.entry_local.pack(fill="x", padx=15, pady=(0, 10))

        self.label_raio = ctk.CTkLabel(self.frame_menu, text="Raio de Busca (km):")
        self.label_raio.pack(anchor="w", padx=15, pady=(5, 0))
        self.entry_raio = ctk.CTkEntry(self.frame_menu, placeholder_text="Ex: 10")
        self.entry_raio.pack(fill="x", padx=15, pady=(0, 10))

        # Datas
        self.label_ano_inicio = ctk.CTkLabel(self.frame_menu, text="Ano Inicial:")
        self.label_ano_inicio.pack(anchor="w", padx=15, pady=(5, 0))
        self.combo_ano_inicio = ctk.CTkOptionMenu(self.frame_menu, values=["2019", "2020", "2021", "2022", "2023"])
        self.combo_ano_inicio.pack(fill="x", padx=15, pady=(0, 10))

        self.label_ano_fim = ctk.CTkLabel(self.frame_menu, text="Ano Final:")
        self.label_ano_fim.pack(anchor="w", padx=15, pady=(5, 0))
        self.combo_ano_fim = ctk.CTkOptionMenu(self.frame_menu, values=["2022", "2023", "2024", "2025", "2026"])
        self.combo_ano_fim.pack(fill="x", padx=15, pady=(0, 10))

        # Botão Processar
        self.btn_analisar = ctk.CTkButton(
            self.frame_menu, 
            text="🔍 Analisar Desmatamento", 
            command=self.processar_analise, 
            fg_color="#2ba84a", 
            hover_color="#1e7a35"
        )
        self.btn_analisar.pack(fill="x", padx=15, pady=(15, 10))

        # Indicador de Área
        self.frame_resultado = ctk.CTkFrame(self.frame_menu, fg_color="#1f242d")
        self.frame_resultado.pack(fill="x", padx=15, pady=5)

        self.label_resultado_titulo = ctk.CTkLabel(self.frame_resultado, text="Área Desmatada (filtrada):", font=ctk.CTkFont(size=12))
        self.label_resultado_titulo.pack(pady=(8, 2))

        self.label_area = ctk.CTkLabel(self.frame_resultado, text="0.00 ha", font=ctk.CTkFont(size=20, weight="bold"), text_color="#e63946")
        self.label_area.pack(pady=(0, 4))
        self.label_comparacao = ctk.CTkLabel(
            self.frame_resultado, text="Bruta: — | Ruído removido: —",
            font=ctk.CTkFont(size=11)
        )
        self.label_comparacao.pack(pady=(0, 8))

        # Botão para abrir sobreposição completa
        self.btn_abrir_mapa = ctk.CTkButton(
            self.frame_menu,
            text="🗺️ Ver mapa de desmatamento no Navegador",
            command=self.abrir_mapa_html,
            fg_color="#1d3557",
            hover_color="#457b9d",
            state="disabled"
        )
        self.btn_abrir_mapa.pack(fill="x", padx=15, pady=(10, 4))
        self.label_dica_mapa = ctk.CTkLabel(
            self.frame_menu,
            text="As máscaras amarela (original) e vermelha (filtrada) aparecem no navegador, não no painel lateral.",
            font=ctk.CTkFont(size=11),
            wraplength=350,
        )
        self.label_dica_mapa.pack(fill="x", padx=15, pady=(0, 6))

        self.label_status = ctk.CTkLabel(
            self.frame_menu,
            text="Informe local, raio e datas; depois clique em Analisar.",
            font=ctk.CTkFont(size=11),
            wraplength=350,
        )
        self.label_status.pack(padx=10, pady=5)

        # Painel do mapa
        self.frame_mapa = ctk.CTkFrame(self)
        self.frame_mapa.grid(row=0, column=1, sticky="nsew", padx=(0, 10), pady=10)

        self.mapa_widget = TkinterMapView(self.frame_mapa, corner_radius=0)
        self.mapa_widget.pack(fill="both", expand=True)

        self.mapa_widget.set_position(-21.1680, -47.7780)
        self.mapa_widget.set_zoom(12)
        self.mapa_widget.set_tile_server("https://mt1.google.com/vt/lyrs=s&x={x}&y={y}&z={z}", max_zoom=22)

        self.mapa_html_path = Path(__file__).resolve().with_name("mapa_desmatamento.html")

    # Convertendo a cidade para coordenadas
    def obter_coordenadas(self, nome_local):
        try:
            geolocator = Nominatim(user_agent="app_desmatamento")
            localizacao = geolocator.geocode(nome_local)
            if localizacao:
                return localizacao.latitude, localizacao.longitude
        except Exception:
            return None
        return None

    # Relata exceções de rede e Earth Engine também dentro da interface.
    def processar_analise(self):
        self.btn_analisar.configure(state="disabled")
        try:
            self.executar_analise()
        except Exception as erro:
            traceback.print_exc()
            self.label_status.configure(
                text=f"Erro na análise: {erro}", text_color="red"
            )
            messagebox.showerror(
                "Falha na análise",
                f"A análise não foi concluída.\n\n{erro}\n\n"
                "Confira também os detalhes no terminal.",
            )
        finally:
            self.btn_analisar.configure(state="normal")

    # Recolhendo dados informados e validando informações
    def executar_analise(self):
        self.btn_abrir_mapa.configure(state="disabled")
        local_texto = self.entry_local.get().strip()
        try:
            raio_km = float(self.entry_raio.get()) if self.entry_raio.get() else 10.0
            if not math.isfinite(raio_km) or raio_km <= 0:
                raise ValueError("Raio inválido")
        except ValueError:
            self.label_status.configure(text="Erro: informe um raio válido em km.", text_color="red")
            return

        ano_inicio = self.combo_ano_inicio.get()
        ano_fim = self.combo_ano_fim.get()
        if int(ano_inicio) >= int(ano_fim):
            self.label_status.configure(text="Erro: ano final deve ser posterior ao inicial.", text_color="red")
            return
        if not local_texto:
            self.label_status.configure(text="Erro: informe uma localidade.", text_color="red")
            return

        self.label_status.configure(text="A buscar coordenadas...", text_color="yellow")
        self.update()

        coords = self.obter_coordenadas(local_texto)
        if not coords:
            self.label_status.configure(text="Erro: Local não encontrado!", text_color="red")
            return

        lat, lon = coords
        self.label_status.configure(text="Buscando no Earth Engine...", text_color="yellow")
        self.update()

        # Buscando local no Earth Engine
        ponto = ee.Geometry.Point([lon, lat])
        aoi = ponto.buffer(raio_km * 1000)

        # Função p/ calcular diferença de bandas B8 e B4 (NDVI - Normalized Difference Vegetation Index)
        def adicionar_ndvi(imagem):
            return imagem.addBands(imagem.normalizedDifference(['B8', 'B4']).rename('NDVI'))

        sentinel = (ee.ImageCollection('COPERNICUS/S2_SR_HARMONIZED') # reflectância de superfície harmonizada
                    .filterBounds(aoi)
                    .filter(ee.Filter.lt('CLOUDY_PIXEL_PERCENTAGE', 10)) # Removendo imagens com +10% de nuvens em cena
                    .map(mascarar_nuvens_scl)
                    .map(adicionar_ndvi))

        # Período de junho a setembro: a data final é exclusiva.
        colecao_antes = sentinel.filterDate(f'{ano_inicio}-06-01', f'{ano_inicio}-10-01')
        colecao_depois = sentinel.filterDate(f'{ano_fim}-06-01', f'{ano_fim}-10-01')
        if colecao_antes.size().getInfo() == 0 or colecao_depois.size().getInfo() == 0:
            self.label_status.configure(
                text="Sem cenas Sentinel-2 nos anos selecionados.", text_color="red"
            )
            return

        observacoes_suficientes = pixels_com_observacoes_suficientes(
            colecao_antes, colecao_depois, OBSERVACOES_MINIMAS
        )
        ndvi_antes = (
            colecao_antes.median().clip(aoi).select('NDVI')
            .updateMask(observacoes_suficientes)
        )
        ndvi_depois = (
            colecao_depois.median().clip(aoi).select('NDVI')
            .updateMask(observacoes_suficientes)
        )

        delta_ndvi = ndvi_depois.subtract(ndvi_antes) # Calcula variação NDVI pixel a pixel
        queda_severa = delta_ndvi.lte(-0.35) # Identifica onde houve queda de NDVI <= -0.35
        era_floresta = ndvi_antes.gte(0.4) # Vê se local era área vegetada no inicio (>= 0.4)
        mascara_original = (
            queda_severa.And(era_floresta)
            .rename('desmatamento')
            .updateMask(observacoes_suficientes)
        )
        self.label_status.configure(text="Filtrando ruídos (5 pixels)...", text_color="yellow")
        self.update()
        # Fixar a contagem na grade nativa de 10 m da banda B4.
        projecao_10m = ee.Image(colecao_antes.first()).select('B4').projection()
        desmatamento_mascara = remover_ruido_conectado(
            mascara_original, projecao_10m, minimo_pixels=PIXELS_MINIMOS
        )

        # As áreas usam as mesmas máscaras exibidas no mapa.
        try:
            areas = calcular_areas(
                mascara_original, desmatamento_mascara,
                observacoes_suficientes, aoi
            )
            area_ha = areas['filtrada_ha']
            self.label_area.configure(text=f"{area_ha:.2f} ha")
            self.label_comparacao.configure(
                text=(f"Bruta: {areas['bruta_ha']:.2f} ha | "
                      f"Ruído removido: {areas['removida_ha']:.2f} ha")
            )
        except Exception as erro:
            self.label_area.configure(text="N/A")
            self.label_comparacao.configure(text="Não foi possível calcular a área.")
            self.label_status.configure(text=f"Falha na análise: {erro}", text_color="red")
            return

        # Duas camadas independentes permitem comparar máscara original e filtrada.
        try:
            map_id_antes = ndvi_antes.getMapId({
                'min': 0, 'max': 0.8, 'palette': ['red', 'yellow', 'green']
            })
            map_id_depois = ndvi_depois.getMapId({
                'min': 0, 'max': 0.8, 'palette': ['red', 'yellow', 'green']
            })
            map_id_original = mascara_original.selfMask().getMapId({
                'palette': ['ffbf00']
            })
            map_id_filtrado = desmatamento_mascara.selfMask().getMapId({
                'palette': ['e63946']
            })

            m = folium.Map(location=[lat, lon], zoom_start=12, tiles=None)
            folium.TileLayer(
                tiles='https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}',
                attr='Esri', name='Imagem de Satélite', overlay=False
            ).add_to(m)
            folium.TileLayer(
                tiles=map_id_antes['tile_fetcher'].url_format,
                attr='GEE', name=f'NDVI {ano_inicio}', overlay=True, show=False
            ).add_to(m)
            folium.TileLayer(
                tiles=map_id_depois['tile_fetcher'].url_format,
                attr='GEE', name=f'NDVI {ano_fim}', overlay=True, show=False
            ).add_to(m)
            folium.TileLayer(
                tiles=map_id_original['tile_fetcher'].url_format,
                attr='GEE', name='Detecção original (sem filtro)',
                overlay=True, show=False
            ).add_to(m)
            folium.TileLayer(
                tiles=map_id_filtrado['tile_fetcher'].url_format,
                attr='GEE', name=f'Detecção filtrada (mín. {PIXELS_MINIMOS} pixels)',
                overlay=True, show=True
            ).add_to(m)
            folium.LayerControl(collapsed=False).add_to(m)
            m.save(self.mapa_html_path)
        except Exception as erro:
            self.label_status.configure(text=f"Falha ao gerar mapa: {erro}", text_color="red")
            return

        # 4. Atualizar janela
        self.mapa_widget.set_position(lat, lon)
        self.mapa_widget.set_zoom(12)
        self.mapa_widget.delete_all_marker()
        self.mapa_widget.delete_all_path()
        self.mapa_widget.delete_all_polygon()

        # Desenhar perímetro do raio
        def criar_circulo(l_lat, l_lon, r_km, pontos=64):
            coords_list = []
            r_terra = 6371.0
            for i in range(pontos):
                ang = math.radians((i / pontos) * 360)
                l_rad, lo_rad = math.radians(l_lat), math.radians(l_lon)
                d_lat = (r_km / r_terra) * math.cos(ang)
                d_lon = (r_km / (r_terra * math.cos(l_rad))) * math.sin(ang)
                coords_list.append((math.degrees(l_rad + d_lat), math.degrees(lo_rad + d_lon)))
            return coords_list

        self.mapa_widget.set_polygon(criar_circulo(lat, lon, raio_km), outline_color="#e63946", fill_color=None, border_width=2)
        self.mapa_widget.set_marker(lat, lon, text=f"{local_texto}\nRaio: {raio_km}km | Desmatado (filtrado): {area_ha:.2f} ha")

        self.btn_abrir_mapa.configure(state="normal")
        self.label_status.configure(
            text=f"Concluído! Abrindo mapa original × filtrado ({PIXELS_MINIMOS} pixels) no navegador...",
            text_color="#2ba84a"
        )
        self.update_idletasks()
        self.abrir_mapa_html()

    # Abre o mapa de resultados no navegador (arquivo local).
    def abrir_mapa_html(self):
        try:
            caminho = Path(self.mapa_html_path).resolve()
            if not caminho.is_file():
                raise FileNotFoundError(f"Mapa ainda não foi gerado: {caminho}")
            # webbrowser.open exige uma URL; caminhos relativos podem não funcionar.
            abriu = webbrowser.open(caminho.as_uri(), new=2)
            if not abriu:
                self.label_status.configure(
                    text="Mapa gerado, mas o navegador não abriu automaticamente.",
                    text_color="yellow",
                )
                messagebox.showinfo(
                    "Mapa salvo",
                    f"O mapa foi salvo em:\n{caminho}\n\nAbra este arquivo no navegador.",
                )
        except Exception as erro:
            self.label_status.configure(
                text="Não foi possível abrir o mapa automaticamente.",
                text_color="red"
            )
            messagebox.showerror("Falha ao abrir mapa", str(erro))


if __name__ == "__main__":
    app = AppDesmatamento()
    app.mainloop()