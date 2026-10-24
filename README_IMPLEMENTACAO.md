# Remoção equilibrada de ruídos — 5 pixels

Implementação para a aplicação Python de monitoramento de desmatamento baseada em Sentinel-2 e Google Earth Engine.

## O que muda

- A banda SCL elimina por pixel classes inválidas, sombras, nuvens, cirrus e neve antes de calcular o NDVI.
- Cada pixel precisa de pelo menos 3 observações válidas **em ambos os períodos** (ano inicial e final).
- A detecção original preserva os limiares existentes: NDVI inicial >= 0.4 e variação <= -0.35.
- O módulo `filtro_ruido.py` remove grupos positivos com **menos de 5 pixels 8-conectados**, medidos em uma projeção B4 Sentinel-2 de 10 m.
- O cálculo de área informa hectares **brutos, filtrados e removidos**.
- O mapa HTML Folium contém as camadas independentes **Detecção original (sem filtro)** (amarelo, desativada) e **Detecção filtrada (mín. 5 pixels)** (vermelho, ativada). Assim é possível comparar as máscaras na mesma área.

Esta etapa realiza as operações no próprio Google Earth Engine; **OpenCV não é necessário**.

## Instalação e execução

1. Tenha Python e um projeto habilitado no Google Earth Engine.
2. Instale as dependências: `python -m pip install -r requirements.txt`.
3. Crie um arquivo `.env` com `GEE_PROJECT_ID=seu-id-do-projeto`; o arquivo real não deve ser versionado.
4. Execute `python Analise_desmatamento.py`.
5. Selecione local, raio, ano inicial e final, depois clique em **Analisar Desmatamento**.
6. Após a análise terminar, o mapa HTML é aberto **automaticamente** no navegador. Caso precise, use **Ver mapa de desmatamento no Navegador** para reabri-lo.
7. Se o navegador não abrir, localize o arquivo `mapa_desmatamento.html` na mesma pasta do script e abra-o manualmente. O aplicativo informa o caminho.
8. Se ocorrer uma exceção durante o processamento, o aplicativo abre uma janela com a mensagem de erro e registra detalhes no terminal.

**Observação:** o mapa da interface Tkinter mostra somente o fundo de satélite, o perímetro e um marcador. As máscaras original e filtrada são exibidas no **mapa Folium do navegador**.

## Testes offline

```bash
python -m unittest discover -s tests -v
python -m compileall -q Analise_desmatamento.py filtro_ruido.py
```

Os testes verificam a construção das expressões e os parâmetros, usando dublês da API: **não confirmam a precisão das imagens reais**.

## Parâmetros

Em `filtro_ruido.py`:

- `PIXELS_MINIMOS = 5`
- `OBSERVACOES_MINIMAS = 3`
- Classes SCL descartadas: `1, 3, 7, 8, 9, 10, 11`.
- Filtro inicial de cenas: `CLOUDY_PIXEL_PERCENTAGE < 10`.
- Datas: de 1º de junho até antes de 1º de outubro.
- Contagem de vizinhança: 8 conexões.
- Escala de redução de área: 10 m.

## Limitações e validação recomendada

- A execução real com Earth Engine requer autenticação e acesso remoto, e **ainda não foi validada com imagens reais**.
- A SCL é de 20 m; sua máscara é aplicada ao NDVI de 10 m com reamostragem implícita.
- A projeção da primeira imagem Sentinel-2 do ano inicial é usada como referência para a conectividade. Em áreas que cruzem fusos UTM ou regiões extensas, reavalie essa escolha.
- A operação `reproject` pode ser cara para áreas grandes.
- Cinco pixels de 10 x 10 m correspondem nominalmente a 0,05 ha; o cálculo oficial da aplicação utiliza `ee.Image.pixelArea()`.
- Um filtro de 5 pixels pode remover clareiras verdadeiras pequenas. Valide sua precisão contra áreas de referência antes de usar os resultados para conclusões científicas ou operacionais.
- Queda de NDVI não distingue por si só desmatamento de mudanças fenológicas, manejo agrícola ou outras perturbações.
