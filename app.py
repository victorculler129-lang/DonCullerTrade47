import streamlit as st
import requests
import base64
import os
from PIL import Image
from io import BytesIO

st.set_page_config(
    page_title="DONCULLER-TRADE47",
    page_icon="🦁",
    layout="centered"
)

API_KEY = os.environ.get("OPENROUTER_API_KEY")
MODEL = "openrouter/free"

st.title("🦁 DONCULLER-TRADE47")
st.subheader("AI Trading Chart Analyzer")

st.write("Análise inteligente e previsão de entradas no mercado.")

ativo = st.selectbox(
    "Escolhe o ativo",
    [
        "Boom 1000", "Crash 1000",
        "Boom 500", "Crash 500",
        "Boom 300", "Crash 300",
        "Boom 100", "Crash 100",
        "Boom 50", "Crash 50",
        "Jump Index 50", "Jump Index",
        "Step Index", "EUR/USD",
        "GBP/USD", "XAU/USD"
    ]
)

timeframe = st.selectbox(
    "Seleciona o timeframe",
    ["M1", "M5", "M15", "M30", "H1", "H4", "D1"]
)

imagem = st.file_uploader(
    "Carrega o screenshot do gráfico",
    type=["png", "jpg", "jpeg"]
)

if imagem:
    img = Image.open(imagem).convert("RGB")
    img.thumbnail((1600, 1600))

    st.image(img, caption="Gráfico selecionado",
             use_container_width=True)

    if st.button("🦁 ANALISAR E PREVER ENTRADA",
                 use_container_width=True):

        if not API_KEY:
            st.error("OPENROUTER_API_KEY não encontrada no Render.")

        else:
            prompt = f"""
És o sistema de análise técnica da DONCULLER-TRADE47.

ATIVO: {ativo}
TIMEFRAME: {timeframe}

Analisa cuidadosamente a imagem do gráfico.

OBJETIVO:
Prever a próxima oportunidade de entrada futura,
escolhendo apenas UMA direção principal.

1. ANALISA:
- Tendência do mercado.
- Estrutura de máximos e mínimos.
- Suportes e resistências.
- Pullbacks e rejeições.
- Padrões de velas.
- RSI, MACD e médias móveis, se estiverem visíveis.

2. ESCOLHE UMA DIREÇÃO:
BUY ou SELL.

Compara internamente as duas possibilidades,
mas apresenta apenas uma previsão final.

Não apresentes duas entradas diferentes.

Só utiliza AGUARDAR quando não houver evidências
suficientes para uma previsão responsável.

3. PREVÊ UMA ENTRADA FUTURA:
Indica o preço ou zona onde a entrada poderá ocorrer.
Explica a condição necessária para ativar a entrada.

4. DEFINE:
- Stop Loss.
- Take Profit.
- Relação risco/retorno, se calculável.

Não inventes preços.
Se a escala não permitir identificar valores,
informa que não é possível determinar o preço exato.

5. APRESENTA A FORÇA TÉCNICA:
Pontuação BUY: 0 a 100.
Pontuação SELL: 0 a 100.

São pontuações técnicas estimadas,
não probabilidades comprovadas de lucro.

FORMATO OBRIGATÓRIO:

ATIVO:
TIMEFRAME:

TENDÊNCIA:

ANÁLISE TÉCNICA:

PONTUAÇÃO BUY:
PONTUAÇÃO SELL:

PREVISÃO PRINCIPAL: BUY / SELL / AGUARDAR

ENTRADA FUTURA:

CONDIÇÃO DE ATIVAÇÃO:

ESTADO: Entrada ainda não ativada / Ativada / Sem dados.

STOP LOSS:

TAKE PROFIT:

RISCO/RETORNO:

JUSTIFICAÇÃO:

Responde em português simples e direto.
Não prometas lucros nem inventes informações.
"""

            with st.spinner("A IA está a analisar o gráfico..."):
                try:
                    buffer = BytesIO()
                    img.save(buffer, format="JPEG", quality=85)

                    encoded = base64.b64encode(
                        buffer.getvalue()
                    ).decode("utf-8")

                    response = requests.post(
                        "https://openrouter.ai/api/v1/chat/completions",
                        headers={
                            "Authorization": f"Bearer {API_KEY}",
                            "Content-Type": "application/json",
                            "X-Title": "DONCULLER-TRADE47"
                        },
                        json={
                            "model": MODEL,
                            "messages": [
                                {
                                    "role": "user",
                                    "content": [
                                        {
                                            "type": "text",
                                            "text": prompt
                                        },
                                        {
                                            "type": "image_url",
                                            "image_url": {
                                                "url": (
                                                    "data:image/jpeg;base64,"
                                                    + encoded
                                                )
                                            }
                                        }
                                    ]
                                }
                            ]
                        },
                        timeout=120
                    )

                    if response.status_code == 200:
                        data = response.json()
                        resultado = data["choices"][0]["message"]["content"]

                        if isinstance(resultado, list):
                            resultado = "\n".join(
                                item.get("text", "")
                                for item in resultado
                                if isinstance(item, dict)
                            )

                        st.success("ANÁLISE CONCLUÍDA")
                        st.markdown(resultado)

                    else:
                        st.error(
                            f"Erro da API: {response.status_code}"
                        )
                        st.write(response.text[:1500])

                except requests.exceptions.Timeout:
                    st.error("A análise demorou demasiado. Tenta novamente.")

                except Exception as erro:
                    st.error(f"Erro durante a análise: {erro}")

st.divider()
st.caption("DONCULLERTRADE47 © 2026")
st.caption("AI Trading | Price Action | Risk Management")

st.warning(
    "As previsões são estimativas técnicas. "
    "Testa sempre numa conta demo antes de arriscar dinheiro."
)
