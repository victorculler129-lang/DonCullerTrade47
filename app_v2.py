import os
import base64
from io import BytesIO
from datetime import datetime, timezone

import requests
import streamlit as st
from PIL import Image

st.set_page_config(
    page_title="DONCULLER-TRADE47 | AI Chart Analyzer",
    page_icon="🦁",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown("""
<style>
:root { color-scheme: dark; }
.stApp { background: #071321; color: #edf3fa; }
section[data-testid="stSidebar"] {
    background: #0b1b2d;
    border-right: 1px solid #1d3550;
}
.block-container {
    padding-top: 1.4rem;
    max-width: 1250px;
}
.hero {
    background: linear-gradient(120deg,#102944,#091827);
    border:1px solid #23415e;
    border-radius:18px;
    padding:22px 24px;
    margin-bottom:18px;
}
.hero h1 {
    margin:0;
    color:#f5f8fc;
    font-size:2rem;
}
.hero p { color:#a9bfd4; }
.panel {
    background:#0d2033;
    border:1px solid #203b55;
    border-radius:15px;
    padding:17px;
    margin:8px 0;
}
.buy {
    color:#25d887;
    font-size:2rem;
    font-weight:850;
}
.sell {
    color:#ff5c68;
    font-size:2rem;
    font-weight:850;
}
.wait {
    color:#ffc857;
    font-size:2rem;
    font-weight:850;
}
.muted { color:#a9bfd4; }
div.stButton > button {
    border-radius:10px;
    min-height:3rem;
    font-weight:750;
    background:#176b50;
    color:white;
    border:1px solid #27966f;
}
[data-testid="stMetric"] {
    background:#0d2033;
    padding:12px;
    border:1px solid #203b55;
    border-radius:12px;
}
</style>
""", unsafe_allow_html=True)

st.markdown("""
<div class="hero">
<h1>🦁 DONCULLER-TRADE47</h1>
<p>AI CHART ANALYZER · SYNTHETIC & FOREX · V2</p>
</div>
""", unsafe_allow_html=True)

API_KEY = os.getenv("OPENROUTER_API_KEY", "").strip()
MODEL = os.getenv("OPENROUTER_MODEL", "openrouter/free").strip()
API_URL = "https://openrouter.ai/api/v1/chat/completions"

SYNTHETIC_ASSETS = [
    "Boom 1000", "Crash 1000",
    "Boom 500", "Crash 500",
    "Boom 300", "Crash 300",
    "Boom 100", "Crash 100",
    "Boom 50", "Crash 50",
    "Jump Index 50", "Jump Index",
    "Step Index"
]

FOREX_ASSETS = ["EUR/USD", "GBP/USD", "XAU/USD"]

with st.sidebar:
    st.header("⚙️ Configuração")

    market = st.radio(
        "Mercado",
        ["Índices sintéticos", "Forex"]
    )

    assets = (
        SYNTHETIC_ASSETS
        if market == "Índices sintéticos"
        else FOREX_ASSETS
    )

    asset
