import os
import re
import smtplib
import time
import logging
import html
import hmac
from logging.handlers import RotatingFileHandler
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
from dotenv import load_dotenv
from database import connect_db, ensure_schema, table_exists, get_setting


st.set_page_config(
    page_title="Centro de Gestión - Agente de Triaje Bancario",
    page_icon="🏦",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ============================================================
# CONFIGURACIÓN GENERAL
# ============================================================
load_dotenv()
EMAIL_USER = get_setting("EMAIL_USER")
EMAIL_PASS = get_setting("EMAIL_PASS")
SMTP_MAX_RETRIES = int(get_setting("SMTP_MAX_RETRIES", "3"))
RETRY_BASE_SECONDS = float(get_setting("RETRY_BASE_SECONDS", "2"))
LOG_DIR = get_setting("LOG_DIR", "logs") or "logs"

EMAIL_DIMAS = get_setting("EMAIL_DIMAS", "alquimidmj2@hotmail.com")
EMAIL_PABLO = get_setting("EMAIL_PABLO", "Pab_gonzalez@hotmail.com")
EMAIL_DANIEL = get_setting("EMAIL_DANIEL", "daniel.calderon@banco.com")
EMAIL_CRISTOBAL = get_setting("EMAIL_CRISTOBAL", "casilva5@estudiante.uc.cl")

# Credenciales de acceso al dashboard.
# Local: .env. En Streamlit Community Cloud: Settings > Secrets.
DASH_PASS_DIMAS = get_setting("DASH_PASS_DIMAS")
DASH_PASS_PABLO = get_setting("DASH_PASS_PABLO")
DASH_PASS_DANIEL = get_setting("DASH_PASS_DANIEL")
DASH_PASS_CRISTOBAL = get_setting("DASH_PASS_CRISTOBAL")
DASH_PASS_ADMIN = get_setting("DASH_PASS_ADMIN")

os.makedirs(LOG_DIR, exist_ok=True)
logger = logging.getLogger("dashboard_triage")
logger.setLevel(logging.INFO)
if not logger.handlers:
    handler = RotatingFileHandler(
        os.path.join(LOG_DIR, "dashboard.log"),
        maxBytes=1_000_000,
        backupCount=3,
        encoding="utf-8",
    )
    handler.setFormatter(logging.Formatter("%(asctime)s | %(levelname)s | %(message)s"))
    logger.addHandler(handler)

# Correos de responsables utilizados por el prototipo.
CORREOS_RESPONSABLES = {
    "Dimas Juárez S.": EMAIL_DIMAS,
    "Pablo González M.": EMAIL_PABLO,
    "Daniel Calderón Z.": EMAIL_DANIEL,
    "Cristóbal Silva L.": EMAIL_CRISTOBAL,
}

# Usuarios del dashboard y alcance de información.
# Un ejecutivo ve únicamente los casos donde figura como responsable asignado.
# El administrador puede revisar todos los casos del prototipo.
USUARIOS_DASHBOARD = {
    "Dimas Juárez S.": {
        "nombre": "Dimas Juárez S.",
        "rol": "EJECUTIVO",
        "password": DASH_PASS_DIMAS,
    },
    "Pablo González M.": {
        "nombre": "Pablo González M.",
        "rol": "EJECUTIVO",
        "password": DASH_PASS_PABLO,
    },
    "Daniel Calderón Z.": {
        "nombre": "Daniel Calderón Z.",
        "rol": "EJECUTIVO",
        "password": DASH_PASS_DANIEL,
    },
    "Cristóbal Silva L.": {
        "nombre": "Cristóbal Silva L.",
        "rol": "EJECUTIVO",
        "password": DASH_PASS_CRISTOBAL,
    },
    "Administrador": {
        "nombre": "Administrador",
        "rol": "ADMIN",
        "password": DASH_PASS_ADMIN,
    },
}


RUTAS_REASIGNACION = {
    "Dimas - Seguridad / Fraude": ("Dimas Juárez S.", "Seguridad / Fraude"),
    "Dimas - Cumplimiento / Legal": ("Dimas Juárez S.", "Cumplimiento / Legal"),
    "Dimas - Seguridad / Cumplimiento-Legal": (
        "Dimas Juárez S.",
        "Seguridad / Cumplimiento-Legal",
    ),
    "Pablo - Operaciones / Reclamos": ("Pablo González M.", "Operaciones / Reclamos"),
    "Daniel - Comercial / Solicitudes": ("Daniel Calderón Z.", "Comercial / Solicitudes"),
    "Daniel - Mesa de Ayuda / Consultas": ("Daniel Calderón Z.", "Mesa de Ayuda / Consultas"),
    "Cristóbal - Experiencia de Clientes": ("Cristóbal Silva L.", "Experiencia de Clientes"),
    "Cristóbal - Recepción General": ("Cristóbal Silva L.", "Recepción General"),
}

CATEGORIAS = ["FRAUDE", "RECLAMO", "SOLICITUD", "CONSULTA", "FELICITACION", "OTRO"]
SENTIMIENTOS = ["ENOJADO", "FRUSTRADO", "ANSIOSO", "NEUTRAL", "SATISFECHO"]

NOMBRES_ESTADO = {
    "RECIBIDO": "Recibido",
    "CLASIFICADO": "Clasificado",
    "RESPUESTA_CLIENTE_ENVIADA": "Cliente notificado",
    "ASIGNADO_HITL": "Asignado al ejecutivo",
    "EN_GESTION": "En gestión",
    "RESUELTO": "Resuelto",
    "CERRADO": "Cerrado",
    "IGNORADO": "Ignorado por filtro",
    "ERROR_IA": "Error de IA",
    "ERROR_ENVIO_CLIENTE": "Error al notificar cliente",
    "ERROR_RESPUESTA_CLIENTE": "Error al generar respuesta",
    "ERROR_ENVIO_RESPONSABLE": "Error al notificar ejecutivo",
}

NOMBRES_SLA = {
    "EN PLAZO": "En plazo",
    "POR VENCER": "Por vencer",
    "VENCIDO": "Fuera de plazo",
    "CUMPLIDO": "Cumplido",
    "SIN SLA": "Sin plazo definido",
}


# ============================================================
# ESTILO VISUAL
# ============================================================
st.markdown(
    """
    <style>
    .block-container {
        padding-top: 1.4rem;
        padding-bottom: 2.5rem;
        max-width: 1500px;
    }
    h1 {font-size: 2.0rem !important; margin-bottom: 0.2rem !important;}
    h2 {font-size: 1.45rem !important; margin-top: 0.8rem !important;}
    h3 {font-size: 1.15rem !important;}
    .kpi-card {
        background: white;
        border: 1px solid #E5E7EB;
        border-radius: 12px;
        padding: 14px 16px;
        min-height: 105px;
        box-shadow: 0 1px 2px rgba(0,0,0,0.04);
    }
    .kpi-label {font-size: 0.87rem; color: #667085; margin-bottom: 3px;}
    .kpi-value {font-size: 1.75rem; font-weight: 700; color: #1F2937; line-height: 1.15;}
    .kpi-help {font-size: 0.78rem; color: #98A2B3; margin-top: 6px; line-height: 1.25;}
    .info-card {
        background: #F8FAFC;
        border: 1px solid #E2E8F0;
        border-radius: 12px;
        padding: 15px 17px;
        margin-bottom: 10px;
    }
    .info-title {font-size: 0.83rem; color: #64748B; font-weight: 600; margin-bottom: 2px;}
    .info-value {font-size: 1rem; color: #0F172A; margin-bottom: 11px; word-break: break-word;}
    .badge {
        display: inline-block;
        border-radius: 999px;
        padding: 5px 10px;
        margin-right: 6px;
        margin-bottom: 6px;
        font-size: 0.82rem;
        font-weight: 600;
        border: 1px solid #D0D5DD;
        background: #F9FAFB;
        color: #344054;
    }
    .case-title {font-size: 1.6rem; font-weight: 750; color: #101828; margin-bottom: 8px;}
    .section-note {color: #667085; font-size: 0.90rem; margin-top: -6px; margin-bottom: 12px;}
    .workflow-card {
        background: #FFFFFF;
        border: 1px solid #DCE3EA;
        border-radius: 14px;
        padding: 18px 20px;
        margin-top: 8px;
        margin-bottom: 14px;
    }
    .workflow-step {
        border-radius: 10px;
        padding: 10px 12px;
        margin-bottom: 8px;
        border: 1px solid #E5E7EB;
        background: #F8FAFC;
        color: #344054;
        font-size: 0.92rem;
    }
    .workflow-step-done {
        background: #ECFDF3;
        border-color: #ABEFC6;
        color: #067647;
    }
    .workflow-step-current {
        background: #EFF8FF;
        border-color: #B2DDFF;
        color: #175CD3;
        font-weight: 700;
    }
    .workflow-step-pending {
        background: #F9FAFB;
        border-color: #EAECF0;
        color: #667085;
    }
    .next-action {
        background: #EFF8FF;
        border-left: 5px solid #2E90FA;
        border-radius: 10px;
        padding: 14px 16px;
        margin: 12px 0 16px 0;
    }
    div[data-testid="stDataFrame"] {border: 1px solid #E5E7EB; border-radius: 10px; overflow: hidden;}
    div.stButton > button {border-radius: 9px; font-weight: 600;}
    .case-summary-grid {
        display:grid;
        grid-template-columns:1.35fr 1fr .8fr 1.15fr 1.1fr;
        gap:10px;
        border:1px solid #E5E7EB;
        border-radius:12px;
        padding:12px 15px;
        margin:8px 0 12px 0;
        background:#FFFFFF;
        align-items:center;
    }
    .case-summary-item {min-width:0;}
    .case-summary-label {color:#667085;font-size:.76rem;margin-bottom:3px;}
    .case-summary-value {font-weight:700;color:#101828;white-space:normal;word-break:break-word;}
    .case-summary-sub {color:#667085;font-size:.82rem;white-space:normal;word-break:break-word;}
    .hover-info {
        position:relative; display:inline-block; margin-left:4px; cursor:help;
        color:#667085; font-weight:700; font-size:.84rem;
    }
    .hover-info .hover-box {
        visibility:hidden; opacity:0; transition:opacity .12s ease;
        position:absolute; z-index:9999; left:50%; top:1.35rem; transform:translateX(-50%);
        width:300px; max-width:70vw; background:#101828; color:#FFFFFF;
        text-align:left; font-weight:400; font-size:.78rem; line-height:1.35;
        padding:10px 12px; border-radius:8px; box-shadow:0 8px 24px rgba(0,0,0,.18);
        pointer-events:none; white-space:normal;
    }
    .hover-info:hover .hover-box {visibility:visible;opacity:1;}
    @media (max-width: 950px) {
        .case-summary-grid {grid-template-columns:1fr 1fr;}
    }
    </style>
    """,
    unsafe_allow_html=True,
)


# Capa visual nueva: identidad propia, inspirada en una interfaz bancaria sobria.
st.markdown(
    """
    <style>
    :root {
        --app-primary: #173B7A;
        --app-primary-2: #2E56A6;
        --app-accent: #3D6FE8;
        --app-bg: #F4F7FB;
        --app-card: #FFFFFF;
        --app-text: #17233A;
        --app-muted: #738099;
        --app-border: #DFE6F0;
    }
    .stApp {background: var(--app-bg); color: var(--app-text);}
    [data-testid="stSidebar"] {
        background: #FFFFFF;
        border-right: 1px solid var(--app-border);
    }
    [data-testid="stSidebar"] .block-container {padding-top: 1.15rem;}
    .block-container {padding-top: 1.15rem; max-width: 1550px;}
    .app-topbar {
        background: linear-gradient(100deg, var(--app-primary) 0%, var(--app-primary-2) 100%);
        color: #FFFFFF;
        border-radius: 18px;
        padding: 20px 24px;
        margin: 0 0 18px 0;
        box-shadow: 0 10px 26px rgba(23,59,122,.12);
    }
    .app-topbar-title {font-size: 1.45rem; font-weight: 800; line-height: 1.15;}
    .app-topbar-sub {font-size: .90rem; opacity: .83; margin-top: 5px;}
    .app-topbar-user {font-size: .82rem; opacity: .92; margin-top: 8px;}
    .sidebar-brand {padding: .35rem .1rem .9rem .1rem;}
    .sidebar-brand-title {font-size: 1.08rem; font-weight: 800; color: var(--app-primary);}
    .sidebar-brand-sub {font-size: .80rem; color: var(--app-muted); margin-top: 3px;}
    .section-note {color: var(--app-muted); margin-top: -2px; margin-bottom: 14px;}
    .kpi-card {
        border: 1px solid var(--app-border) !important;
        border-radius: 16px !important;
        box-shadow: 0 4px 14px rgba(34,52,84,.045) !important;
        min-height: 116px !important;
    }
    .info-card, .case-summary {
        border-color: var(--app-border) !important;
        border-radius: 16px !important;
    }
    .stButton > button {border-radius: 10px; font-weight: 700;}
    div[data-testid="stDataFrame"] {border-radius: 14px; overflow: hidden;}
    .home-action {
        background:#FFFFFF;
        border:1px solid var(--app-border);
        border-radius:16px;
        padding:16px 18px;
        margin-bottom:12px;
    }
    .home-action-title {font-weight:800; color:var(--app-text); margin-bottom:4px;}
    .home-action-copy {font-size:.86rem; color:var(--app-muted);}

    .home-case-card {
        background:#FFFFFF;
        border:1px solid var(--app-border);
        border-radius:18px;
        padding:18px 20px;
        margin:14px 0 14px 0;
        box-shadow:0 6px 18px rgba(34,52,84,.045);
    }
    .home-case-head {
        display:grid;
        grid-template-columns: .9fr 1.25fr 1fr .8fr 1.2fr 1.15fr;
        gap:12px;
        align-items:start;
    }
    .home-case-cell {min-width:0;}
    .home-case-label {
        color:var(--app-muted);
        font-size:.74rem;
        font-weight:700;
        text-transform:uppercase;
        letter-spacing:.035em;
        margin-bottom:4px;
    }
    .home-case-value {
        color:var(--app-text);
        font-size:1rem;
        font-weight:800;
        line-height:1.25;
        overflow-wrap:anywhere;
    }
    .home-case-sub {
        color:var(--app-muted);
        font-size:.80rem;
        line-height:1.35;
        margin-top:3px;
        overflow-wrap:anywhere;
    }
    .home-message-title {
        font-size:.88rem;
        font-weight:800;
        color:var(--app-text);
        margin-bottom:4px;
    }
    .home-message-meta {
        color:#667085;
        font-size:.78rem;
        margin-bottom:9px;
        line-height:1.4;
    }
    .home-message-card {
        background:#FFFFFF;
        border:1px solid #DDE5F0;
        border-radius:16px;
        padding:16px 18px;
        min-height:250px;
        box-shadow:0 4px 14px rgba(34,52,84,.045);
    }
    .home-message-body {
        background:#FFFFFF;
        color:#17233A;
        border:1px solid #E3E8F0;
        border-radius:12px;
        padding:14px 15px;
        margin-top:10px;
        min-height:170px;
        max-height:310px;
        overflow:auto;
        white-space:pre-wrap;
        overflow-wrap:anywhere;
        font-family:"Segoe UI", Arial, sans-serif;
        font-size:.90rem;
        line-height:1.55;
    }

    /* Correos y respuestas: contraste alto y fondo blanco real */
    .home-message-card {
        background:#FFFFFF !important;
        color:#17233A !important;
    }
    .home-message-card * {
        color:#17233A !important;
    }
    .home-message-body {
        background:#FFFFFF !important;
        color:#17233A !important;
        -webkit-text-fill-color:#17233A !important;
    }
    div[data-testid="stTextArea"] textarea,
    div[data-testid="stTextArea"] textarea:disabled {
        background:#FFFFFF !important;
        color:#17233A !important;
        -webkit-text-fill-color:#17233A !important;
        opacity:1 !important;
        border:1px solid #D7E0EC !important;
        box-shadow:none !important;
    }
    div[data-testid="stTextArea"] textarea:disabled {
        cursor:default !important;
    }

    .priority-contact {
        display:grid;
        grid-template-columns:repeat(3,minmax(0,1fr));
        gap:10px 18px;
        margin-top:12px;
        padding-top:11px;
        border-top:1px solid #E7ECF3;
    }
    .priority-contact-item {min-width:0;}
    .priority-contact-label {
        font-size:.72rem;
        color:#7A8699;
        text-transform:uppercase;
        letter-spacing:.035em;
        font-weight:700;
        margin-bottom:2px;
    }
    .priority-contact-value {
        font-size:.88rem;
        color:#17233A;
        font-weight:650;
        overflow-wrap:anywhere;
    }
    @media (max-width: 1150px) {
        .home-case-head {grid-template-columns:1fr 1fr 1fr;}
    }
    @media (max-width: 760px) {
        .home-case-head {grid-template-columns:1fr 1fr;}
        .priority-contact {grid-template-columns:1fr;}
    }
    </style>
    """,
    unsafe_allow_html=True,
)


# Capa final de UX: oculta chrome de Streamlit y unifica acciones/controles.
st.markdown(
    """
    <style>
    #MainMenu,
    footer,
    [data-testid="stToolbar"],
    [data-testid="stDecoration"],
    [data-testid="stHeaderActionElements"] {
        display:none !important;
    }

    /* Conserva un header minimo para mantener disponible el control del sidebar */
    [data-testid="stHeader"] {
        height:3rem !important;
        min-height:3rem !important;
        background:transparent !important;
    }

    /* Controles nativos del sidebar. Streamlit ha cambiado estos test-id entre versiones. */
    [data-testid="stSidebarCollapseButton"],
    [data-testid="stSidebarCollapsedControl"],
    [data-testid="collapsedControl"],
    [data-testid="stExpandSidebarButton"],
    button[aria-label="Expand sidebar"],
    button[aria-label="Collapse sidebar"] {
        display:flex !important;
        visibility:visible !important;
        opacity:1 !important;
        pointer-events:auto !important;
        z-index:999999 !important;
    }

    /* Cuando el sidebar esta cerrado, fuerza a mostrar el boton de reapertura. */
    [data-testid="stExpandSidebarButton"],
    [data-testid="stSidebarCollapsedControl"],
    [data-testid="collapsedControl"] {
        position:fixed !important;
        top:.65rem !important;
        left:.75rem !important;
        min-width:2.5rem !important;
        width:2.5rem !important;
        height:2.5rem !important;
        align-items:center !important;
        justify-content:center !important;
        background:#FFFFFF !important;
        border:1px solid #D5DEEC !important;
        border-radius:10px !important;
        box-shadow:0 4px 14px rgba(23,59,122,.14) !important;
        color:#173B7A !important;
    }

    [data-testid="stExpandSidebarButton"] button,
    [data-testid="stSidebarCollapsedControl"] button,
    [data-testid="collapsedControl"] button,
    button[aria-label="Expand sidebar"] {
        display:flex !important;
        visibility:visible !important;
        opacity:1 !important;
        pointer-events:auto !important;
        color:#173B7A !important;
    }

    .block-container {padding-top:1rem !important;}
    .app-topbar {padding:15px 20px !important; border-radius:16px !important; margin-bottom:16px !important;}
    .app-topbar-title {font-size:1.32rem !important;}
    .app-topbar-status {float:right; font-size:.78rem; background:rgba(255,255,255,.14); border:1px solid rgba(255,255,255,.18); padding:6px 10px; border-radius:999px;}
    .stButton > button[kind="primary"], .stFormSubmitButton > button[kind="primary"] {
        background:#2456A6 !important; border-color:#2456A6 !important; color:white !important;
    }
    .stButton > button[kind="primary"]:hover, .stFormSubmitButton > button[kind="primary"]:hover {
        background:#173B7A !important; border-color:#173B7A !important;
    }
    .st-key-login_shell {
        background:#FFFFFF; border:1px solid #DFE6F0; border-radius:18px; padding:28px 30px 24px 30px;
        box-shadow:0 12px 34px rgba(23,59,122,.08);
    }
    .login-brand {
        background:linear-gradient(100deg,#173B7A 0%,#2E56A6 100%); color:white; border-radius:14px;
        padding:20px 22px; margin-bottom:20px;
    }
    .login-brand-title {font-size:1.35rem;font-weight:800;margin-bottom:4px;}
    .login-brand-sub {font-size:.88rem;opacity:.86;}
    .login-note {font-size:.78rem;color:#738099;text-align:center;margin-top:12px;}
    [class*="st-key-kpi_nav_"] button {
        white-space:pre-line !important; text-align:left !important; justify-content:flex-start !important;
        min-height:118px !important; padding:16px 17px !important; border-radius:16px !important;
        color:#17233A !important; box-shadow:0 4px 14px rgba(34,52,84,.045) !important; line-height:1.35 !important;
    }
    [class*="st-key-kpi_nav_"] button p {white-space:pre-line !important; text-align:left !important; width:100%;}
    [class*="st-key-kpi_nav_"] button:hover {box-shadow:0 8px 20px rgba(34,52,84,.11) !important; transform:translateY(-1px);}
    [class*="st-key-kpi_nav_"] button:disabled {opacity:.72 !important;}

    /* Colores funcionales de Inicio */
    .st-key-kpi_nav_pendientes button {
        background:#EAF2FF !important; border:1px solid #9EC1FF !important; color:#173B7A !important;
    }
    .st-key-kpi_nav_criticos button {
        background:#FDECEC !important; border:1px solid #F3A6A6 !important; color:#9B1C1C !important;
    }
    .st-key-kpi_nav_vencidos button {
        background:#FFF4D8 !important; border:1px solid #F2CA72 !important; color:#805B00 !important;
    }
    .st-key-kpi_nav_hitl button {
        background:#F2ECFF !important; border:1px solid #C9B4FF !important; color:#5B3AA8 !important;
    }

    /* Selector rápido, alineado junto a Pendientes */
    .st-key-home_case_selector {
        background:#E9F8F4 !important; border:1px solid #8FD8C6 !important; border-radius:16px !important;
        min-height:118px !important; padding:13px 14px 10px 14px !important;
        box-shadow:0 4px 14px rgba(34,52,84,.045) !important;
    }
    .st-key-home_case_selector [data-testid="stCaptionContainer"] p {
        color:#087A66 !important; font-weight:800 !important; letter-spacing:.035em !important;
    }
    .st-key-home_case_selector [data-baseweb="select"] > div {
        background:#FFFFFF !important; border-color:#69BEAA !important; min-height:48px !important;
    }
    .priority-card {background:#FFFFFF;border:1px solid #DFE6F0;border-radius:16px;padding:17px 18px;margin:8px 0 12px 0;}
    .priority-head {display:flex;justify-content:space-between;gap:12px;align-items:flex-start;flex-wrap:wrap;}
    .priority-ticket {font-size:1.12rem;font-weight:800;color:#17233A;}
    .priority-client {font-size:.88rem;color:#738099;margin-top:2px;}
    .tag {display:inline-block;border-radius:999px;padding:4px 9px;font-size:.74rem;font-weight:700;margin:0 5px 5px 0;}
    .tag-blue {background:#EAF1FF;color:#2456A6}.tag-red {background:#FDECEC;color:#B42318}.tag-amber {background:#FFF3D6;color:#946200}.tag-purple {background:#F0EBFF;color:#6941C6}.tag-green {background:#E9F8F1;color:#087A52}
    .age-text {font-size:.82rem;color:#667085;margin-top:9px;}
    .ia-label, .human-label {font-weight:800;border-radius:10px;padding:9px 12px;margin:10px 0 8px 0;}
    .ia-label {background:#EEF4FF;color:#2456A6;border-left:4px solid #3D6FE8;}
    .human-label {background:#F2F8F5;color:#087A52;border-left:4px solid #16A36A;}
    .compact-caption {font-size:.80rem;color:#738099;}
    @media (max-width:900px) {
        .st-key-login_shell {padding:20px 18px;}
        [class*="st-key-kpi_nav_"] button {min-height:94px !important;}
    }
    </style>
    """,
    unsafe_allow_html=True,
)


def kpi_card(label, value, help_text):
    st.markdown(
        f"""
        <div class="kpi-card">
            <div class="kpi-label">{label}</div>
            <div class="kpi-value">{value}</div>
            <div class="kpi-help">{help_text}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def formatear_antiguedad(valor):
    """Devuelve una antigüedad relativa legible a partir de una fecha/timestamp."""
    try:
        ts = pd.to_datetime(valor, errors="coerce")
        if pd.isna(ts):
            return "antigüedad no disponible"
        now = pd.Timestamp.now(tz=ts.tz) if getattr(ts, "tz", None) is not None else pd.Timestamp.now()
        delta = now - ts
        segundos = max(0, int(delta.total_seconds()))
        if segundos < 60:
            return f"hace {segundos} s"
        minutos = segundos // 60
        if minutos < 60:
            return f"hace {minutos} min"
        horas = minutos // 60
        if horas < 48:
            return f"hace {horas} h"
        dias = horas // 24
        return f"hace {dias} días"
    except Exception:
        return "antigüedad no disponible"


def formatear_duracion(minutos):
    if minutos is None:
        return "Sin datos"
    try:
        minutos = float(minutos)
    except Exception:
        return "Sin datos"
    if minutos < 1:
        return f"{max(1, round(minutos * 60))} s"
    if minutos < 60:
        return f"{minutos:.1f} min"
    horas = minutos / 60
    if horas < 48:
        return f"{horas:.1f} h"
    return f"{horas / 24:.1f} días"


def kpi_navegable(label, value, help_text, foco, key, disabled=False):
    """KPI de Inicio que también funciona como acceso directo a la bandeja."""
    with st.container(key=f"kpi_nav_{key}"):
        st.button(
            f"{label}\n{value}\n{help_text}",
            key=f"btn_kpi_nav_{key}",
            use_container_width=True,
            disabled=disabled,
            on_click=ir_a_bandeja,
            args=(foco,),
        )


def info_block(items):
    html = '<div class="info-card">'
    for label, value in items:
        html += f'<div class="info-title">{label}</div><div class="info-value">{value}</div>'
    html += "</div>"
    st.markdown(html, unsafe_allow_html=True)


def badge(text):
    return f'<span class="badge">{text}</span>'


# ============================================================
# BASE DE DATOS
# ============================================================
def conectar_db():
    return connect_db()


def tabla_existe():
    return table_exists()


def asegurar_columnas_v7():
    """Mantiene el esquema PostgreSQL compatible con agente y dashboard."""
    ensure_schema()


def cargar_casos():
    conexion = conectar_db()
    try:
        filas = conexion.execute("SELECT * FROM interacciones ORDER BY id DESC").fetchall()
        return pd.DataFrame(filas)
    finally:
        conexion.close()


def obtener_caso(row_id):
    conexion = conectar_db()
    fila = conexion.execute(
        "SELECT * FROM interacciones WHERE id = ?", (int(row_id),)
    ).fetchone()
    conexion.close()
    return dict(fila) if fila else None


def actualizar_estado(row_id, nuevo_estado):
    fecha = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    campos = ["estado = ?", "fecha_actualizacion_estado = ?"]
    valores = [nuevo_estado, fecha]

    if nuevo_estado == "EN_GESTION":
        campos.append("fecha_en_gestion = COALESCE(fecha_en_gestion, ?)")
        valores.append(fecha)
    elif nuevo_estado == "RESUELTO":
        campos.append("fecha_resolucion = COALESCE(fecha_resolucion, ?)")
        valores.append(fecha)
    elif nuevo_estado == "CERRADO":
        campos.append("fecha_cierre = COALESCE(fecha_cierre, ?)")
        valores.append(fecha)

    valores.append(int(row_id))
    conexion = conectar_db()
    conexion.execute(
        f"UPDATE interacciones SET {', '.join(campos)} WHERE id = ?",
        valores,
    )
    conexion.commit()
    conexion.close()


def guardar_nota(row_id, nota):
    conexion = conectar_db()
    conexion.execute(
        "UPDATE interacciones SET nota_ejecutivo = ?, fecha_actualizacion_estado = ? WHERE id = ?",
        (nota.strip(), datetime.now().strftime("%Y-%m-%d %H:%M:%S"), int(row_id)),
    )
    conexion.commit()
    conexion.close()


def confirmar_revision_ejecutivo(row_id):
    fecha = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    conexion = conectar_db()
    conexion.execute(
        """
        UPDATE interacciones
        SET revision_ejecutivo_confirmada = 1,
            fecha_revision_ejecutivo = ?,
            fecha_actualizacion_estado = ?
        WHERE id = ?
        """,
        (fecha, fecha, int(row_id)),
    )
    conexion.commit()
    conexion.close()


def guardar_validacion_guardrails(
    row_id,
    validacion_prompt,
    validacion_ofensivo,
    validacion_amenaza,
    comentario,
):
    fecha = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    conexion = conectar_db()
    conexion.execute(
        """
        UPDATE interacciones
        SET validacion_prompt_injection = ?,
            validacion_ofensivo = ?,
            validacion_amenaza = ?,
            comentario_validacion_guardrail = ?,
            fecha_validacion_guardrail = ?,
            fecha_actualizacion_estado = ?
        WHERE id = ?
        """,
        (
            validacion_prompt,
            validacion_ofensivo,
            validacion_amenaza,
            comentario.strip(),
            fecha,
            fecha,
            int(row_id),
        ),
    )
    conexion.commit()
    conexion.close()


def reasignar_caso(row_id, responsable, area, correo):
    fecha = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    conexion = conectar_db()
    conexion.execute(
        """
        UPDATE interacciones
        SET responsable_asignado = ?, area_derivada = ?, correo_responsable_asignado = ?,
            fecha_ultima_reasignacion = ?, fecha_actualizacion_estado = ?,
            estado_notificacion_reasignacion = 'PENDIENTE',
            detalle_notificacion_reasignacion = NULL
        WHERE id = ?
        """,
        (responsable, area, correo, fecha, fecha, int(row_id)),
    )
    conexion.commit()
    conexion.close()


def registrar_resultado_reasignacion(row_id, estado, detalle):
    fecha = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    conexion = conectar_db()
    conexion.execute(
        """
        UPDATE interacciones
        SET estado_notificacion_reasignacion = ?,
            detalle_notificacion_reasignacion = ?,
            fecha_notificacion_reasignacion = ?
        WHERE id = ?
        """,
        (estado, str(detalle or ""), fecha, int(row_id)),
    )
    conexion.commit()
    conexion.close()


def enviar_correo_smtp_dashboard(destinatario, asunto, cuerpo):
    if not EMAIL_USER or not EMAIL_PASS:
        return False, "Faltan EMAIL_USER o EMAIL_PASS en .env"

    # Sandbox coherente con el agente: destinos ficticios @banco.com se
    # redirigen a EMAIL_USER y quedan identificados como simulación.
    es_ficticio = destinatario.lower().endswith("@banco.com")
    destinatario_real = EMAIL_USER if es_ficticio else destinatario
    asunto_real = f"[SIMULACIÓN -> {destinatario}] {asunto}" if es_ficticio else asunto

    msg = MIMEMultipart()
    msg["From"] = EMAIL_USER
    msg["To"] = destinatario_real
    msg["Subject"] = asunto_real
    msg["X-Agente-Triage"] = "dashboard-v7"
    msg.attach(MIMEText(cuerpo, "plain", "utf-8"))

    ultimo_error = ""
    for intento in range(1, SMTP_MAX_RETRIES + 1):
        try:
            with smtplib.SMTP_SSL("smtp.gmail.com", 465, timeout=20) as servidor:
                servidor.login(EMAIL_USER, EMAIL_PASS)
                rechazados = servidor.sendmail(EMAIL_USER, destinatario_real, msg.as_string())
            if rechazados:
                raise RuntimeError(f"SMTP rechazó destinatarios: {rechazados}")
            detalle = f"Aceptado por smtp.gmail.com para {destinatario_real}"
            if es_ficticio:
                detalle += f" (simulación del destino lógico {destinatario})"
            logger.info("REASSIGN_SMTP_OK | to=%s | attempt=%s", destinatario_real, intento)
            return True, detalle
        except Exception as exc:
            ultimo_error = str(exc)
            logger.warning("REASSIGN_SMTP_RETRY | to=%s | attempt=%s/%s | error=%s", destinatario_real, intento, SMTP_MAX_RETRIES, ultimo_error)
            if intento < SMTP_MAX_RETRIES:
                time.sleep(RETRY_BASE_SECONDS * (2 ** (intento - 1)))

    logger.error("REASSIGN_SMTP_FAIL | to=%s | error=%s", destinatario_real, ultimo_error)
    return False, f"No fue aceptado por SMTP: {ultimo_error}"


def construir_notificacion_reasignacion(caso, responsable, area):
    ticket = caso.get("ticket_id") or f"CASO-{caso.get('id')}"
    cuerpo = f"""Estimado/a {responsable},

Se te ha reasignado un caso en el prototipo de triaje bancario.

Ticket: {ticket}
Categoría: {caso.get('categoria') or 'N/D'}
Prioridad: {caso.get('prioridad') or 'N/D'}
Área asignada: {area}
Cliente: {caso.get('nombre_cliente') or 'N/D'} ({extraer_email(caso.get('remitente'))})
Asunto: {caso.get('asunto') or 'Sin asunto'}

Mensaje original:
--------------------------------------------------
{caso.get('cuerpo_original') or 'Sin contenido almacenado.'}
--------------------------------------------------

Acción requerida: revisar el caso en el dashboard y continuar la gestión bajo criterio humano.

Atentamente,
Centro de Gestión de Casos - Prototipo V7"""
    asunto = f"[REASIGNACIÓN] [{ticket}] {caso.get('categoria') or 'CASO'} · {caso.get('prioridad') or 'N/D'}"
    return asunto, cuerpo


def reasignar_y_notificar(caso, responsable, area, correo):
    reasignar_caso(caso["id"], responsable, area, correo)
    asunto, cuerpo = construir_notificacion_reasignacion(caso, responsable, area)
    ok, detalle = enviar_correo_smtp_dashboard(correo, asunto, cuerpo)
    registrar_resultado_reasignacion(
        caso["id"], "ACEPTADO_SMTP" if ok else "ERROR", detalle
    )
    logger.info(
        "CASE_REASSIGN | ticket=%s | responsable=%s | area=%s | mail_status=%s",
        caso.get("ticket_id"), responsable, area, "OK" if ok else "ERROR"
    )
    return ok, detalle


def guardar_feedback(
    row_id,
    feedback_clasificacion,
    categoria_corregida,
    sentimiento_corregido,
    ruteo_correcto,
    comentario_feedback,
):
    conexion = conectar_db()
    conexion.execute(
        """
        UPDATE interacciones
        SET feedback_clasificacion = ?, categoria_corregida = ?,
            sentimiento_corregido = ?, ruteo_correcto = ?,
            comentario_feedback = ?, fecha_feedback = ?
        WHERE id = ?
        """,
        (
            feedback_clasificacion,
            categoria_corregida,
            sentimiento_corregido,
            ruteo_correcto,
            comentario_feedback.strip(),
            datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            int(row_id),
        ),
    )
    conexion.commit()
    conexion.close()


# ============================================================
# FUNCIONES DE PRESENTACIÓN Y MÉTRICAS
# ============================================================
def parse_fecha(valor):
    if valor is None or (isinstance(valor, float) and pd.isna(valor)) or not str(valor).strip():
        return None
    try:
        return datetime.strptime(str(valor), "%Y-%m-%d %H:%M:%S")
    except ValueError:
        return None


def calcular_estado_sla(fila):
    limite = parse_fecha(fila.get("fecha_limite_sla"))
    if not limite:
        return "SIN SLA"

    estado = str(fila.get("estado") or "")
    cierre_ref = parse_fecha(fila.get("fecha_resolucion")) or parse_fecha(fila.get("fecha_cierre"))

    if estado in {"RESUELTO", "CERRADO"} and cierre_ref:
        return "CUMPLIDO" if cierre_ref <= limite else "VENCIDO"

    ahora = datetime.now()
    if ahora > limite:
        return "VENCIDO"

    try:
        objetivo = int(fila.get("sla_objetivo_min"))
    except (TypeError, ValueError):
        objetivo = None

    minutos_restantes = (limite - ahora).total_seconds() / 60
    umbral = max(15, objetivo * 0.25) if objetivo else 30
    return "POR VENCER" if minutos_restantes <= umbral else "EN PLAZO"


def formato_minutos(minutos):
    try:
        minutos = int(minutos)
    except (TypeError, ValueError):
        return "No disponible"
    if minutos < 60:
        return f"{minutos} min"
    horas, resto = divmod(minutos, 60)
    return f"{horas} h {resto} min" if resto else f"{horas} h"


def minutos_entre(inicio, fin):
    a = parse_fecha(inicio)
    b = parse_fecha(fin)
    if not a or not b:
        return None
    return (b - a).total_seconds() / 60


def construir_guardrail(fila):
    if int(fila.get("amenaza_detectada") or 0) == 1:
        return "Amenaza"
    if int(fila.get("prompt_injection") or 0) == 1:
        return "Prompt injection"
    if int(fila.get("ofensivo_detectado") or 0) == 1:
        return "Lenguaje ofensivo"
    if int(fila.get("revision_baja_confianza") or 0) == 1:
        return "Baja confianza"
    return "Ninguno"


def extraer_email(remitente):
    texto = str(remitente or "")
    encontrados = re.findall(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}", texto)
    return encontrados[-1] if encontrados else texto.strip() or "No disponible"


def nombre_estado(estado):
    return NOMBRES_ESTADO.get(str(estado or ""), str(estado or "No disponible").replace("_", " ").title())


def nombre_sla(valor):
    return NOMBRES_SLA.get(valor, valor)


def correo_responsable(nombre):
    return CORREOS_RESPONSABLES.get(str(nombre or ""), "No configurado")


def estado_envio_visible(valor, enviado_flag=0):
    estado = str(valor or "").upper()
    if estado == "ACEPTADO_SMTP" or int(enviado_flag or 0) == 1:
        return "Aceptado por SMTP"
    if estado == "ERROR":
        return "Error de envío"
    return "Pendiente"


def guardrails_detectados(caso):
    detectados = []
    if int(caso.get("prompt_injection") or 0) == 1:
        detectados.append(("Prompt injection", "validacion_prompt_injection"))
    if int(caso.get("ofensivo_detectado") or 0) == 1:
        detectados.append(("Lenguaje ofensivo", "validacion_ofensivo"))
    if int(caso.get("amenaza_detectada") or 0) == 1:
        detectados.append(("Amenaza", "validacion_amenaza"))
    return detectados


def guardrails_validados(caso):
    detectados = guardrails_detectados(caso)
    if not detectados:
        return True
    for _, campo in detectados:
        if str(caso.get(campo) or "PENDIENTE").upper() == "PENDIENTE":
            return False
    return True


def evaluacion_ia_completa(caso):
    """La evaluación del agente se considera completa solo si el ejecutivo dejó una decisión explícita."""
    clasificacion = str(caso.get("feedback_clasificacion") or "PENDIENTE").upper()
    ruteo = str(caso.get("ruteo_correcto") or "PENDIENTE").upper()
    categoria = str(caso.get("categoria_corregida") or "").strip()
    sentimiento = str(caso.get("sentimiento_corregido") or "").strip()
    comentario = str(caso.get("comentario_feedback") or "").strip()
    return (
        clasificacion in {"CORRECTA", "INCORRECTA"}
        and ruteo in {"SI", "NO"}
        and bool(categoria)
        and bool(sentimiento)
        and bool(comentario)
    )


def pasos_gestion(caso):
    estado = str(caso.get("estado") or "")
    avanzado = estado in {"EN_GESTION", "RESUELTO", "CERRADO"}
    revision_ok = int(caso.get("revision_ejecutivo_confirmada") or 0) == 1 or avanzado
    alertas_ok = guardrails_validados(caso) or avanzado
    tomado = avanzado
    nota_ok = bool(str(caso.get("nota_ejecutivo") or "").strip()) or estado in {"RESUELTO", "CERRADO"}
    evaluacion_ok = evaluacion_ia_completa(caso) or estado in {"RESUELTO", "CERRADO"}
    gestion_y_evaluacion_ok = nota_ok and evaluacion_ok
    resuelto = estado in {"RESUELTO", "CERRADO"}
    cerrado = estado == "CERRADO"
    return [
        ("1. Revisar antecedentes", revision_ok),
        ("2. Validar alertas del agente", alertas_ok),
        ("3. Tomar el caso", tomado),
        ("4. Registrar gestión y evaluar la IA", gestion_y_evaluacion_ok),
        ("5. Marcar como resuelto", resuelto),
        ("6. Cerrar el caso", cerrado),
    ]


def paso_actual(caso):
    pasos = pasos_gestion(caso)
    for i, (_, hecho) in enumerate(pasos, start=1):
        if not hecho:
            return i
    return 7


def proxima_accion_guiada(caso):
    paso = paso_actual(caso)
    if paso == 1:
        return "Lee el mensaje del cliente, revisa la categoría, prioridad y ejecutivo asignado. Si todo está claro, confirma la revisión."
    if paso == 2:
        return "El agente activó una o más alertas. Indica si cada alerta es correcta o si fue un falso positivo."
    if paso == 3:
        return "Toma el caso para dejar registrado que comenzaste a gestionarlo."
    if paso == 4:
        return (
            "Registra brevemente qué hiciste y completa la evaluación del agente: "
            "clasificación, categoría correcta, sentimiento correcto, ruteo y comentario. "
            "La etapa 5 no se habilitará hasta guardar todo."
        )
    if paso == 5:
        return "La gestión y la evaluación de la IA ya están registradas. Si el problema fue solucionado, marca el caso como resuelto."
    if paso == 6:
        return "Si no quedan acciones pendientes, cierra el caso."
    return "El caso está cerrado. No requiere más acciones, salvo que aparezca nueva información."


def mostrar_barra_gestion(caso):
    """Muestra el flujo guiado al comienzo del detalle del caso."""
    st.markdown("### Gestión guiada del caso")
    st.caption("Sigue los pasos en orden. La web no habilita el cierre hasta completar la evaluación humana del agente.")
    pasos = pasos_gestion(caso)
    actual = paso_actual(caso)
    completados = sum(1 for _, hecho in pasos if hecho)
    progreso = completados / len(pasos)
    st.progress(progreso, text=f"Avance de la gestión: {completados} de {len(pasos)} pasos completados")

    html_pasos = '<div class="workflow-card">'
    for idx, (nombre_paso, hecho) in enumerate(pasos, start=1):
        if hecho:
            clase = "workflow-step workflow-step-done"
            icono = "✓"
        elif idx == actual:
            clase = "workflow-step workflow-step-current"
            icono = "→"
        else:
            clase = "workflow-step workflow-step-pending"
            icono = "○"
        html_pasos += f'<div class="{clase}">{icono} {nombre_paso}</div>'
    html_pasos += '</div>'
    st.markdown(html_pasos, unsafe_allow_html=True)
    st.markdown(
        f'<div class="next-action"><b>Qué debes hacer ahora:</b><br>{proxima_accion_guiada(caso)}</div>',
        unsafe_allow_html=True,
    )
    return actual




# ============================================================
# GESTIÓN COMPACTA / ASISTENTE PASO A PASO
# ============================================================
def mostrar_barra_gestion_compacta(caso):
    """Stepper horizontal compacto. Solo destaca el paso actual."""
    pasos = pasos_gestion(caso)
    actual = paso_actual(caso)
    completados = sum(1 for _, hecho in pasos if hecho)
    progreso = completados / len(pasos)

    st.markdown("### Gestión guiada")
    st.progress(progreso, text=f"{completados} de {len(pasos)} pasos completados")

    html = '<div style="display:flex;gap:7px;flex-wrap:wrap;margin:8px 0 12px 0;">'
    nombres_cortos = [
        "Revisar", "Validar alertas", "Tomar caso",
        "Gestionar + evaluar", "Resolver", "Cerrar"
    ]
    for idx, ((_, hecho), corto) in enumerate(zip(pasos, nombres_cortos), start=1):
        if hecho:
            fondo, borde, color, icono = "#ECFDF3", "#ABEFC6", "#067647", "✓"
        elif idx == actual:
            fondo, borde, color, icono = "#EFF8FF", "#84CAFF", "#175CD3", "→"
        else:
            fondo, borde, color, icono = "#F9FAFB", "#EAECF0", "#667085", "○"
        html += (
            f'<div style="flex:1;min-width:125px;background:{fondo};border:1px solid {borde};'
            f'color:{color};border-radius:9px;padding:8px 10px;font-size:0.82rem;font-weight:600;'
            f'text-align:center;white-space:nowrap;">{icono} {idx}. {corto}</div>'
        )
    html += '</div>'
    st.markdown(html, unsafe_allow_html=True)
    return actual


def _esc(valor):
    return html.escape(str(valor if valor is not None else ""), quote=True)


def _tooltip(contenido):
    return (
        '<span class="hover-info">ⓘ'
        f'<span class="hover-box">{_esc(contenido)}</span>'
        '</span>'
    )


def resumen_caso_compacto(caso):
    """Información operativa mínima; el detalle aparece al pasar el cursor por ⓘ."""
    estado = nombre_estado(caso.get("estado"))
    sla_tecnico = calcular_estado_sla(caso)
    plazo = nombre_sla(sla_tecnico)
    cliente = caso.get("nombre_cliente") or "Cliente sin nombre"
    correo = extraer_email(caso.get("remitente"))
    categoria = caso.get("categoria") or "N/D"
    prioridad = caso.get("prioridad") or "N/D"
    ejecutivo = caso.get("responsable_asignado") or "Sin asignar"
    area = caso.get("area_derivada") or "No disponible"
    asunto = caso.get("asunto") or "Sin asunto"
    fecha = caso.get("fecha_recepcion") or "No disponible"
    sentimiento = caso.get("sentimiento") or "N/D"
    guardrail = construir_guardrail(caso)
    conf = caso.get("confianza_modelo")
    conf_txt = f"{float(conf):.2f}" if conf is not None else "No disponible"
    correo_exec = caso.get("correo_responsable_asignado") or correo_responsable(ejecutivo)
    notif_exec = estado_envio_visible(
        caso.get("estado_envio_responsable"), caso.get("notificacion_responsable_enviada")
    )
    paso = paso_actual(caso)
    siguiente = proxima_accion_guiada(caso)
    sla_obj = formato_minutos(caso.get("sla_objetivo_min")) if caso.get("sla_objetivo_min") else "No definido"

    tip_cliente = f"Correo: {correo} | Asunto: {asunto} | Recibido: {fecha}"
    tip_categoria = (
        f"Categoría detectada: {categoria} | Sentimiento: {sentimiento} | "
        f"Confianza estimada: {conf_txt} | Alerta principal: {guardrail}"
    )
    tip_prioridad = (
        f"Prioridad: {prioridad} | SLA objetivo: {sla_obj} | Estado del plazo: {plazo}"
    )
    tip_ejecutivo = (
        f"{ejecutivo} | Área: {area} | Correo: {correo_exec} | Notificación: {notif_exec}"
    )
    tip_estado = (
        f"Estado actual: {estado} | Paso de gestión: {min(paso, 6)} de 6 | "
        f"Siguiente acción: {siguiente}"
    )

    st.markdown(
        f"""
        <div class="case-summary-grid">
          <div class="case-summary-item">
            <div class="case-summary-label">Cliente {_tooltip(tip_cliente)}</div>
            <div class="case-summary-value">{_esc(cliente)}</div>
            <div class="case-summary-sub">{_esc(correo)}</div>
          </div>
          <div class="case-summary-item">
            <div class="case-summary-label">Categoría {_tooltip(tip_categoria)}</div>
            <div class="case-summary-value">{_esc(categoria)}</div>
          </div>
          <div class="case-summary-item">
            <div class="case-summary-label">Prioridad {_tooltip(tip_prioridad)}</div>
            <div class="case-summary-value">{_esc(prioridad)}</div>
          </div>
          <div class="case-summary-item">
            <div class="case-summary-label">Ejecutivo {_tooltip(tip_ejecutivo)}</div>
            <div class="case-summary-value">{_esc(ejecutivo)}</div>
          </div>
          <div class="case-summary-item">
            <div class="case-summary-label">Estado / plazo {_tooltip(tip_estado)}</div>
            <div class="case-summary-value">{_esc(estado)} · {_esc(plazo)}</div>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_inicio_caso_detalle(caso, prefijo="inicio"):
    """Vista compacta del caso para Inicio, con mensaje y respuesta visibles."""
    ticket = caso.get("ticket_id") or f"ID {caso.get('id')}"
    cliente = caso.get("nombre_cliente") or "Cliente sin nombre"
    correo = extraer_email(caso.get("remitente")) or "Correo no disponible"
    categoria = caso.get("categoria") or "Sin categoría"
    prioridad = caso.get("prioridad") or "Sin prioridad"
    estado = nombre_estado(caso.get("estado"))
    ejecutivo = caso.get("responsable_asignado") or "Sin asignar"
    fecha = caso.get("fecha_recepcion") or "Fecha no disponible"
    asunto = caso.get("asunto") or "Sin asunto"
    area = caso.get("area_derivada") or "Área no disponible"
    mensaje = caso.get("cuerpo_original") or "Sin contenido almacenado."
    respuesta = caso.get("respuesta_cliente_texto") or "No hay respuesta almacenada para este caso."
    estado_respuesta = estado_envio_visible(
        caso.get("estado_envio_cliente"), caso.get("respuesta_cliente_enviada")
    )

    st.markdown(
        f"""
        <div class="home-case-card">
          <div class="home-case-head">
            <div class="home-case-cell">
              <div class="home-case-label">Ticket</div>
              <div class="home-case-value">{_esc(ticket)}</div>
              <div class="home-case-sub">{_esc(fecha)}</div>
            </div>
            <div class="home-case-cell">
              <div class="home-case-label">Cliente</div>
              <div class="home-case-value">{_esc(cliente)}</div>
              <div class="home-case-sub">{_esc(correo)}</div>
            </div>
            <div class="home-case-cell">
              <div class="home-case-label">Categoría</div>
              <div class="home-case-value">{_esc(categoria)}</div>
              <div class="home-case-sub">{_esc(asunto)}</div>
            </div>
            <div class="home-case-cell">
              <div class="home-case-label">Prioridad</div>
              <div class="home-case-value">{_esc(prioridad)}</div>
              <div class="home-case-sub">SLA: {_esc(nombre_sla(calcular_estado_sla(caso)))}</div>
            </div>
            <div class="home-case-cell">
              <div class="home-case-label">Estado</div>
              <div class="home-case-value">{_esc(estado)}</div>
              <div class="home-case-sub">{_esc(area)}</div>
            </div>
            <div class="home-case-cell">
              <div class="home-case-label">Ejecutivo</div>
              <div class="home-case-value">{_esc(ejecutivo)}</div>
              <div class="home-case-sub">Respuesta: {_esc(estado_respuesta)}</div>
            </div>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    col_cliente, col_respuesta = st.columns(2, gap="large")

    with col_cliente:
        st.markdown(
            f"""
            <div class="home-message-card">
                <div class="home-message-title">Correo recibido del cliente</div>
                <div class="home-message-meta">
                    <b>De:</b> {_esc(correo)}<br>
                    <b>Asunto:</b> {_esc(asunto)}<br>
                    <b>Recibido:</b> {_esc(fecha)}
                </div>
                <div class="home-message-body">{_esc(mensaje)}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    with col_respuesta:
        st.markdown(
            f"""
            <div class="home-message-card">
                <div class="home-message-title">Respuesta enviada al cliente</div>
                <div class="home-message-meta">
                    <b>Estado de envío:</b> {_esc(estado_respuesta)}
                </div>
                <div class="home-message-body">{_esc(respuesta)}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )


def sugerencia_gestion(caso):
    """Propone una nota basada solo en hechos ya registrados; el ejecutivo debe validarla."""
    categoria = str(caso.get("categoria") or "OTRO").upper()
    ticket = caso.get("ticket_id") or f"CASO-{caso.get('id')}"
    area = caso.get("area_derivada") or "el área asignada"

    bases = {
        "FRAUDE": "Revisé los antecedentes del posible fraude informado y mantuve el caso en revisión por el área asignada, sin confirmar aún la existencia de fraude.",
        "RECLAMO": "Revisé el reclamo y los antecedentes aportados por el cliente para continuar su gestión.",
        "SOLICITUD": "Revisé la solicitud del cliente y los antecedentes disponibles para continuar su evaluación.",
        "CONSULTA": "Revisé la consulta del cliente y los antecedentes disponibles para orientar su gestión.",
        "FELICITACION": "Revisé el mensaje de felicitación y confirmé que quedó registrado y derivado al responsable correspondiente.",
        "OTRO": "Revisé el mensaje y los antecedentes disponibles para determinar la gestión que corresponde.",
    }
    partes = [bases.get(categoria, bases["OTRO"])]

    # Añade solo hechos verificables del flujo.
    if int(caso.get("amenaza_detectada") or 0):
        val = str(caso.get("validacion_amenaza") or "PENDIENTE").replace("_", " ").lower()
        partes.append(f"La alerta de amenaza fue revisada por el ejecutivo y quedó como {val}.")
    if int(caso.get("ofensivo_detectado") or 0):
        val = str(caso.get("validacion_ofensivo") or "PENDIENTE").replace("_", " ").lower()
        partes.append(f"La alerta de lenguaje ofensivo fue revisada por el ejecutivo y quedó como {val}.")
    if int(caso.get("prompt_injection") or 0):
        val = str(caso.get("validacion_prompt_injection") or "PENDIENTE").replace("_", " ").lower()
        partes.append(f"La alerta de posible manipulación de instrucciones fue revisada y quedó como {val}.")

    if estado_envio_visible(caso.get("estado_envio_cliente"), caso.get("respuesta_cliente_enviada")) == "Aceptado por SMTP":
        partes.append("Verifiqué que la notificación al cliente fue aceptada por el servidor de correo.")

    partes.append(f"El ticket {ticket} permanece bajo criterio humano en {area} hasta completar la gestión.")
    return " ".join(partes)


def sugerencia_evaluacion(caso):
    """Comentario sugerido de evaluación; describe lo detectado sin darlo por correcto automáticamente."""
    categoria = caso.get("categoria") or "N/D"
    sentimiento = caso.get("sentimiento") or "N/D"
    ejecutivo = caso.get("responsable_asignado") or "Sin asignar"
    area = caso.get("area_derivada") or "N/D"
    partes = [
        f"El agente detectó la categoría {categoria} y el sentimiento {sentimiento}.",
        f"El caso fue asignado a {ejecutivo}, área {area}.",
    ]
    alertas = []
    if int(caso.get("amenaza_detectada") or 0):
        alertas.append(f"amenaza: {caso.get('validacion_amenaza') or 'PENDIENTE'}")
    if int(caso.get("ofensivo_detectado") or 0):
        alertas.append(f"lenguaje ofensivo: {caso.get('validacion_ofensivo') or 'PENDIENTE'}")
    if int(caso.get("prompt_injection") or 0):
        alertas.append(f"posible manipulación de instrucciones: {caso.get('validacion_prompt_injection') or 'PENDIENTE'}")
    if alertas:
        partes.append("Validación de alertas: " + "; ".join(alertas) + ".")
    else:
        partes.append("No se registraron alertas especiales en este caso.")
    partes.append("Confirma o corrige estos elementos antes de resolver el ticket.")
    return " ".join(partes)


def renderizar_accion_actual(caso, actual):
    """Muestra únicamente los controles necesarios para el paso actual."""
    with st.container(border=True):
        st.markdown(f"#### Paso actual · {actual if actual <= 6 else 6}")
        st.caption(proxima_accion_guiada(caso))

        # PASO 1: revisar antecedentes
        if actual == 1:
            st.markdown("**Revisa el mensaje y confirma que entendiste el caso.**")
            st.text_area(
                "Mensaje del cliente",
                value=caso.get("cuerpo_original") or "Sin contenido almacenado.",
                height=155,
                disabled=True,
                key=f"mensaje_p1_{caso['id']}",
            )
            if st.button(
                "✓ Antecedentes revisados · continuar",
                type="primary",
                use_container_width=True,
                key=f"confirmar_revision_{caso['id']}",
            ):
                confirmar_revision_ejecutivo(caso["id"])
                st.rerun()

        # PASO 2: validar alertas
        elif actual == 2:
            st.markdown("**Valida las alertas que activó el agente.**")
            detectados = guardrails_detectados(caso)
            opciones_alerta = ["PENDIENTE", "CONFIRMADA", "FALSO_POSITIVO"]

            val_prompt = str(caso.get("validacion_prompt_injection") or "PENDIENTE")
            val_ofensivo = str(caso.get("validacion_ofensivo") or "PENDIENTE")
            val_amenaza = str(caso.get("validacion_amenaza") or "PENDIENTE")

            cols = st.columns(max(1, len(detectados)))
            for idx, (etiqueta, campo) in enumerate(detectados):
                actual_val = str(caso.get(campo) or "PENDIENTE")
                with cols[idx]:
                    seleccionado = st.radio(
                        etiqueta,
                        opciones_alerta,
                        index=opciones_alerta.index(actual_val) if actual_val in opciones_alerta else 0,
                        horizontal=False,
                        key=f"guardrail_compacto_{campo}_{caso['id']}",
                    )
                if campo == "validacion_prompt_injection":
                    val_prompt = seleccionado
                elif campo == "validacion_ofensivo":
                    val_ofensivo = seleccionado
                elif campo == "validacion_amenaza":
                    val_amenaza = seleccionado

            comentario_guardrail = st.text_input(
                "Comentario (opcional, recomendado si marcas falso positivo)",
                value=caso.get("comentario_validacion_guardrail") or "",
                placeholder="Ej.: Revisado manualmente; la alerta fue un falso positivo.",
                key=f"comentario_guardrail_compacto_{caso['id']}",
            )

            todos_resueltos = all(
                valor != "PENDIENTE"
                for valor in [
                    val_prompt if int(caso.get("prompt_injection") or 0) else "CONFIRMADA",
                    val_ofensivo if int(caso.get("ofensivo_detectado") or 0) else "CONFIRMADA",
                    val_amenaza if int(caso.get("amenaza_detectada") or 0) else "CONFIRMADA",
                ]
            )
            if st.button(
                "Guardar validación · continuar",
                type="primary",
                use_container_width=True,
                disabled=not todos_resueltos,
                key=f"guardar_guardrails_compacto_{caso['id']}",
            ):
                guardar_validacion_guardrails(
                    caso["id"], val_prompt, val_ofensivo, val_amenaza, comentario_guardrail
                )
                st.rerun()

        # PASO 3: tomar caso
        elif actual == 3:
            st.markdown("**El caso ya fue revisado. Ahora registra que comenzarás a gestionarlo.**")
            if st.button(
                "▶ Tomar caso y comenzar gestión",
                type="primary",
                use_container_width=True,
                key=f"tomar_compacto_{caso['id']}",
            ):
                actualizar_estado(caso["id"], "EN_GESTION")
                st.rerun()

        # PASO 4: gestión + evaluación IA en una sola pantalla
        elif actual == 4:
            st.markdown("**Registra la gestión y valida lo que hizo el agente antes de resolver.**")
            st.caption(
                "Las sugerencias se construyen con los datos ya registrados del caso. "
                "Revísalas y modifícalas si no representan exactamente lo que hiciste."
            )

            alertas = [etiqueta for etiqueta, _ in guardrails_detectados(caso)]
            alertas_texto = ", ".join(alertas) if alertas else "Sin alertas especiales"
            estado_cliente = estado_envio_visible(
                caso.get("estado_envio_cliente"), caso.get("respuesta_cliente_enviada")
            )
            estado_ejecutivo = estado_envio_visible(
                caso.get("estado_envio_responsable"), caso.get("notificacion_responsable_enviada")
            )
            categoria_agente = caso.get("categoria") or "N/D"
            sentimiento_agente = caso.get("sentimiento") or "N/D"
            area_agente = caso.get("area_derivada") or "N/D"
            ejecutivo_agente = caso.get("responsable_asignado") or "N/D"
            asunto = caso.get("asunto") or "Sin asunto"

            st.markdown('<div class="ia-label">Análisis de la IA</div>', unsafe_allow_html=True)
            with st.expander("Ver análisis y contexto del agente", expanded=True):
                cctx1, cctx2, cctx3 = st.columns([1.25, 1, 1], gap="medium")
                with cctx1:
                    st.markdown(
                        f"**Asunto:** {asunto}<br>"
                        f"**Categoría detectada:** {categoria_agente}<br>"
                        f"**Sentimiento detectado:** {sentimiento_agente}",
                        unsafe_allow_html=True,
                    )
                with cctx2:
                    st.markdown(
                        f"**Ejecutivo asignado:** {ejecutivo_agente}<br>"
                        f"**Área:** {area_agente}<br>"
                        f"**Alertas:** {alertas_texto}",
                        unsafe_allow_html=True,
                    )
                with cctx3:
                    st.markdown(
                        f"**Cliente notificado:** {estado_cliente}<br>"
                        f"**Ejecutivo notificado:** {estado_ejecutivo}<br>"
                        f"**Prioridad:** {caso.get('prioridad') or 'N/D'}",
                        unsafe_allow_html=True,
                    )
                st.text_area(
                    "Mensaje original",
                    value=caso.get("cuerpo_original") or "Sin contenido almacenado.",
                    height=135,
                    disabled=True,
                    key=f"mensaje_eval_v84_{caso['id']}",
                )

            st.markdown('<div class="human-label">Validación humana</div>', unsafe_allow_html=True)
            st.caption("Confirma, corrige y documenta la decisión del ejecutivo. La IA propone; la persona valida.")

            nota_key = f"nota_eval_v84_{caso['id']}"
            comentario_key = f"comentario_eval_v84_{caso['id']}"
            if nota_key not in st.session_state:
                st.session_state[nota_key] = caso.get("nota_ejecutivo") or ""
            if comentario_key not in st.session_state:
                st.session_state[comentario_key] = caso.get("comentario_feedback") or ""

            suger_nota = sugerencia_gestion(caso)
            suger_comentario = sugerencia_evaluacion(caso)

            sug1, sug2 = st.columns(2, gap="large")
            with sug1:
                st.caption("Sugerencia para la gestión realizada")
                st.info(suger_nota)
                if st.button(
                    "Usar sugerencia en el campo 1",
                    key=f"usar_sug_nota_{caso['id']}",
                    use_container_width=True,
                ):
                    st.session_state[nota_key] = suger_nota
                    st.rerun()
            with sug2:
                st.caption("Sugerencia para el comentario de evaluación")
                st.info(suger_comentario)
                if st.button(
                    "Usar sugerencia en el campo 6",
                    key=f"usar_sug_comentario_{caso['id']}",
                    use_container_width=True,
                ):
                    st.session_state[comentario_key] = suger_comentario
                    st.rerun()

            with st.form(key=f"form_gestion_eval_{caso['id']}", clear_on_submit=False):
                izq, der = st.columns(2, gap="large")
                with izq:
                    nota = st.text_area(
                        "1. ¿Qué hiciste para resolver o gestionar el caso?",
                        height=110,
                        key=nota_key,
                        placeholder="Describe solo acciones que realmente realizaste.",
                    )
                    feedback_actual = str(caso.get("feedback_clasificacion") or "PENDIENTE").upper()
                    opciones_feedback = ["PENDIENTE", "CORRECTA", "INCORRECTA"]
                    feedback = st.selectbox(
                        "2. ¿La categoría detectada por el agente fue correcta?",
                        opciones_feedback,
                        index=opciones_feedback.index(feedback_actual) if feedback_actual in opciones_feedback else 0,
                        help=f"El agente propuso: {categoria_agente}",
                    )
                    ruteo_actual = str(caso.get("ruteo_correcto") or "PENDIENTE").upper()
                    opciones_ruteo = ["PENDIENTE", "SI", "NO"]
                    ruteo = st.radio(
                        "3. ¿Llegó al ejecutivo correcto?",
                        opciones_ruteo,
                        horizontal=True,
                        index=opciones_ruteo.index(ruteo_actual) if ruteo_actual in opciones_ruteo else 0,
                        help=f"Asignado a {ejecutivo_agente} · {area_agente}",
                    )

                with der:
                    cat_actual = caso.get("categoria_corregida") or caso.get("categoria") or "OTRO"
                    categoria_corregida = st.selectbox(
                        "4. Categoría validada por el ejecutivo",
                        CATEGORIAS,
                        index=CATEGORIAS.index(cat_actual) if cat_actual in CATEGORIAS else CATEGORIAS.index("OTRO"),
                        help="Mantén la categoría si era correcta o selecciona la que corresponda.",
                    )
                    sent_actual = caso.get("sentimiento_corregido") or caso.get("sentimiento") or "NEUTRAL"
                    sentimiento_corregido = st.selectbox(
                        "5. Sentimiento validado por el ejecutivo",
                        SENTIMIENTOS,
                        index=SENTIMIENTOS.index(sent_actual) if sent_actual in SENTIMIENTOS else SENTIMIENTOS.index("NEUTRAL"),
                        help=f"El agente detectó: {sentimiento_agente}",
                    )
                    comentario = st.text_area(
                        "6. Comentario de evaluación",
                        height=110,
                        key=comentario_key,
                        placeholder="Resume por qué aceptas o corriges la clasificación, sentimiento, ruteo o alertas.",
                    )

                st.caption(
                    "Obligatorio: gestión realizada, decisión sobre la categoría, ruteo y comentario. "
                    "Las sugerencias son editables y no sustituyen el criterio del ejecutivo."
                )

                submitted = st.form_submit_button(
                    "Guardar gestión y evaluación · continuar",
                    type="primary",
                    use_container_width=True,
                )

                if submitted:
                    faltantes = []
                    if not nota.strip():
                        faltantes.append("qué gestión realizaste")
                    if feedback == "PENDIENTE":
                        faltantes.append("si la categoría del agente fue correcta")
                    if ruteo == "PENDIENTE":
                        faltantes.append("si llegó al ejecutivo correcto")
                    if not categoria_corregida:
                        faltantes.append("categoría validada")
                    if not sentimiento_corregido:
                        faltantes.append("sentimiento validado")
                    if not comentario.strip():
                        faltantes.append("comentario de evaluación")

                    if faltantes:
                        st.error("No se puede avanzar todavía. Completa: " + ", ".join(faltantes) + ".")
                    else:
                        guardar_nota(caso["id"], nota)
                        guardar_feedback(
                            caso["id"],
                            feedback,
                            categoria_corregida,
                            sentimiento_corregido,
                            ruteo,
                            comentario,
                        )
                        st.success("Gestión y evaluación guardadas. Ya puedes avanzar al paso 5.")
                        st.rerun()

        # PASO 5: resolver
        elif actual == 5:
            st.markdown("**La gestión y la evaluación ya están completas.**")
            c1, c2 = st.columns([2, 1])
            with c1:
                st.write(caso.get("nota_ejecutivo") or "Gestión registrada.")
            with c2:
                if st.button(
                    "✓ Marcar resuelto",
                    type="primary",
                    use_container_width=True,
                    key=f"resolver_compacto_{caso['id']}",
                ):
                    actualizar_estado(caso["id"], "RESUELTO")
                    st.rerun()

        # PASO 6: cerrar
        elif actual == 6:
            st.markdown("**El caso está resuelto. Ciérralo si no quedan acciones pendientes.**")
            c1, c2 = st.columns(2)
            if c1.button(
                "🔒 Cerrar caso",
                type="primary",
                use_container_width=True,
                key=f"cerrar_compacto_{caso['id']}",
            ):
                actualizar_estado(caso["id"], "CERRADO")
                st.rerun()
            if c2.button(
                "↩ Volver a gestión",
                use_container_width=True,
                key=f"volver_compacto_{caso['id']}",
            ):
                actualizar_estado(caso["id"], "EN_GESTION")
                st.rerun()

        # Cerrado
        else:
            st.success("✓ Caso cerrado. No quedan pasos pendientes.")
            if st.button(
                "↩ Reabrir caso",
                use_container_width=True,
                key=f"reabrir_compacto_{caso['id']}",
            ):
                actualizar_estado(caso["id"], "EN_GESTION")
                st.rerun()


def mostrar_informacion_opcional(caso):
    """Toda la información secundaria queda plegada para evitar scroll."""
    with st.expander("▸ Ver antecedentes completos"):
        c1, c2 = st.columns(2)
        with c1:
            st.write(f"**Cliente:** {caso.get('nombre_cliente') or 'No disponible'}")
            st.write(f"**Correo:** {extraer_email(caso.get('remitente'))}")
            st.write(f"**Asunto:** {caso.get('asunto') or 'Sin asunto'}")
            st.write(f"**Fecha de recepción:** {caso.get('fecha_recepcion') or 'No disponible'}")
        with c2:
            st.write(f"**Área:** {caso.get('area_derivada') or 'No disponible'}")
            st.write(f"**Ejecutivo:** {caso.get('responsable_asignado') or 'No disponible'}")
            st.write(f"**Correo ejecutivo:** {caso.get('correo_responsable_asignado') or correo_responsable(caso.get('responsable_asignado'))}")
            st.write(f"**Sentimiento detectado:** {caso.get('sentimiento') or 'No disponible'}")
        st.markdown("**Mensaje original**")
        st.text_area(
            "Mensaje original completo",
            value=caso.get("cuerpo_original") or "Sin contenido almacenado.",
            height=180,
            disabled=True,
            label_visibility="collapsed",
            key=f"mensaje_completo_{caso['id']}",
        )

    with st.expander("▸ Ver notificaciones y respuesta al cliente"):
        estado_cliente = estado_envio_visible(
            caso.get("estado_envio_cliente"), caso.get("respuesta_cliente_enviada")
        )
        estado_ejecutivo = estado_envio_visible(
            caso.get("estado_envio_responsable"), caso.get("notificacion_responsable_enviada")
        )
        c1, c2 = st.columns(2)
        c1.write(f"**Cliente:** {estado_cliente}")
        c2.write(f"**Ejecutivo:** {estado_ejecutivo}")
        st.markdown("**Respuesta enviada al cliente**")
        st.text_area(
            "Respuesta enviada al cliente",
            value=caso.get("respuesta_cliente_texto") or "No hay respuesta almacenada.",
            height=180,
            disabled=True,
            label_visibility="collapsed",
            key=f"respuesta_cliente_visible_{caso['id']}",
        )

    with st.expander("▸ Ver información técnica del agente"):
        conf = caso.get("confianza_modelo")
        conf_texto = f"{float(conf):.2f}" if conf is not None else "No disponible"
        st.write(f"**Confianza estimada:** {conf_texto}")
        st.write(f"**Guardrail:** {construir_guardrail(caso)}")
        st.write("**Datos personales minimizados:** " + ("Sí" if int(caso.get("pii_detectada") or 0) else "No"))
        if caso.get("pii_tipos"):
            st.write(f"**Tipos detectados:** {caso.get('pii_tipos')}")
        if int(caso.get("prompt_injection") or 0):
            st.write(f"**Prompt injection:** {caso.get('validacion_prompt_injection') or 'PENDIENTE'}")
        if int(caso.get("ofensivo_detectado") or 0):
            st.write(f"**Lenguaje ofensivo:** {caso.get('validacion_ofensivo') or 'PENDIENTE'}")
        if int(caso.get("amenaza_detectada") or 0):
            st.write(f"**Amenaza:** {caso.get('validacion_amenaza') or 'PENDIENTE'}")
        if caso.get("cuerpo_anonimizado"):
            st.markdown("**Texto anonimizado enviado al LLM**")
            st.code(caso.get("cuerpo_anonimizado"), language=None)
        if caso.get("ultimo_error"):
            st.error(f"Error registrado: {caso.get('ultimo_error')}")

    with st.expander("▸ Reasignar caso"):
        ruta = st.selectbox(
            "Nuevo ejecutivo y área",
            list(RUTAS_REASIGNACION.keys()),
            key=f"ruta_reasignacion_compacto_{caso['id']}",
        )
        nuevo_responsable, nueva_area = RUTAS_REASIGNACION[ruta]
        nuevo_correo = correo_responsable(nuevo_responsable)
        st.caption(f"Se notificará a: {nuevo_correo}")
        if st.button(
            "Reasignar y notificar",
            type="primary",
            key=f"reasignar_compacto_{caso['id']}",
        ):
            ok, detalle = reasignar_y_notificar(
                caso, nuevo_responsable, nueva_area, nuevo_correo
            )
            if ok:
                st.success(f"Caso reasignado a {nuevo_responsable}.")
            else:
                st.error(f"Caso reasignado, pero la notificación falló: {detalle}")
            st.rerun()


# ============================================================
# AUTENTICACIÓN Y CONTROL DE ACCESO DEL PROTOTIPO
# ============================================================
def usuario_actual():
    return st.session_state.get("usuario_dashboard")


def autenticar_dashboard():
    """Inicio de sesión del prototipo, manteniendo credenciales en Secrets/.env."""
    if usuario_actual():
        return True

    espacio_izq, centro, espacio_der = st.columns([1, 1.15, 1])
    with centro:
        with st.container(key="login_shell"):
            st.markdown(
                """
                <div class="login-brand">
                    <div class="login-brand-title">Agente de Triaje Bancario</div>
                    <div class="login-brand-sub">MIIUC IND3340-1 Inteligencia Artificial para Negocios</div>
                </div>
                """,
                unsafe_allow_html=True,
            )
            st.markdown("### Iniciar sesión")
            st.caption("Selecciona tu cuenta e ingresa la contraseña asignada.")

            with st.form("login_dashboard", clear_on_submit=False):
                cuenta = st.selectbox("Usuario", list(USUARIOS_DASHBOARD.keys()))
                password = st.text_input("Contraseña", type="password")
                ingresar = st.form_submit_button("Ingresar", type="primary", use_container_width=True)

            st.markdown(
                '<div class="login-note">Acceso restringido a usuarios autorizados. Cada ejecutivo visualiza únicamente los casos dentro de su alcance.</div>',
                unsafe_allow_html=True,
            )

            if ingresar:
                configuracion = USUARIOS_DASHBOARD[cuenta]
                esperada = str(configuracion.get("password") or "")

                if not esperada:
                    st.error(
                        "Esta cuenta todavía no tiene contraseña configurada. "
                        "Configúrala en Secrets/.env y reinicia el dashboard."
                    )
                elif password and hmac.compare_digest(password, esperada):
                    st.session_state["usuario_dashboard"] = {
                        "cuenta": cuenta,
                        "nombre": configuracion["nombre"],
                        "rol": configuracion["rol"],
                    }
                    logger.info("LOGIN_OK | usuario=%s | rol=%s", cuenta, configuracion["rol"])
                    st.rerun()
                else:
                    logger.warning("LOGIN_FAIL | usuario=%s", cuenta)
                    st.error("Contraseña incorrecta.")

    return False


def cerrar_sesion_dashboard():
    usuario = usuario_actual() or {}
    logger.info("LOGOUT | usuario=%s", usuario.get("cuenta", "desconocido"))
    st.session_state.pop("usuario_dashboard", None)
    st.rerun()


def filtrar_casos_por_usuario(df):
    usuario = usuario_actual() or {}
    if usuario.get("rol") == "ADMIN":
        return df.copy()
    nombre = usuario.get("nombre")
    return df[df["responsable_asignado"].fillna("") == nombre].copy()


def obtener_caso_autorizado(row_id):
    """Valida en servidor que la sesión tenga permiso sobre el ticket solicitado."""
    caso = obtener_caso(row_id)
    if not caso:
        return None
    usuario = usuario_actual() or {}
    if usuario.get("rol") == "ADMIN":
        return caso
    if str(caso.get("responsable_asignado") or "") == str(usuario.get("nombre") or ""):
        return caso
    logger.warning(
        "ACCESS_DENIED | usuario=%s | row_id=%s | responsable=%s",
        usuario.get("cuenta", "desconocido"),
        row_id,
        caso.get("responsable_asignado"),
    )
    st.error("No tienes permiso para acceder a este caso.")
    return None


# ============================================================
# CABECERA Y NAVEGACIÓN
# ============================================================
if not autenticar_dashboard():
    st.stop()

usuario_sesion = usuario_actual()

# Navegación solicitada desde botones de acceso rápido. Se procesa antes
# de crear el widget de navegación para evitar conflictos con Session State.
if st.session_state.get("_nav_request"):
    st.session_state["nav_principal_v9"] = st.session_state.pop("_nav_request")

def ir_a_bandeja(foco="Todos", row_id=None):
    """Envía al usuario a la bandeja con un foco opcional y un caso preseleccionado."""
    st.session_state["_nav_request"] = "Bandeja y gestión"
    st.session_state["_bandeja_foco_request"] = foco
    if row_id is not None:
        st.session_state["_bandeja_caso_request"] = int(row_id)


def ir_a_historial():
    """Abre la Bandeja y deja visible el historial de casos cerrados."""
    st.session_state["_nav_request"] = "Bandeja y gestión"
    st.session_state["_bandeja_foco_request"] = "Todos"
    st.session_state["_bandeja_historial_abierto"] = True

with st.sidebar:
    st.markdown(
        """
        <div class="sidebar-brand">
            <div class="sidebar-brand-title">Gestión Inteligente</div>
            <div class="sidebar-brand-sub">Atención y triaje bancario</div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    st.markdown(f"**{usuario_sesion['nombre']}**")
    st.caption("Administrador · vista global" if usuario_sesion["rol"] == "ADMIN" else "Ejecutivo · vista personal")
    pagina = st.radio(
        "Navegación",
        ["Inicio", "Bandeja y gestión", "Métricas"],
        label_visibility="collapsed",
        key="nav_principal_v9",
    )
    st.divider()
    if st.button("↻ Actualizar datos", use_container_width=True, key="actualizar_sidebar_v9"):
        st.rerun()
    if st.button("Cerrar sesión", use_container_width=True, key="logout_sidebar_v9"):
        cerrar_sesion_dashboard()

vista_texto = "Vista global de todos los casos" if usuario_sesion["rol"] == "ADMIN" else "Vista personal · solo casos asignados"
hora_actualizacion = datetime.now().strftime("%H:%M")
st.markdown(
    f"""
    <div class="app-topbar">
        <span class="app-topbar-status">● Operativo · actualizado {hora_actualizacion}</span>
        <div class="app-topbar-title">Asistente de Atención a Clientes</div>
        <div class="app-topbar-sub">Triaje, enrutamiento y revisión humana</div>
        <div class="app-topbar-user">{html.escape(usuario_sesion['nombre'])} · {vista_texto}</div>
    </div>
    """,
    unsafe_allow_html=True,
)

if not tabla_existe():
    st.error(
        "No se encontró la tabla compartida 'interacciones' en Supabase. "
        "Ejecuta primero: python setup_cloud_db.py"
    )
    st.stop()

asegurar_columnas_v7()

casos = cargar_casos()
if casos.empty:
    st.info("Aún no existen casos registrados.")
    st.stop()

# Compatibilidad con registros de versiones anteriores.
for col, default in {
    "pii_detectada": 0,
    "pii_tipos": "",
    "confianza_modelo": None,
    "revision_baja_confianza": 0,
    "feedback_clasificacion": "",
    "categoria_corregida": "",
    "sentimiento_corregido": "",
    "ruteo_correcto": "",
    "comentario_feedback": "",
    "requiere_revision_humana": 0,
    "amenaza_detectada": 0,
    "prompt_injection": 0,
    "ofensivo_detectado": 0,
    "estado_envio_cliente": "PENDIENTE",
    "estado_envio_responsable": "PENDIENTE",
    "correo_responsable_asignado": "",
    "estado_notificacion_reasignacion": "",
    "detalle_notificacion_reasignacion": "",
    "revision_ejecutivo_confirmada": 0,
    "validacion_prompt_injection": "PENDIENTE",
    "validacion_ofensivo": "PENDIENTE",
    "validacion_amenaza": "PENDIENTE",
    "comentario_validacion_guardrail": "",
    "es_relevante_bancario": 1,
    "tipo_pertinencia": "RELEVANTE",
    "motivo_pertinencia": "",
    "origen_filtro_pertinencia": "",
    "fecha_filtro_pertinencia": "",
}.items():
    if col not in casos.columns:
        casos[col] = default

casos["SLA_TECNICO"] = casos.apply(lambda fila: calcular_estado_sla(fila.to_dict()), axis=1)
casos["SLA"] = casos["SLA_TECNICO"].map(nombre_sla)
casos["Guardrail"] = casos.apply(lambda fila: construir_guardrail(fila.to_dict()), axis=1)
casos["Correo cliente"] = casos["remitente"].apply(extraer_email)
casos["Estado visible"] = casos["estado"].apply(nombre_estado)
casos["Correo ejecutivo"] = casos["responsable_asignado"].apply(correo_responsable)

# Fecha normalizada para ordenar y mostrar la bandeja. El criterio operativo
# solicitado es siempre: recepción más reciente -> recepción más antigua.
if "fecha_recepcion" in casos.columns:
    casos["_fecha_recepcion_dt"] = pd.to_datetime(casos["fecha_recepcion"], errors="coerce")
    casos["Fecha recepción"] = casos["_fecha_recepcion_dt"].dt.strftime("%d-%m-%Y · %H:%M").fillna("Sin fecha")
else:
    casos["_fecha_recepcion_dt"] = pd.NaT
    casos["Fecha recepción"] = "Sin fecha"

# El filtro de pertinencia conserva trazabilidad de correos descartados, pero
# éstos NO deben contaminar la bandeja operativa ni las métricas de casos.
mascara_ignorados = (
    casos["estado"].fillna("").eq("IGNORADO")
    | casos["es_relevante_bancario"].fillna(1).astype(int).eq(0)
)
correos_ignorados_globales = casos[mascara_ignorados].copy()
casos_operativos_globales = casos[~mascara_ignorados].copy()

# Control de acceso por responsable. Desde este punto, las tablas, métricas,
# gráficos e historiales operativos excluyen los correos ignorados.
casos_globales = casos_operativos_globales.copy()
casos = filtrar_casos_por_usuario(casos_globales)

if casos.empty and usuario_sesion["rol"] != "ADMIN":
    st.info("No tienes casos asignados actualmente.")
    st.stop()

# Métricas principales, con términos cotidianos.
abiertos = casos[~casos["estado"].isin(["RESUELTO", "CERRADO"])]
en_gestion = casos[casos["estado"] == "EN_GESTION"]
criticos = abiertos[abiertos["prioridad"] == "CRITICA"]
vencidos = abiertos[abiertos["SLA_TECNICO"] == "VENCIDO"]
revision_humana = casos[casos["requiere_revision_humana"].fillna(0).astype(int) == 1]
pii = casos[casos["pii_detectada"].fillna(0).astype(int) == 1]
guardrails = casos[casos["Guardrail"] != "Ninguno"]

# ============================================================
# PÁGINA: INICIO — CENTRO OPERATIVO
# ============================================================
if pagina == "Inicio":
    titulo_inicio = "Centro operativo" if usuario_sesion["rol"] == "ADMIN" else "Mi centro operativo"
    st.markdown(f"## {titulo_inicio}")
    st.markdown(
        '<div class="section-note">Vista principal para entender qué está ocurriendo, qué requiere atención y dónde entrar. La gestión detallada se realiza en Bandeja y gestión.</div>',
        unsafe_allow_html=True,
    )

    # --- 1. Estado general -------------------------------------------------
    # Pendientes y el selector rápido quedan juntos a la izquierda.
    # Los demás KPI conservan acceso directo a la Bandeja con su filtro.
    h1, h2, h3, h4, h5 = st.columns([0.82, 2.05, 0.72, 0.82, 0.92])

    with h1:
        kpi_navegable(
            "Pendientes", len(abiertos), "Casos que aún requieren gestión",
            "Todos", "pendientes", disabled=len(abiertos) == 0,
        )

    with h2:
        casos_selector_inicio = abiertos.sort_values(
            ["_fecha_recepcion_dt", "id"],
            ascending=[False, False],
            na_position="last",
        ).copy()

        opciones_selector_inicio = {}
        for _, fila in casos_selector_inicio.iterrows():
            etiqueta = (
                f"{fila.get('Fecha recepción') or 'Sin fecha'} · "
                f"{fila.get('ticket_id') or 'SIN-TICKET'} · "
                f"{fila.get('nombre_cliente') or 'Cliente sin nombre'} · "
                f"{fila.get('categoria') or 'Sin categoría'}"
            )
            opciones_selector_inicio[etiqueta] = int(fila["id"])

        with st.container(key="home_case_selector"):
            st.caption("ELEGIR CASO ABIERTO")
            seleccion_inicio = st.selectbox(
                "Seleccionar caso para gestionar",
                list(opciones_selector_inicio.keys()),
                index=None,
                placeholder=(
                    f"Elegir entre {len(opciones_selector_inicio)} pendientes"
                    if opciones_selector_inicio
                    else "Sin casos pendientes"
                ),
                key="inicio_selector_rapido_caso",
                help=(
                    "Selecciona un caso para previsualizarlo en Inicio. "
                    "No se abrirá hasta que pulses el botón Abrir caso."
                ),
                disabled=not bool(opciones_selector_inicio),
                label_visibility="collapsed",
            )

        # La selección solo cambia la previsualización. NO navega a otra página.
        caso_seleccionado_inicio_id = (
            opciones_selector_inicio.get(seleccion_inicio)
            if seleccion_inicio
            else None
        )

    with h3:
        kpi_navegable(
            "Críticos", len(criticos), "Prioridad crítica",
            "Críticos", "criticos", disabled=len(criticos) == 0,
        )

    with h4:
        kpi_navegable(
            "Fuera de plazo", len(vencidos), "SLA vencido",
            "Fuera de plazo", "vencidos", disabled=len(vencidos) == 0,
        )

    with h5:
        kpi_navegable(
            "Revisión humana", len(revision_humana), "Validación HITL",
            "Revisión humana", "hitl", disabled=len(revision_humana) == 0,
        )

    # --- 2. Caso sugerido / caso seleccionado -------------------------------
    candidatos = abiertos.copy()
    caso_siguiente = None
    caso_fue_seleccionado = False

    if not candidatos.empty:
        candidatos = candidatos.sort_values(
            ["_fecha_recepcion_dt", "id"],
            ascending=[True, True],
            na_position="last",
        )

        # Por defecto se propone el caso abierto más antiguo.
        caso_siguiente = candidatos.iloc[0]

        # Si el usuario eligió un caso en el selector, solo cambia la previsualización.
        if caso_seleccionado_inicio_id is not None:
            coincidencias = abiertos[
                abiertos["id"].astype(int) == int(caso_seleccionado_inicio_id)
            ]
            if not coincidencias.empty:
                caso_siguiente = coincidencias.iloc[0]
                caso_fue_seleccionado = True

        if caso_fue_seleccionado:
            st.markdown("### Caso seleccionado")
            st.caption(
                "Revisa los antecedentes. El caso solo se abrirá en Bandeja y gestión "
                "cuando pulses Abrir caso."
            )
        else:
            st.markdown("### Caso sugerido")
            st.caption(
                "Se propone el caso abierto con la fecha de recepción más antigua para evitar que quede rezagado."
            )

        ticket_siguiente = caso_siguiente.get("ticket_id") or f"ID {caso_siguiente.get('id')}"
        cliente_siguiente = caso_siguiente.get("nombre_cliente") or "Cliente sin nombre"
        correo_siguiente = extraer_email(caso_siguiente.get("remitente")) or "Correo no disponible"
        fecha_siguiente = caso_siguiente.get("Fecha recepción") or "Sin fecha"
        asunto_siguiente = caso_siguiente.get("asunto") or "Sin asunto"
        categoria_siguiente = caso_siguiente.get("categoria") or "Sin categoría"
        prioridad_siguiente = caso_siguiente.get("prioridad") or "Sin prioridad"
        estado_siguiente = caso_siguiente.get("Estado visible") or nombre_estado(caso_siguiente.get("estado"))
        sla_siguiente = nombre_sla(caso_siguiente.get("SLA_TECNICO"))
        ejecutivo_siguiente = caso_siguiente.get("responsable_asignado") or "Sin asignar"
        antiguedad_siguiente = formatear_antiguedad(caso_siguiente.get("_fecha_recepcion_dt"))

        # Datos útiles para decidir si abrir el caso sin entrar todavía a la bandeja.
        estado_respuesta_siguiente = estado_envio_visible(
            caso_siguiente.get("estado_envio_cliente"),
            caso_siguiente.get("respuesta_cliente_enviada"),
        )
        guardrail_siguiente = construir_guardrail(caso_siguiente)
        revision_siguiente = (
            "Sí"
            if int(caso_siguiente.get("requiere_revision_humana") or 0) == 1
            else "No"
        )
        mensaje_siguiente = re.sub(
            r"\s+",
            " ",
            str(caso_siguiente.get("cuerpo_original") or "Sin contenido almacenado."),
        ).strip()
        if len(mensaje_siguiente) > 260:
            mensaje_siguiente = mensaje_siguiente[:257].rstrip() + "..."

        with st.container(border=True):
            c1, c2, c3 = st.columns([1.0, 1.45, 1.15], gap="large")

            with c1:
                st.caption(
                    "CASO SELECCIONADO"
                    if caso_fue_seleccionado
                    else "CASO ABIERTO MÁS ANTIGUO"
                )
                st.markdown(f"### {ticket_siguiente}")
                st.markdown(f"**{cliente_siguiente}**")
                st.caption(correo_siguiente)
                st.markdown("**Recibido**")
                st.write(fecha_siguiente)
                st.caption(f"Antigüedad: {antiguedad_siguiente}")

            with c2:
                st.caption("MENSAJE DEL CLIENTE")
                st.markdown(f"**{asunto_siguiente}**")
                st.write(mensaje_siguiente)
                st.caption(
                    f"Categoría: {categoria_siguiente} · Prioridad: {prioridad_siguiente}"
                )

            with c3:
                st.caption("GESTIÓN / ATENCIÓN")
                st.write(f"**Estado:** {estado_siguiente}")
                st.write(f"**SLA:** {sla_siguiente}")
                st.write(f"**Ejecutivo:** {ejecutivo_siguiente}")
                st.write(f"**Revisión humana:** {revision_siguiente}")
                st.write(f"**Guardrail:** {guardrail_siguiente}")
                st.write(f"**Respuesta cliente:** {estado_respuesta_siguiente}")

            if caso_siguiente.get("SLA_TECNICO") == "VENCIDO":
                st.warning(
                    "Este caso está fuera de plazo."
                    if caso_fue_seleccionado
                    else "Este caso está fuera de plazo y además es el caso abierto más antiguo."
                )
            elif int(caso_siguiente.get("requiere_revision_humana") or 0) == 1:
                st.warning(
                    "Este caso requiere revisión humana antes de completar su gestión."
                )

            a1, a2, a3 = st.columns([1.2, 1, 1])
            with a1:
                texto_boton_abrir = (
                    "Abrir caso"
                    if caso_fue_seleccionado
                    else "Abrir caso sugerido"
                )
                st.button(
                    texto_boton_abrir,
                    type="primary",
                    use_container_width=True,
                    key=(
                        "inicio_abrir_seleccionado"
                        if caso_fue_seleccionado
                        else "inicio_abrir_siguiente"
                    ),
                    on_click=ir_a_bandeja,
                    args=("Todos", int(caso_siguiente["id"])),
                )
            with a2:
                st.button(
                    f"Pendientes · {len(abiertos)} casos",
                    use_container_width=True,
                    key="inicio_ver_pendientes",
                    on_click=ir_a_bandeja,
                    args=("Todos",),
                )
            with a3:
                st.button(
                    f"Historial cerrado ({len(casos[casos['estado'] == 'CERRADO'])})",
                    use_container_width=True,
                    key="inicio_ver_cerrados",
                    on_click=ir_a_historial,
                )
    else:
        st.success("No tienes casos pendientes en este momento.")
        if len(casos[casos["estado"] == "CERRADO"]) > 0:
            st.button(
                f"Ver historial cerrado ({len(casos[casos['estado'] == 'CERRADO'])})",
                use_container_width=True,
                key="inicio_ver_cerrados_sin_pendientes",
                on_click=ir_a_historial,
            )

    # --- 3. Actividad y carga ---------------------------------------------
    st.markdown("### Panorama operativo")
    c_actividad, c_carga = st.columns([1.25, 0.75], gap="large")

    with c_actividad:
        st.markdown("#### Actividad reciente")
        recientes = casos.sort_values(
            ["_fecha_recepcion_dt", "id"],
            ascending=[False, False],
            na_position="last",
        ).head(8).copy()
        tabla_recientes = recientes.rename(columns={
            "ticket_id": "Ticket",
            "nombre_cliente": "Cliente",
            "categoria": "Categoría",
            "prioridad": "Prioridad",
            "Estado visible": "Estado",
        })
        cols_recientes = [
            "Fecha recepción", "Ticket", "Cliente", "Categoría", "Prioridad", "Estado"
        ]
        cols_recientes = [c for c in cols_recientes if c in tabla_recientes.columns]
        st.dataframe(
            tabla_recientes[cols_recientes],
            use_container_width=True,
            hide_index=True,
            height=min(350, 75 + max(1, len(tabla_recientes)) * 34),
        )

    with c_carga:
        if usuario_sesion["rol"] == "ADMIN":
            st.markdown("#### Carga por ejecutivo")
            carga = (
                abiertos["responsable_asignado"]
                .fillna("Sin asignar")
                .replace("", "Sin asignar")
                .value_counts()
                .rename_axis("Ejecutivo")
                .reset_index(name="Pendientes")
            )
            if carga.empty:
                st.info("No hay casos pendientes para distribuir.")
            else:
                carga = carga.sort_values("Pendientes", ascending=True)
                fig_carga_inicio = px.bar(
                    carga,
                    x="Pendientes",
                    y="Ejecutivo",
                    orientation="h",
                    text="Pendientes",
                    title=None,
                )
                fig_carga_inicio.update_layout(
                    height=max(230, 58 * len(carga)),
                    margin=dict(l=8, r=18, t=10, b=20),
                    xaxis_title="Casos pendientes",
                    yaxis_title="",
                    showlegend=False,
                )
                fig_carga_inicio.update_traces(textposition="outside", cliponaxis=False)
                st.plotly_chart(
                    fig_carga_inicio,
                    use_container_width=True,
                    config={"displayModeBar": False},
                )
        else:
            st.markdown("#### Mi situación")
            propios = abiertos.copy()
            en_gestion_propios = int((propios["estado"] == "EN_GESTION").sum())
            nuevos_propios = int((propios["estado"] == "NUEVO").sum())
            st.metric("Nuevos", nuevos_propios)
            st.metric("En gestión", en_gestion_propios)
            st.metric("Fuera de plazo", len(vencidos))

# PÁGINA: BANDEJA Y GESTIÓN
# ============================================================
elif pagina == "Bandeja y gestión":
    # Los cerrados salen de la bandeja operativa y pasan al historial.
    casos_activos = casos[casos["estado"] != "CERRADO"].copy()
    casos_cerrados = casos[casos["estado"] == "CERRADO"].copy()

    st.markdown("## Bandeja y gestión")
    st.markdown(
        '<div class="section-note">Espacio operativo para buscar, filtrar, abrir y gestionar casos. Aquí se revisan correos, se registran decisiones HITL y se cierran o reabren tickets.</div>',
        unsafe_allow_html=True,
    )

    foco_solicitado = st.session_state.pop("_bandeja_foco_request", None)
    opciones_foco_bandeja = ["Todos", "Críticos", "Fuera de plazo", "Revisión humana", "Guardrails"]
    if foco_solicitado in opciones_foco_bandeja:
        st.session_state["foco_bandeja_v9"] = foco_solicitado
    foco_bandeja = st.segmented_control(
        "Vista rápida",
        opciones_foco_bandeja,
        default=st.session_state.get("foco_bandeja_v9", "Todos"),
        key="foco_bandeja_v9",
    )

    if foco_bandeja == "Críticos":
        casos_activos = casos_activos[casos_activos["prioridad"] == "CRITICA"]
    elif foco_bandeja == "Fuera de plazo":
        casos_activos = casos_activos[casos_activos["SLA_TECNICO"] == "VENCIDO"]
    elif foco_bandeja == "Revisión humana":
        casos_activos = casos_activos[casos_activos["requiere_revision_humana"].fillna(0).astype(int) == 1]
    elif foco_bandeja == "Guardrails":
        casos_activos = casos_activos[casos_activos["Guardrail"] != "Ninguno"]

    # Orden operativo solicitado: del correo más reciente al más antiguo.
    casos_activos = casos_activos.sort_values(
        ["_fecha_recepcion_dt", "id"],
        ascending=[False, False],
        na_position="last",
    )
    casos_cerrados = casos_cerrados.sort_values(
        ["_fecha_recepcion_dt", "id"],
        ascending=[False, False],
        na_position="last",
    )

    st.markdown("### Casos activos")
    st.caption("Selecciona un ticket a la izquierda. La gestión completa se realiza en el panel derecho.")

    lista_col, detalle_col = st.columns([0.82, 1.18], gap="large")

    with lista_col:
        with st.expander("Buscar o filtrar", expanded=False):
            texto_busqueda = st.text_input("Buscar", placeholder="Ticket, cliente, correo o asunto", key="buscar_activos_v90")
            f1, f2 = st.columns(2)
            estados_visibles = sorted(casos_activos["Estado visible"].dropna().unique().tolist())
            categorias = sorted([x for x in casos_activos["categoria"].dropna().unique().tolist() if x])
            estados_sel = f1.multiselect("Estado", estados_visibles, key="estado_activos_v90")
            categorias_sel = f2.multiselect("Categoría", categorias, key="categoria_activos_v90")
            responsables_sel = []
            if usuario_sesion["rol"] == "ADMIN":
                responsables = sorted([x for x in casos_activos["responsable_asignado"].dropna().unique().tolist() if x])
                responsables_sel = st.multiselect("Ejecutivo", responsables, key="responsable_activos_v90")

        filtrado = casos_activos.copy()
        if texto_busqueda.strip():
            patron = re.escape(texto_busqueda.strip())
            mascara = (
                filtrado["ticket_id"].fillna("").astype(str).str.contains(patron, case=False, regex=True)
                | filtrado["nombre_cliente"].fillna("").astype(str).str.contains(patron, case=False, regex=True)
                | filtrado["Correo cliente"].fillna("").astype(str).str.contains(patron, case=False, regex=True)
                | filtrado["asunto"].fillna("").astype(str).str.contains(patron, case=False, regex=True)
            )
            filtrado = filtrado[mascara]
        if estados_sel:
            filtrado = filtrado[filtrado["Estado visible"].isin(estados_sel)]
        if categorias_sel:
            filtrado = filtrado[filtrado["categoria"].isin(categorias_sel)]
        if responsables_sel:
            filtrado = filtrado[filtrado["responsable_asignado"].isin(responsables_sel)]

        filtrado = filtrado.sort_values(
            ["_fecha_recepcion_dt", "id"], ascending=[False, False], na_position="last"
        )

        if filtrado.empty:
            st.info("No hay casos activos que coincidan con los filtros.")
            caso = None
        else:
            tabla = filtrado.copy().rename(columns={
                "ticket_id": "Ticket", "nombre_cliente": "Cliente", "categoria": "Categoría",
                "prioridad": "Prioridad", "Estado visible": "Estado",
            })
            columnas = ["Fecha recepción", "Ticket", "Cliente", "Categoría", "Prioridad", "Estado"]
            columnas = [c for c in columnas if c in tabla.columns]
            st.dataframe(
                tabla[columnas], use_container_width=True, hide_index=True,
                height=min(330, 75 + max(1, len(tabla)) * 34),
                column_config={
                    "Fecha recepción": st.column_config.TextColumn("Fecha", width="medium"),
                    "Ticket": st.column_config.TextColumn("Ticket", width="small"),
                    "Cliente": st.column_config.TextColumn("Cliente", width="medium"),
                    "Categoría": st.column_config.TextColumn("Categoría", width="small"),
                    "Prioridad": st.column_config.TextColumn("Prioridad", width="small"),
                    "Estado": st.column_config.TextColumn("Estado", width="medium"),
                },
            )

            opciones = {
                f"{row.get('Fecha recepción') or 'Sin fecha'} · {row['ticket_id'] or 'SIN-TICKET'} · "
                f"{row.get('nombre_cliente') or 'Cliente'} · {row.get('categoria') or 'Sin categoría'}": int(row["id"])
                for _, row in filtrado.iterrows()
            }
            etiquetas_opciones = list(opciones.keys())
            caso_solicitado_id = st.session_state.pop("_bandeja_caso_request", None)
            indice_inicial = 0
            if caso_solicitado_id is not None:
                for i, etiqueta in enumerate(etiquetas_opciones):
                    if opciones[etiqueta] == int(caso_solicitado_id):
                        indice_inicial = i
                        break

            seleccion = st.selectbox(
                "Seleccionar caso para gestionar", etiquetas_opciones, index=indice_inicial,
                help="Selecciona un ticket para iniciar o continuar la gestión.",
                key="abrir_activo_v90",
            )
            caso = obtener_caso_autorizado(opciones[seleccion])

    with detalle_col:
        if caso:
            ticket = caso.get("ticket_id") or str(caso.get("id"))
            st.markdown(f'<div class="case-title">Caso {html.escape(str(ticket))}</div>', unsafe_allow_html=True)
            actual = mostrar_barra_gestion_compacta(caso)
            resumen_caso_compacto(caso)
            renderizar_accion_actual(caso, actual)
            with st.expander("Información adicional del caso", expanded=False):
                mostrar_informacion_opcional(caso)
        else:
            st.info("Selecciona un caso activo para comenzar la gestión.")

    # Solo el administrador puede revisar la trazabilidad de correos descartados.
    if usuario_sesion["rol"] == "ADMIN":
        st.divider()
        with st.expander(
            f"Correos ignorados por filtro de pertinencia ({len(correos_ignorados_globales)})",
            expanded=False,
        ):
            st.caption(
                "Estos mensajes no generaron ticket, respuesta al remitente ni asignación a un ejecutivo. "
                "Se conservan únicamente para trazabilidad y revisión del filtro."
            )
            if correos_ignorados_globales.empty:
                st.info("Todavía no hay correos descartados por el filtro de pertinencia.")
            else:
                ignorados = correos_ignorados_globales.copy()
                buscar_ignorado = st.text_input(
                    "Buscar correo ignorado",
                    placeholder="Remitente, asunto, tipo o motivo",
                    key="buscar_ignorados_pertinencia",
                )
                if buscar_ignorado.strip():
                    patron = re.escape(buscar_ignorado.strip())
                    mascara = (
                        ignorados["remitente"].fillna("").astype(str).str.contains(patron, case=False, regex=True)
                        | ignorados["asunto"].fillna("").astype(str).str.contains(patron, case=False, regex=True)
                        | ignorados["tipo_pertinencia"].fillna("").astype(str).str.contains(patron, case=False, regex=True)
                        | ignorados["motivo_pertinencia"].fillna("").astype(str).str.contains(patron, case=False, regex=True)
                    )
                    ignorados = ignorados[mascara]

                tabla_ignorados = ignorados.rename(columns={
                    "fecha_recepcion": "Fecha",
                    "remitente": "Remitente",
                    "asunto": "Asunto",
                    "tipo_pertinencia": "Tipo",
                    "motivo_pertinencia": "Motivo",
                    "origen_filtro_pertinencia": "Filtro",
                })
                cols_ignorados = ["Fecha", "Remitente", "Asunto", "Tipo", "Motivo", "Filtro"]
                st.dataframe(
                    tabla_ignorados[cols_ignorados],
                    use_container_width=True,
                    hide_index=True,
                    height=min(300, 75 + max(1, len(tabla_ignorados)) * 34),
                )

    st.divider()
    historial_expandido = bool(st.session_state.pop("_bandeja_historial_abierto", False))
    with st.expander(
        f"Historial de casos cerrados ({len(casos_cerrados)})",
        expanded=historial_expandido,
    ):
        if casos_cerrados.empty:
            st.info("Todavía no hay casos cerrados.")
        else:
            buscar_cerrados = st.text_input(
                "Buscar en historial",
                placeholder="Ticket, cliente, correo, categoría o ejecutivo",
                key="buscar_cerrados_v84",
            )
            hist = casos_cerrados.copy()
            if buscar_cerrados.strip():
                patron = re.escape(buscar_cerrados.strip())
                hist = hist[
                    hist["ticket_id"].fillna("").astype(str).str.contains(patron, case=False, regex=True)
                    | hist["nombre_cliente"].fillna("").astype(str).str.contains(patron, case=False, regex=True)
                    | hist["Correo cliente"].fillna("").astype(str).str.contains(patron, case=False, regex=True)
                    | hist["categoria"].fillna("").astype(str).str.contains(patron, case=False, regex=True)
                    | hist["responsable_asignado"].fillna("").astype(str).str.contains(patron, case=False, regex=True)
                ]

            tabla_hist = hist.copy().rename(columns={
                "ticket_id": "Ticket", "nombre_cliente": "Cliente", "categoria": "Categoría",
                "responsable_asignado": "Ejecutivo", "fecha_cierre": "Fecha cierre",
            })
            cols_hist = ["Fecha recepción", "Ticket", "Cliente", "Correo cliente", "Categoría", "Ejecutivo", "Fecha cierre", "SLA"]
            cols_hist = [c for c in cols_hist if c in tabla_hist.columns]
            st.dataframe(tabla_hist[cols_hist], use_container_width=True, hide_index=True, height=min(260, 75 + max(1, len(hist)) * 34))

            if not hist.empty:
                opciones_hist = {
                    f"{row['ticket_id'] or 'SIN-TICKET'} · {row.get('nombre_cliente') or 'Cliente'} · {row.get('categoria') or 'Sin categoría'}": int(row["id"])
                    for _, row in hist.iterrows()
                }
                sel_hist = st.selectbox("Ver caso cerrado", list(opciones_hist.keys()), key="ver_cerrado_v84")
                caso_cerrado = obtener_caso_autorizado(opciones_hist[sel_hist])
                if caso_cerrado:
                    resumen_caso_compacto(caso_cerrado)
                    with st.expander("Ver antecedentes del caso cerrado", expanded=False):
                        st.write(f"**Asunto:** {caso_cerrado.get('asunto') or 'Sin asunto'}")
                        st.write(f"**Mensaje:** {caso_cerrado.get('cuerpo_original') or 'Sin contenido almacenado.'}")
                        st.write(f"**Gestión registrada:** {caso_cerrado.get('nota_ejecutivo') or 'Sin nota'}")
                        st.write(f"**Comentario de evaluación:** {caso_cerrado.get('comentario_feedback') or 'Sin comentario'}")
                    if st.button("↩ Reabrir este caso", key=f"reabrir_hist_{caso_cerrado['id']}"):
                        actualizar_estado(caso_cerrado["id"], "EN_GESTION")
                        st.rerun()

# ============================================================
# TAB 2: RESUMEN OPERATIVO
# ============================================================
elif pagina == "Métricas":
    titulo_resumen = "Resumen operativo global" if usuario_sesion["rol"] == "ADMIN" else "Mi resumen operativo"
    ayuda_resumen = (
        "Indicadores de todos los casos del prototipo."
        if usuario_sesion["rol"] == "ADMIN"
        else "Indicadores calculados únicamente sobre los casos asignados a tu cuenta."
    )
    st.subheader(titulo_resumen)
    st.markdown(f'<div class="section-note">{ayuda_resumen}</div>', unsafe_allow_html=True)

    cerrados_total = casos[casos["estado"] == "CERRADO"]
    con_sla = casos[casos["SLA_TECNICO"].isin(["EN PLAZO", "POR VENCER", "VENCIDO", "CUMPLIDO"])]
    cumplidos_sla = con_sla[con_sla["SLA_TECNICO"].isin(["EN PLAZO", "POR VENCER", "CUMPLIDO"])]
    sla_pct = (len(cumplidos_sla) / len(con_sla) * 100) if len(con_sla) else 0

    k1, k2, k3, k4, k5 = st.columns(5)
    with k1:
        etiqueta_total = "Total de casos" if usuario_sesion["rol"] == "ADMIN" else "Mis casos"
        ayuda_total = "Todos los casos registrados en la base." if usuario_sesion["rol"] == "ADMIN" else "Casos asignados a tu cuenta, incluidos los cerrados."
        kpi_card(etiqueta_total, len(casos), ayuda_total)
    with k2:
        kpi_card("Pendientes", len(abiertos), "Casos que aún requieren gestión.")
    with k3:
        kpi_card("En gestión", len(en_gestion), "Casos que actualmente están siendo trabajados.")
    with k4:
        kpi_card("Fuera de plazo", len(vencidos), "Casos abiertos que superaron su tiempo objetivo.")
    with k5:
        kpi_card("SLA cumplido", f"{sla_pct:.1f}%", f"{len(cumplidos_sla)} de {len(con_sla)} casos con SLA evaluable.")

    st.markdown("### Distribución de la carga")
    graf1, graf2 = st.columns([1.15, 0.85], gap="large")

    with graf1:
        cat_df = (
            casos["categoria"]
            .fillna("SIN CATEGORIA")
            .value_counts()
            .rename_axis("Categoría")
            .reset_index(name="Casos")
            .sort_values("Casos", ascending=False)
        )
        fig_cat = px.bar(
            cat_df,
            x="Categoría",
            y="Casos",
            color="Categoría",
            text="Casos",
            title="Casos por categoría",
        )
        fig_cat.update_layout(
            showlegend=False,
            height=330,
            margin=dict(l=20, r=20, t=55, b=20),
            xaxis_title="",
            yaxis_title="Cantidad de casos",
        )
        fig_cat.update_traces(textposition="outside", cliponaxis=False)
        st.plotly_chart(fig_cat, use_container_width=True, config={"displayModeBar": False})
        st.caption("Muestra qué tipos de solicitudes están llegando con mayor frecuencia.")

    with graf2:
        resp_df = (
            abiertos["responsable_asignado"]
            .fillna("Sin responsable")
            .replace("", "Sin responsable")
            .value_counts()
            .rename_axis("Ejecutivo")
            .reset_index(name="Activos")
            .sort_values("Activos", ascending=True)
        )
        if resp_df.empty:
            st.info("No hay carga activa pendiente.")
        else:
            vencidos_resp = (
                vencidos["responsable_asignado"].fillna("Sin responsable").replace("", "Sin responsable")
                .value_counts().to_dict()
            )
            resp_df["Vencidos"] = resp_df["Ejecutivo"].map(vencidos_resp).fillna(0).astype(int)
            fig_resp = px.bar(
                resp_df, x="Activos", y="Ejecutivo", orientation="h", text="Activos",
                title="Carga activa por ejecutivo",
                hover_data={"Vencidos": True, "Activos": True},
            )
            fig_resp.update_layout(
                height=330, margin=dict(l=20, r=28, t=55, b=20),
                xaxis_title="Casos activos", yaxis_title="", showlegend=False,
            )
            fig_resp.update_traces(textposition="outside", cliponaxis=False)
            st.plotly_chart(fig_resp, use_container_width=True, config={"displayModeBar": False})
            st.caption("Muestra la carga operativa actual. El detalle al pasar el cursor incluye casos vencidos.")

    st.markdown("### Tiempos del proceso")
    tiempos_asignacion = [
        minutos_entre(r.get("fecha_recepcion"), r.get("fecha_asignacion"))
        for _, r in casos.iterrows()
    ]
    tiempos_asignacion = [x for x in tiempos_asignacion if x is not None and x >= 0]

    tiempos_cierre = [
        minutos_entre(r.get("fecha_asignacion"), r.get("fecha_cierre"))
        for _, r in casos.iterrows()
    ]
    tiempos_cierre = [x for x in tiempos_cierre if x is not None and x >= 0]

    t1, t2, t3 = st.columns(3)
    with t1:
        prom_asignacion = (sum(tiempos_asignacion) / len(tiempos_asignacion)) if tiempos_asignacion else None
        kpi_card("Recepción → asignación", formatear_duracion(prom_asignacion), "Promedio desde que llega un correo hasta su asignación.")
    with t2:
        prom_cierre = (sum(tiempos_cierre) / len(tiempos_cierre)) if tiempos_cierre else None
        kpi_card("Asignación → cierre", formatear_duracion(prom_cierre), "Promedio desde la asignación hasta el cierre final.")
    with t3:
        porcentaje = (len(revision_humana) / len(casos) * 100) if len(casos) else 0
        kpi_card("Revisión humana requerida", f"{porcentaje:.1f}%", f"{len(revision_humana)} de {len(casos)} casos requirieron validación especial.")

    with st.expander("Glosario de indicadores"):
        st.markdown(
            """
            - **Plazo / SLA:** tiempo objetivo definido para atender un tipo de caso dentro del prototipo.
            - **Revisión humana:** caso que el agente considera que debe ser validado especialmente por una persona.
            - **Recepción → asignación:** tiempo que tarda el sistema en llevar un correo desde la bandeja hasta el ejecutivo responsable.
            - **Asignación → cierre:** tiempo total que tarda el responsable en terminar y cerrar el caso.
            """
        )
