import streamlit as st
import requests
import os
import base64
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

API_URL = "https://api.openai.com/v1/responses"
MODEL = "gpt-5.4-mini"

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
# CARREGAR IMAGEM
# =====================================================

st.markdown("### 📷 CARREGAR GRÁFICO")

uploaded_file = st.file_uploader(
    "Seleciona o screenshot do gráfico",
    type=["png", "jpg", "jpeg"]
)

image = None

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
        st.error(f"Erro ao abrir imagem: {e}")

st.markdown("---")

# =====================================================
# PREPARAÇÃO DA IMAGEM
# =====================================================

def image_to_base64(img):

    buffer = BytesIO()

    img = img.copy()
    img.thumbnail((2000, 2000))

    img.save(
        buffer,
        format="JPEG",
        quality=92,
        optimize=True
    )

    return base64.b64encode(
        buffer.getvalue()
    ).decode("utf-8")


# =====================================================
# INSTRUÇÕES DO GPT
# =====================================================

def build_prompt():

    return f"""
És o motor principal de análise técnica da
DONCULLER-TRADE47.

Analisa a imagem do gráfico com atenção.

ATIVO: {asset}
TIMEFRAME: {timeframe}
PLATAFORMA: {platform}

OBJETIVO:
Identificar a direção mais provável do próximo movimento.

Compara BUY e SELL antes de decidir.

Não escolhas AGUARDAR automaticamente.
Quando houver evidência técnica suficiente, escolhe BUY ou SELL.
Quando não houver uma entrada defensável, escolhe AGUARDAR.

ANÁLISE OBRIGATÓRIA:

1. Tendência principal.
2. Estrutura HH, HL, LH e LL.
3. Suportes e resistências.
4. Zonas de oferta e procura.
5. Liquidez e varrimentos.
6. Falsos rompimentos.
7. Padrões de velas.
8. EMA 20 e EMA 50, se visíveis.
9. RSI, se visível.
10. MACD, se visível.
11. ZigZag, se visível.
12. Fractais, se visíveis.
13. Possíveis zonas de entrada.
14. Relação risco/retorno.

REGRAS:

- Não inventes preços.
- Não inventes indicadores.
- Não afirmes que um indicador está positivo ou negativo
  quando não for possível observá-lo.
- Não confundas estimativa técnica com taxa de acerto real.
- Não prometas lucros.
- Considera a direção e o comportamento próprio do ativo.
- Para BUY, o SL deve ficar abaixo da entrada.
- Para SELL, o SL deve ficar acima da entrada.
- Só apresenta preços quando forem legíveis.
- Se não houver dados suficientes, explica a limitação.
- Não forces uma operação.

PROBABILIDADES:

Apresenta uma estimativa técnica de BUY e SELL.
As duas percentagens devem somar 100%.
Não as apresentes como percentagens históricas de acerto.

FORMATO OBRIGATÓRIO:

DECISÃO: BUY / SELL / AGUARDAR

PROBABILIDADE ESTIMADA:
BUY: ...%
SELL: ...%

QUALIDADE:
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
...

PRÓXIMA AÇÃO:
...

Responde em português simples, direto e operacional.
Máximo de 450 palavras.
"""


# =====================================================
# EXTRAIR RESPOSTA OPENAI
# =====================================================

def extract_answer(result):

    if result.get("error"):
        raise ValueError(str(result["error"]))

    if result.get("status") == "incomplete":

        details = result.get("incomplete_details", {})

        raise ValueError(
            "A resposta ficou incompleta: "
            + str(details)
        )

    # Campo simplificado da Responses API
    answer = result.get("output_text", "")

    if answer:
        return answer.strip()

    # Alternativa: procurar texto dentro de output
    parts = []

    for item in result.get("output", []):

        if item.get("type") == "message":

            for content in item.get("content", []):

                if content.get("type") == "output_text":
                    parts.append(content.get("text", ""))

                elif content.get("type") == "refusal":
                    raise ValueError(
                        content.get("refusal", "Pedido recusado.")
                    )

    answer = "\n".join(parts).strip()

    if not answer:
        raise ValueError(
            "O GPT não devolveu um relatório de análise."
        )

    return answer


# =====================================================
# MOTOR PRINCIPAL OPENAI
# =====================================================

def analyze_chart(img):

    api_key = os.environ.get("OPENAI_API_KEY")

    if not api_key:
        return None, (
            "A variável OPENAI_API_KEY não foi encontrada "
            "no Render."
        )

    try:

        encoded_image = image_to_base64(img)

        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }

        payload = {
            "model": MODEL,

            "input": [
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "input_text",
                            "text": build_prompt()
                        },
                        {
                            "type": "input_image",
                            "image_url": (
                                "data:image/jpeg;base64,"
                                + encoded_image
                            ),
                            "detail": "high"
                        }
                    ]
                }
            ],

            "max_output_tokens": 1800
        }

        response = requests.post(
            API_URL,
            headers=headers,
            json=payload,
            timeout=180
        )

        try:
            result = response.json()

        except ValueError:
            return None, (
                f"Resposta inválida do servidor. "
                f"HTTP {response.status_code}"
            )

        if response.status_code != 200:

            error = result.get("error", {})

            if isinstance(error, dict):
                details = error.get(
                    "message",
                    str(error)
                )
            else:
                details = str(error)

            return None, (
                f"OPENAI HTTP {response.status_code}: "
                f"{details}"
            )

        answer = extract_answer(result)

        return answer, None

    except requests.exceptions.Timeout:

        return None, (
            "O GPT demorou demasiado a responder. "
            "Tenta novamente."
        )

    except requests.exceptions.ConnectionError:

        return None, (
            "Falha de ligação à API da OpenAI."
        )

    except ValueError as e:

        return None, f"RESPOSTA INVÁLIDA: {str(e)}"

    except Exception as e:

        return None, f"ERRO INESPERADO: {str(e)}"


# =====================================================
# BOTÃO DE ANÁLISE
# =====================================================

if st.button(
    "🔍 ANALISAR GRÁFICO",
    use_container_width=True
):

    if image is None:

        st.warning(
            "Primeiro, carrega um screenshot do gráfico."
        )

    else:

        with st.spinner(
            "GPT a analisar o mercado..."
        ):

            answer, error = analyze_chart(image)

        if error:

            st.error(error)

        else:

            st.markdown("---")
            st.markdown("## 📊 RELATÓRIO DE ANÁLISE")

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
                "DONCULLER-TRADE47 | "
                "Motor de análise GPT"
            )


# =====================================================
# AVISO
# =====================================================

st.markdown("---")

st.caption(
    "Análise técnica assistida por IA. "
    "As estimativas não representam taxas de acerto comprovadas. "
    "Testa sempre em conta Demo antes de operar com dinheiro real."
)
