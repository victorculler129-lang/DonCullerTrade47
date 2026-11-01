import streamlit as st
import requests
import base64
import json
from PIL import Image
from io import BytesIO
import os

st.set_page_config(
    page_title="DONCULLER-TRADE47",
    page_icon="🦁",
    layout="centered"
)

API_KEY = os.environ.get("OPENROUTER_API_KEY")

MODEL = "openrouter/free"

st.title("🦁 DONCULLER-TRADE47")
st.subheader("AI Trading Chart Analyzer")

st.write(
    "Inteligência artificial para análise "
    "visual de gráficos de trading."
)

st.divider()

ativo = st.selectbox(
    "Escolhe o ativo",
    [
        "Boom 1000",
        "Crash 1000",
        "Boom 500",
        "Crash 500",
        "Jump Index",
        "Step Index",
        "EUR/USD",
        "GBP/USD",
        "XAU/USD"
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

    st.image(
        img,
        caption="Gráfico selecionado",
        use_container_width=True
    )

    if st.button("🦁 ANALISAR GRÁFICO", use_container_width=True):

        if not API_KEY:
            st.error(
                "Chave OpenRouter não encontrada. "
                "Verifica as variáveis Environment no Render."
            )

        else:

            with st.spinner(
                "A DONCULLER-TRADE47 está a analisar o gráfico..."
            ):

                try:

                    buffer = BytesIO()
                    img.save(buffer, format="JPEG", quality=85)

                    imagem_base64 = base64.b64encode(
                        buffer.getvalue()
                    ).decode("utf-8")

                    prompt = f"""
                    És o motor de análise técnica da DONCULLER-TRADE47.

                    Analisa cuidadosamente o screenshot enviado.

                    Ativo: {ativo}
                    Timeframe: {timeframe}

                    Identifica:

                    1. Tendência: ALTA, BAIXA ou LATERAL.
                    2. Estrutura do mercado.
                    3. Suportes e resistências visíveis.
                    4. Padrões de velas japonesas.
                    5. Possíveis sinais de reversão.
                    6. Decisão: BUY, SELL ou AGUARDAR.
                    7. Possível zona de entrada.
                    8. Stop Loss sugerido.
                    9. Take Profit sugerido.
                    10. Justificação da análise.

                    REGRAS IMPORTANTES:

                    - Nunca inventes preços que não estejam legíveis.
                    - Se não conseguires identificar os preços,
                      informa que são necessários mais dados.
                    - Não inventes indicadores.
                    - Se o gráfico estiver confuso, responde AGUARDAR.
                    - Não apresentes probabilidades de sucesso inventadas.
                    - Distingue observações de hipóteses.
                    - Considera o risco de operações em índices sintéticos.
                    - Responde sempre em português simples.

                    Organiza a resposta com títulos claros.
                    """

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
                                                    + imagem_base64
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

                        resultado = response.json()

                        analise = resultado[
                            "choices"
                        ][0]["message"]["content"]

                        st.success("ANÁLISE CONCLUÍDA")

                        st.markdown(analise)

                    else:

                        st.error(
                            f"Erro da API: {response.status_code}"
                        )

                        st.write(response.text[:1500])

                except requests.exceptions.Timeout:

                    st.error(
                        "A análise demorou demasiado. "
                        "Tenta novamente."
                    )

                except Exception as e:

                    st.error(f"Erro durante a análise: {e}")

st.divider()

st.caption("DONCULLERTRADE47 © 2026")
st.caption(
    "Análise técnica | Gestão de risco | Inteligência artificial"
)

st.warning(
    "Os resultados são análises assistidas por IA, "
    "não garantias de lucro. Confirma os sinais antes "
    "de qualquer operação."
                    )
