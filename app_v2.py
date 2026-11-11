import streamlit as st
import requests
import os
import base64
import json
from io import BytesIO
from PIL import Image, ImageOps

# =====================================================
# CONFIGURAÇÃO
# =====================================================

st.set_page_config(
    page_title="DONCULLER-TRADE47",
    page_icon="🦁",
    layout="centered"
)

API_URL = "https://openrouter.ai/api/v1/chat/completions"
MODEL = "openrouter/free"

# =====================================================
# VISUAL
# =====================================================

st.markdown("""
<style>
.stApp {
    background-color: #071426;
    color: #ffffff;
}

h1, h2, h3 {
    color: #ffffff;
}

.subtitle {
    color: #8daacb;
    text-align: center;
    font-size: 14px;
}

.panel {
    background: #10233d;
    padding: 18px;
    border-radius: 12px;
    border: 1px solid #203d60;
    margin-bottom: 15px;
}

.buy {
    background: #063d32;
    border: 1px solid #12b886;
    padding: 15px;
    border-radius: 10px;
}

.sell {
    background: #481c29;
    border: 1px solid #e05260;
    padding: 15px;
    border-radius: 10px;
}

.wait {
    background: #3d3515;
    border: 1px solid #d6b33c;
    padding: 15px;
    border-radius: 10px;
}

.stButton > button {
    background-color: #1479d1;
    color: white;
    border-radius: 8px;
    border: none;
    width: 100%;
    font-weight: bold;
    padding: 12px;
}

.stButton > button:hover {
    background-color: #0864b5;
    color: white;
}
</style>
""", unsafe_allow_html=True)

st.markdown(
    "<h1 style='text-align:center;'>🦁 DONCULLER-TRADE47</h1>",
    unsafe_allow_html=True
)

st.markdown(
    "<p class='subtitle'>AI TRADING CHART ANALYZER</p>",
    unsafe_allow_html=True
)

st.markdown("---")

# =====================================================
# CONFIGURAÇÃO DA ANÁLISE
# =====================================================

st.markdown("### ⚙️ CONFIGURAÇÃO")

col1, col2 = st.columns(2)

with col1:
    asset = st.selectbox(
        "Ativo",
        [
            "Boom 1000",
            "Crash 1000",
            "Boom 500",
            "Crash 500",
            "Boom 300",
            "Crash 300",
            "Boom 100",
            "Crash 100",
            "Boom 50",
            "Crash 50",
            "Jump Index 50",
            "Jump Index",
            "Step Index",
            "EUR/USD",
            "GBP/USD",
            "XAU/USD"
        ]
    )

with col2:
    timeframe = st.selectbox(
        "Temporalidade",
        ["M1", "M5", "M15", "M30", "H1", "H4", "D1"]
    )

platform = st.selectbox(
    "Plataforma",
    ["Deriv MT5", "Deriv cTrader", "TradingView", "Outra"]
)

st.markdown("---")

# =====================================================
# IMAGEM
# =====================================================

st.markdown("### 📷 CARREGAR GRÁFICO")

uploaded_file = st.file_uploader(
    "Seleciona o screenshot do gráfico",
    type=["png", "jpg", "jpeg"]
)

if uploaded_file:
    try:
        image = Image.open(uploaded_file)
        image = ImageOps.exif_transpose(image).convert("RGB")

        st.image(
            image,
            caption="Gráfico selecionado",
            use_container_width=True
        )

    except Exception as e:
        st.error(f"Não foi possível abrir a imagem: {e}")
        image = None
else:
    image = None

# =====================================================
# PREPARAÇÃO DA IMAGEM
# =====================================================

def image_to_base64(img):
    buffer = BytesIO()

    img.thumbnail((1600, 1600))
    img.save(buffer, format="JPEG", quality=88)

    encoded = base64.b64encode(
        buffer.getvalue()
    ).decode("utf-8")

    return encoded


# =====================================================
# INSTRUÇÕES DA IA
# =====================================================

def build_prompt():

    return f"""
És um analista técnico profissional de mercados financeiros.

Analisa cuidadosamente o screenshot fornecido.

ATIVO: {asset}
TIMEFRAME: {timeframe}
PLATAFORMA: {platform}

OBJETIVO:
Identificar a direção mais provável do próximo movimento
operacional: BUY, SELL ou AGUARDAR.

NÃO escolhas AGUARDAR automaticamente.
Compara sempre as possibilidades de BUY e SELL.
Escolhe BUY ou SELL quando existir evidência técnica suficiente.
Escolhe AGUARDAR apenas quando não houver uma entrada
tecnicamente defensável.

ANALISA:

1. Tendência principal.
2. Estrutura de mercado: HH, HL, LH e LL.
3. Suportes e resistências.
4. Impulsos e correções.
5. Liquidez e possíveis varrimentos.
6. Falsos rompimentos.
7. Padrões de velas.
8. EMA 20 e EMA 50, se forem visíveis.
9. RSI, se estiver visível.
10. MACD, se estiver visível.
11. ZigZag, se estiver visível.
12. Fractals, se estiverem visíveis.
13. Possíveis zonas de entrada.
14. Relação risco/retorno.

IMPORTANTE:
Não inventes indicadores que não estejam visíveis.
Não inventes preços que não possam ser lidos no gráfico.
Se o preço não estiver legível, informa isso.
Não afirmes que calculaste indicadores sem dados suficientes.
Não prometas lucros nem percentagens de acerto.

FORMATO OBRIGATÓRIO DA RESPOSTA:

DECISÃO: BUY / SELL / AGUARDAR

PROBABILIDADE ESTIMADA:
BUY: ...%
SELL: ...%

QUALIDADE DO SINAL:
Forte / Moderada / Fraca

TENDÊNCIA:
...

ESTRUTURA:
...

ENTRADA:
...

CONDIÇÃO DE ATIVAÇÃO:
...

STOP LOSS:
...

TAKE PROFIT 1:
...

TAKE PROFIT 2:
...

RISCO/RETORNO:
...

CONFIRMAÇÕES:
...

RISCOS E INVALIDAÇÃO:
...

JUSTIFICAÇÃO:
Explica de forma curta e direta.

PRÓXIMA AÇÃO:
Diz exatamente o que o trader deve esperar ou fazer.

As probabilidades são estimativas técnicas, não garantias.
Se não houver dados suficientes para definir preços,
indica claramente essa limitação.
Responde em português simples e operacional.
"""


# =====================================================
# ANÁLISE OPENROUTER
# =====================================================

def analyze_chart(img):

    api_key = os.environ.get("OPENROUTER_API_KEY")

    if not api_key:
        return None, "A chave OPENROUTER_API_KEY não foi encontrada no Render."

    try:
        encoded_image = image_to_base64(img)

        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://doncullertrade47.onrender.com",
            "X-Title": "DONCULLER-TRADE47"
        }

        payload = {
            "model": MODEL,
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": build_prompt()
                        },
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": (
                                    "data:image/jpeg;base64,"
                                    + encoded_image
                                )
                            }
                        }
                    ]
                }
            ],
            "temperature": 0.2,
            "max_tokens": 1800
        }

        response = requests.post(
            API_URL,
            headers=headers,
            json=payload,
            timeout=120
        )

        if response.status_code != 200:
            try:
                details = response.json()
            except Exception:
                details = response.text

            return None, (
                f"OpenRouter HTTP {response.status_code}: "
                f"{details}"
            )

        result = response.json()

        answer = (
            result.get("choices", [{}])[0]
            .get("message", {})
            .get("content", "")
        )

        if isinstance(answer, list):
            answer = "\n".join(
                str(item.get("text", ""))
                for item in answer
                if isinstance(item, dict)
            )

        if not answer:
            return None, "A IA não devolveu uma análise válida."

        return answer, None

    except requests.exceptions.Timeout:
        return None, "Tempo de resposta excedido. Tenta novamente."

    except requests.exceptions.ConnectionError:
        return None, "Falha de ligação ao OpenRouter."

    except Exception as e:
        return None, f"Erro inesperado: {str(e)}"


# =====================================================
# BOTÃO DE ANÁLISE
# =====================================================

st.markdown("---")

if st.button("🔍 ANALISAR GRÁFICO", use_container_width=True):

    if image is None:
        st.warning("Primeiro, carrega um screenshot do gráfico.")

    else:

        with st.spinner(
            "A analisar tendência, estrutura e possíveis entradas..."
        ):

            answer, error = analyze_chart(image)

        if error:
            st.error(error)

        else:

            st.markdown("---")
            st.markdown("## 📊 RELATÓRIO DE ANÁLISE")

            # Identificar a decisão para destacar visualmente
            upper_answer = answer.upper()

            if "DECISÃO: BUY" in upper_answer:
                st.markdown(
                    "<div class='buy'><h2>🟢 BUY</h2></div>",
                    unsafe_allow_html=True
                )

            elif "DECISÃO: SELL" in upper_answer:
                st.markdown(
                    "<div class='sell'><h2>🔴 SELL</h2></div>",
                    unsafe_allow_html=True
                )

            elif "DECISÃO: AGUARDAR" in upper_answer:
                st.markdown(
                    "<div class='wait'><h2>🟡 AGUARDAR</h2></div>",
                    unsafe_allow_html=True
                )

            st.markdown(answer)

            st.markdown("---")
            st.caption(
                "DONCULLER-TRADE47 | Análise técnica assistida por IA"
            )


# =====================================================
# AVISO
# =====================================================

st.markdown("---")

st.caption(
    "A análise é uma estimativa técnica. "
    "Testa sempre em conta Demo antes de operar com dinheiro real."
)
