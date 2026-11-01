import streamlit as st
import requests
import base64
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

    if st.button(
        "🦁 ANALISAR GRÁFICO",
        use_container_width=True
    ):

        if not API_KEY:
            st.error(
                "Chave OpenRouter não encontrada. "
                "Verifica o Environment no Render."
            )

        else:

            with st.spinner(
                "DONCULLER-TRADE47 está a analisar..."
            ):

                try:

                    buffer = BytesIO()
                    img.save(buffer, format="JPEG", quality=85)

                    imagem_base64 = base64.b64encode(
                        buffer.getvalue()
                    ).decode("utf-8")

                    prompt = f"""
És o motor de análise técnica da
DONCULLER-TRADE47.

Analisa cuidadosamente o screenshot.

ATIVO: {ativo}
TIMEFRAME: {timeframe}

OBJETIVO:

Fazer uma análise técnica rigorosa,
clara e organizada.

ESTRUTURA OBRIGATÓRIA:

1. TENDÊNCIA
- Alta, baixa ou lateral.
- Explica o motivo.

2. ESTRUTURA DO MERCADO
- Identifica máximos e mínimos.
- Procura tendências, pullbacks e possíveis reversões.

3. CENÁRIO BUY
- Existe oportunidade de compra?
- Possível zona de entrada.
- Stop Loss.
- Take Profit.
- Confirmação necessária.

4. CENÁRIO SELL
- Existe oportunidade de venda?
- Possível zona de entrada.
- Stop Loss.
- Take Profit.
- Confirmação necessária.

5. COMPARAÇÃO
- Compara os cenários BUY e SELL.
- Indica qual apresenta melhores condições técnicas.
- Se nenhum for suficientemente claro, explica porquê.

6. DECISÃO FINAL
Escolhe apenas uma:
BUY, SELL ou AGUARDAR.

7. JUSTIFICAÇÃO
Explica claramente a decisão.

REGRAS IMPORTANTES:

- Analisa BUY e SELL independentemente.
- Não escolhas BUY ou SELL sem evidências.
- Se a decisão for AGUARDAR, apresenta os dois cenários
  possíveis quando houver dados suficientes.
- Não inventes preços, entradas, SL ou TP.
- Se os preços não forem legíveis, informa isso.
- Não inventes indicadores que não aparecem no gráfico.
- Considera suportes, resistências e estrutura do mercado.
- Não apresentes percentagens de confiança inventadas.
- Não prometas lucros ou resultados garantidos.
- Considera o risco dos índices sintéticos.
- Se faltar informação, explica o que é necessário.
- Responde sempre em português simples.

A análise deve ser profissional, objetiva e organizada.
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

                    st.error(
                        f"Erro durante a análise: {e}"
                    )

st.divider()

st.caption("DONCULLERTRADE47 © 2026")

st.caption(
    "Análise técnica | Gestão de risco | "
    "Inteligência artificial"
)

st.warning(
    "As análises são assistidas por IA e não "
    "garantem lucros. Confirma os sinais antes "
    "de qualquer operação."
)
