
import os
import sqlite3
from datetime import datetime
from typing import Tuple

import pandas as pd
import streamlit as st

# ============================================================
# CONFIGURACIÓN GENERAL
# ============================================================

st.set_page_config(
    page_title="Asistente de Atención a Clientes",
    page_icon="💬",
    layout="wide",
    initial_sidebar_state="expanded",
)

APP_TITLE = "Asistente de Atención a Clientes"
APP_SUBTITLE = "Triaje, enrutamiento y revisión humana"
SQLITE_PATH = "banco_auditoria.db"
TABLE_NAME = "casos"  # Cambia este nombre si tu tabla principal usa otro nombre.


# ============================================================
# PALETA / CSS
# ============================================================

PRIMARY = "#173B7A"
PRIMARY_2 = "#2456A6"
ACCENT = "#3D6FE8"
BG = "#F4F7FB"
CARD = "#FFFFFF"
TEXT = "#15233B"
MUTED = "#6E7B91"
BORDER = "#DFE6F0"
SUCCESS = "#138A5B"
WARNING = "#D78A00"
DANGER = "#D64545"
PURPLE = "#7557D9"


st.markdown(
    f"""
    <style>
        .stApp {{
            background: {BG};
            color: {TEXT};
        }}

        #MainMenu, footer, header {{
            visibility: hidden;
        }}

        .block-container {{
            padding-top: 1.2rem;
            padding-bottom: 2rem;
            max-width: 1600px;
        }}

        [data-testid="stSidebar"] {{
            background: #FFFFFF;
            border-right: 1px solid {BORDER};
        }}

        [data-testid="stSidebar"] .block-container {{
            padding-top: 1.2rem;
        }}

        .topbar {{
            background: linear-gradient(90deg, {PRIMARY} 0%, {PRIMARY_2} 100%);
            color: white;
            border-radius: 18px;
            padding: 18px 24px;
            display: flex;
            align-items: center;
            justify-content: space-between;
            gap: 20px;
            margin-bottom: 20px;
            box-shadow: 0 8px 22px rgba(30, 64, 120, 0.12);
        }}

        .topbar-title {{
            font-size: 1.45rem;
            font-weight: 800;
            line-height: 1.1;
            margin-bottom: 4px;
        }}

        .topbar-subtitle {{
            opacity: .84;
            font-size: .92rem;
        }}

        .status-pill {{
            background: rgba(255,255,255,.14);
            border: 1px solid rgba(255,255,255,.18);
            border-radius: 999px;
            padding: 8px 13px;
            font-size: .86rem;
            font-weight: 700;
            white-space: nowrap;
        }}

        .section-title {{
            font-size: 1.45rem;
            font-weight: 800;
            margin: 2px 0 2px 0;
        }}

        .section-subtitle {{
            color: {MUTED};
            margin-bottom: 16px;
        }}

        .kpi-card {{
            background: {CARD};
            border: 1px solid {BORDER};
            border-radius: 16px;
            padding: 16px 18px;
            min-height: 118px;
            box-shadow: 0 3px 12px rgba(35, 57, 89, .05);
        }}

        .kpi-label {{
            color: {MUTED};
            font-size: .86rem;
            margin-bottom: 4px;
        }}

        .kpi-value {{
            font-size: 1.75rem;
            font-weight: 800;
            color: {TEXT};
            line-height: 1.1;
        }}

        .kpi-note {{
            font-size: .80rem;
            color: {MUTED};
            margin-top: 7px;
        }}

        .case-card {{
            background: {CARD};
            border: 1px solid {BORDER};
            border-radius: 15px;
            padding: 14px 16px;
            margin-bottom: 10px;
            transition: all .15s ease;
        }}

        .case-card:hover {{
            border-color: #B8C7E3;
            box-shadow: 0 4px 14px rgba(35, 57, 89, .06);
        }}

        .case-top {{
            display: flex;
            align-items: center;
            justify-content: space-between;
            gap: 12px;
            margin-bottom: 7px;
        }}

        .case-id {{
            font-weight: 800;
            color: {TEXT};
            font-size: .98rem;
        }}

        .case-date {{
            color: {MUTED};
            font-size: .82rem;
            white-space: nowrap;
        }}

        .case-subject {{
            font-weight: 700;
            margin-bottom: 5px;
            color: {TEXT};
        }}

        .case-preview {{
            color: {MUTED};
            font-size: .89rem;
            line-height: 1.35;
            margin-bottom: 8px;
        }}

        .case-meta {{
            display: flex;
            flex-wrap: wrap;
            gap: 7px;
            align-items: center;
        }}

        .badge {{
            display: inline-flex;
            align-items: center;
            padding: 4px 8px;
            border-radius: 999px;
            font-size: .76rem;
            font-weight: 700;
        }}

        .badge-blue {{
            color: #1F57BD;
            background: #EAF1FF;
        }}

        .badge-red {{
            color: #B52C2C;
            background: #FDEAEA;
        }}

        .badge-orange {{
            color: #9B6200;
            background: #FFF1D6;
        }}

        .badge-green {{
            color: #0D724A;
            background: #E7F7F0;
        }}

        .badge-purple {{
            color: #6043B5;
            background: #EFEAFE;
        }}

        .detail-card {{
            background: {CARD};
            border: 1px solid {BORDER};
            border-radius: 16px;
            padding: 18px;
            margin-bottom: 12px;
        }}

        .detail-label {{
            color: {MUTED};
            font-size: .78rem;
            margin-bottom: 2px;
        }}

        .detail-value {{
            color: {TEXT};
            font-weight: 700;
            font-size: .93rem;
        }}

        .progress-wrap {{
            background: {CARD};
            border: 1px solid {BORDER};
            border-radius: 16px;
            padding: 18px;
            margin-bottom: 12px;
        }}

        .progress-row {{
            display: grid;
            grid-template-columns: repeat(5, 1fr);
            gap: 8px;
        }}

        .step {{
            text-align: center;
            font-size: .78rem;
            color: {MUTED};
        }}

        .step-dot {{
            width: 30px;
            height: 30px;
            border-radius: 50%;
            margin: 0 auto 7px auto;
            display: flex;
            align-items: center;
            justify-content: center;
            border: 2px solid {BORDER};
            background: white;
            color: {MUTED};
            font-weight: 800;
        }}

        .step.active .step-dot,
        .step.done .step-dot {{
            color: white;
            border-color: {ACCENT};
            background: {ACCENT};
        }}

        .step.done {{
            color: {SUCCESS};
        }}

        .sidebar-brand {{
            padding: 6px 2px 16px 2px;
        }}

        .sidebar-brand-title {{
            font-size: 1.08rem;
            font-weight: 800;
            color: {PRIMARY};
        }}

        .sidebar-brand-sub {{
            color: {MUTED};
            font-size: .80rem;
            margin-top: 3px;
        }}

        .small-muted {{
            color: {MUTED};
            font-size: .82rem;
        }}

        .stButton > button {{
            border-radius: 10px;
            border: 1px solid #D5DEEC;
            font-weight: 700;
        }}

        div[data-testid="stTextInput"] input,
        div[data-testid="stSelectbox"] > div > div {{
            border-radius: 10px;
        }}

        @media (max-width: 900px) {{
            .topbar {{
                flex-direction: column;
                align-items: flex-start;
            }}
            .progress-row {{
                grid-template-columns: 1fr;
            }}
        }}
    </style>
    """,
    unsafe_allow_html=True,
)


# ============================================================
# UTILIDADES DE DATOS
# ============================================================

def get_secret(name: str, default=None):
    """Busca primero en st.secrets y luego en variables de entorno."""
    try:
        if name in st.secrets:
            return st.secrets[name]
    except Exception:
        pass
    return os.getenv(name, default)


def first_existing_column(df: pd.DataFrame, candidates, default=None):
    for col in candidates:
        if col in df.columns:
            return col
    return default


def normalize_case_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    """
    Normaliza nombres de columnas frecuentes para que el dashboard funcione
    aunque tu base use nombres distintos.

    No modifica tu base de datos.
    """
    if df is None or df.empty:
        return pd.DataFrame()

    df = df.copy()

    mappings = {
        "case_id": ["case_id", "id_caso", "codigo", "ticket_id", "id"],
        "fecha": ["fecha_recepcion", "created_at", "fecha", "received_at", "fecha_creacion", "timestamp"],
        "categoria": ["categoria", "category", "clasificacion"],
        "prioridad": ["prioridad", "priority"],
        "estado": ["estado", "status"],
        "asunto": ["asunto", "subject", "titulo"],
        "mensaje": ["mensaje", "body", "contenido", "correo", "texto", "message"],
        "cliente": ["cliente", "customer_name", "nombre_cliente", "remitente_nombre"],
        "email": ["email", "customer_email", "correo_cliente", "remitente"],
        "ejecutivo": ["ejecutivo", "assigned_to", "responsable", "ejecutivo_asignado"],
        "sentimiento": ["sentimiento", "sentiment"],
        "pii": ["pii", "pii_detectada", "pii_minimizada"],
        "guardrail": ["guardrail", "guardrails", "prompt_injection", "riesgo_guardrail"],
        "revision_humana": ["revision_humana", "human_review", "hitl"],
    }

    rename_dict = {}
    for normalized, options in mappings.items():
        found = first_existing_column(df, options)
        if found:
            rename_dict[found] = normalized

    df = df.rename(columns=rename_dict)

    # Columnas faltantes: se crean solo para visualización.
    defaults = {
        "case_id": "SIN-ID",
        "fecha": pd.NaT,
        "categoria": "SIN CATEGORÍA",
        "prioridad": "Media",
        "estado": "Abierto",
        "asunto": "Sin asunto",
        "mensaje": "",
        "cliente": "",
        "email": "",
        "ejecutivo": "Sin asignar",
        "sentimiento": "No evaluado",
        "pii": False,
        "guardrail": False,
        "revision_humana": False,
    }

    for col, value in defaults.items():
        if col not in df.columns:
            df[col] = value

    # Fecha normalizada y orden descendente: más reciente -> más antiguo.
    df["_fecha"] = pd.to_datetime(df["fecha"], errors="coerce", utc=True)

    # Si tu base guarda hora local sin zona, Streamlit puede convertirla como UTC.
    # Para efectos de ordenamiento no afecta mientras todas las filas usen el mismo criterio.
    df = df.sort_values("_fecha", ascending=False, na_position="last").reset_index(drop=True)

    return df


def load_demo_cases() -> pd.DataFrame:
    """Datos de demostración solamente si no se puede leer la base."""
    now = pd.Timestamp.now(tz="UTC")
    demo = pd.DataFrame(
        [
            {
                "case_id": "CON-0008",
                "fecha": now - pd.Timedelta(minutes=12),
                "categoria": "CONSULTA",
                "prioridad": "Media",
                "estado": "Abierto",
                "asunto": "Consulta sobre estado de transferencia",
                "mensaje": "Hola, necesito saber el estado de una transferencia que realicé.",
                "cliente": "Carolina Martínez",
                "email": "cliente@ejemplo.cl",
                "ejecutivo": "Daniel Calderón",
                "sentimiento": "Neutral",
                "pii": False,
                "guardrail": False,
                "revision_humana": True,
            },
            {
                "case_id": "FRA-0012",
                "fecha": now - pd.Timedelta(minutes=25),
                "categoria": "FRAUDE",
                "prioridad": "Crítica",
                "estado": "Abierto",
                "asunto": "Retiro no autorizado",
                "mensaje": "Detecté un retiro que no reconozco y necesito ayuda.",
                "cliente": "Cliente",
                "email": "cliente@ejemplo.cl",
                "ejecutivo": "Dimas Juárez",
                "sentimiento": "Negativo",
                "pii": True,
                "guardrail": False,
                "revision_humana": True,
            },
            {
                "case_id": "REC-0005",
                "fecha": now - pd.Timedelta(hours=1),
                "categoria": "RECLAMO",
                "prioridad": "Media",
                "estado": "Abierto",
                "asunto": "Problema con cargo en tarjeta",
                "mensaje": "Tengo un cargo duplicado y necesito una revisión.",
                "cliente": "Cliente",
                "email": "cliente@ejemplo.cl",
                "ejecutivo": "Pablo González",
                "sentimiento": "Negativo",
                "pii": False,
                "guardrail": False,
                "revision_humana": False,
            },
        ]
    )
    return normalize_case_dataframe(demo)


@st.cache_data(ttl=30, show_spinner=False)
def load_cases() -> Tuple[pd.DataFrame, str]:
    """
    Intenta:
    1) PostgreSQL/Supabase mediante DATABASE_URL.
    2) SQLite local banco_auditoria.db.
    3) Datos demo si no encuentra ninguna fuente.

    IMPORTANTE:
    Si tu tabla no se llama 'casos', cambia TABLE_NAME arriba.
    """

    database_url = get_secret("DATABASE_URL")

    # ---------- PostgreSQL / Supabase ----------
    if database_url:
        try:
            import psycopg2

            conn = psycopg2.connect(
                database_url,
                connect_timeout=5,
                options="-c statement_timeout=5000",
            )
            try:
                df = pd.read_sql_query(f'SELECT * FROM "{TABLE_NAME}"', conn)
            finally:
                conn.close()

            return normalize_case_dataframe(df), "PostgreSQL / Supabase"
        except Exception as e:
            postgres_error = str(e)
        else:
            postgres_error = None
    else:
        postgres_error = None

    # ---------- SQLite ----------
    if os.path.exists(SQLITE_PATH):
        try:
            conn = sqlite3.connect(SQLITE_PATH, timeout=3)
            try:
                df = pd.read_sql_query(f'SELECT * FROM "{TABLE_NAME}"', conn)
            finally:
                conn.close()

            return normalize_case_dataframe(df), "SQLite"
        except Exception as e:
            sqlite_error = str(e)
        else:
            sqlite_error = None
    else:
        sqlite_error = None

    # ---------- Demo ----------
    df = load_demo_cases()

    errors = []
    if postgres_error:
        errors.append("PostgreSQL no disponible")
    if sqlite_error:
        errors.append("SQLite no disponible")

    source = "Datos demo"
    if errors:
        source += " (" + ", ".join(errors) + ")"

    return df, source


def format_case_datetime(value) -> str:
    if pd.isna(value):
        return "Fecha no disponible"

    ts = pd.Timestamp(value)

    # Si tiene zona horaria, convierte a Chile continental.
    try:
        if ts.tzinfo is not None:
            ts = ts.tz_convert("America/Santiago")
    except Exception:
        pass

    return ts.strftime("%d-%m-%Y · %H:%M")


def normalize_text(value, fallback=""):
    if pd.isna(value):
        return fallback
    text = str(value).strip()
    return text if text else fallback


def bool_value(value) -> bool:
    if isinstance(value, bool):
        return value
    if pd.isna(value):
        return False
    return str(value).strip().lower() in {"1", "true", "sí", "si", "yes", "y", "x"}


def priority_badge(priority: str) -> str:
    p = normalize_text(priority, "Media").lower()
    if p in {"crítica", "critica", "alta"}:
        return "badge-red"
    if p in {"media", "medium"}:
        return "badge-orange"
    return "badge-green"


def category_badge(category: str) -> str:
    c = normalize_text(category, "SIN CATEGORÍA").upper()
    if c == "FRAUDE":
        return "badge-red"
    if c in {"OFENSIVO", "AMENAZA", "AMENAZAS"}:
        return "badge-orange"
    if c == "FELICITACIÓN":
        return "badge-green"
    if c == "RECLAMO":
        return "badge-purple"
    return "badge-blue"


def is_open_state(value: str) -> bool:
    s = normalize_text(value, "Abierto").lower()
    return s not in {
        "cerrado",
        "resuelto",
        "closed",
        "resolved",
        "finalizado",
        "completado",
    }


# ============================================================
# COMPONENTES
# ============================================================

def render_topbar(data_source: str):
    st.markdown(
        f"""
        <div class="topbar">
            <div>
                <div class="topbar-title">{APP_TITLE}</div>
                <div class="topbar-subtitle">{APP_SUBTITLE}</div>
            </div>
            <div class="status-pill">● Operativo · Fuente: {data_source}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_kpis(df: pd.DataFrame):
    if df.empty:
        return

    total = len(df)
    abiertos = int(df["estado"].apply(is_open_state).sum())

    priority_norm = df["prioridad"].astype(str).str.strip().str.lower()
    criticos = int(priority_norm.isin(["crítica", "critica"]).sum())

    revision = int(df["revision_humana"].apply(bool_value).sum())
    pii = int(df["pii"].apply(bool_value).sum())
    guardrails = int(df["guardrail"].apply(bool_value).sum())

    values = [
        ("Total casos", total, "Registros disponibles"),
        ("Abiertos", abiertos, "Pendientes de cierre"),
        ("Críticos", criticos, "Prioridad crítica"),
        ("Revisión humana", revision, "Casos HITL"),
        ("PII detectada", pii, "Casos con indicador PII"),
        ("Guardrails", guardrails, "Alertas de seguridad"),
    ]

    cols = st.columns(6)
    for col, (label, value, note) in zip(cols, values):
        with col:
            st.markdown(
                f"""
                <div class="kpi-card">
                    <div class="kpi-label">{label}</div>
                    <div class="kpi-value">{value}</div>
                    <div class="kpi-note">{note}</div>
                </div>
                """,
                unsafe_allow_html=True,
            )


def render_case_card(row: pd.Series):
    case_id = normalize_text(row["case_id"], "SIN-ID")
    categoria = normalize_text(row["categoria"], "SIN CATEGORÍA")
    prioridad = normalize_text(row["prioridad"], "Media")
    asunto = normalize_text(row["asunto"], "Sin asunto")
    mensaje = normalize_text(row["mensaje"], "")
    ejecutivo = normalize_text(row["ejecutivo"], "Sin asignar")
    fecha = format_case_datetime(row["_fecha"])

    preview = mensaje
    if len(preview) > 125:
        preview = preview[:122] + "..."

    st.markdown(
        f"""
        <div class="case-card">
            <div class="case-top">
                <div class="case-id">{case_id}</div>
                <div class="case-date">📅 {fecha}</div>
            </div>
            <div class="case-subject">{asunto}</div>
            <div class="case-preview">{preview}</div>
            <div class="case-meta">
                <span class="badge {category_badge(categoria)}">{categoria}</span>
                <span class="badge {priority_badge(prioridad)}">{prioridad}</span>
                <span class="small-muted">Ejecutivo: {ejecutivo}</span>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_progress(row: pd.Series):
    estado = normalize_text(row["estado"], "Abierto").lower()

    if estado in {"cerrado", "resuelto", "closed", "resolved", "finalizado"}:
        active = 5
    elif bool_value(row["revision_humana"]):
        active = 3
    else:
        active = 2

    labels = ["Recepción", "Análisis IA", "Revisión humana", "Respuesta", "Cierre"]

    blocks = []
    for i, label in enumerate(labels, start=1):
        css_class = "done" if i < active else "active" if i == active else ""
        blocks.append(
            f"""
            <div class="step {css_class}">
                <div class="step-dot">{i}</div>
                <div>{label}</div>
            </div>
            """
        )

    st.markdown(
        f"""
        <div class="progress-wrap">
            <div class="progress-row">
                {''.join(blocks)}
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_case_detail(row: pd.Series):
    case_id = normalize_text(row["case_id"], "SIN-ID")
    categoria = normalize_text(row["categoria"], "SIN CATEGORÍA")
    prioridad = normalize_text(row["prioridad"], "Media")
    estado = normalize_text(row["estado"], "Abierto")
    asunto = normalize_text(row["asunto"], "Sin asunto")
    cliente = normalize_text(row["cliente"], "No identificado")
    email = normalize_text(row["email"], "No disponible")
    ejecutivo = normalize_text(row["ejecutivo"], "Sin asignar")
    sentimiento = normalize_text(row["sentimiento"], "No evaluado")
    mensaje = normalize_text(row["mensaje"], "Sin contenido disponible")
    fecha = format_case_datetime(row["_fecha"])

    st.markdown(
        f"""
        <div class="detail-card">
            <div style="display:flex; justify-content:space-between; gap:16px; flex-wrap:wrap;">
                <div>
                    <div style="font-size:1.18rem; font-weight:800;">{case_id}</div>
                    <div style="font-weight:700; margin-top:3px;">{asunto}</div>
                    <div class="small-muted" style="margin-top:5px;">📅 {fecha}</div>
                </div>
                <div class="case-meta">
                    <span class="badge {category_badge(categoria)}">{categoria}</span>
                    <span class="badge {priority_badge(prioridad)}">{prioridad}</span>
                    <span class="badge badge-blue">{estado}</span>
                </div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    render_progress(row)

    col1, col2 = st.columns([0.95, 1.45], gap="large")

    with col1:
        st.markdown("#### Datos del caso")

        info = [
            ("Cliente", cliente),
            ("Correo", email),
            ("Sentimiento", sentimiento),
            ("Ejecutivo asignado", ejecutivo),
            ("PII", "Sí" if bool_value(row["pii"]) else "No"),
            ("Guardrail", "Sí" if bool_value(row["guardrail"]) else "No"),
        ]

        html = '<div class="detail-card">'
        for label, value in info:
            html += f"""
                <div style="margin-bottom:12px;">
                    <div class="detail-label">{label}</div>
                    <div class="detail-value">{value}</div>
                </div>
            """
        html += "</div>"
        st.markdown(html, unsafe_allow_html=True)

    with col2:
        st.markdown("#### Correo del cliente")
        st.markdown(
            f"""
            <div class="detail-card" style="min-height:230px;">
                <div style="white-space:pre-wrap; line-height:1.55;">{mensaje}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        st.markdown("#### Gestión humana")

        categoria_revision = st.selectbox(
            "Categoría validada",
            ["CONSULTA", "SOLICITUD", "RECLAMO", "FRAUDE", "FELICITACIÓN", "OFENSIVO", "AMENAZA"],
            index=(
                ["CONSULTA", "SOLICITUD", "RECLAMO", "FRAUDE", "FELICITACIÓN", "OFENSIVO", "AMENAZA"]
                .index(categoria.upper())
                if categoria.upper() in ["CONSULTA", "SOLICITUD", "RECLAMO", "FRAUDE", "FELICITACIÓN", "OFENSIVO", "AMENAZA"]
                else 0
            ),
            key=f"categoria_{case_id}",
        )

        comentario = st.text_area(
            "Comentario del revisor",
            placeholder="Registra aquí la validación, corrección o decisión tomada.",
            key=f"comentario_{case_id}",
        )

        c1, c2 = st.columns(2)
        with c1:
            if st.button("Guardar evaluación", use_container_width=True, key=f"guardar_{case_id}"):
                st.success(
                    f"Evaluación registrada en la sesión: {categoria_revision}. "
                    "Conecta este botón con tu función actual de actualización en PostgreSQL/SQLite."
                )
        with c2:
            if st.button("Marcar como resuelto", use_container_width=True, type="primary", key=f"resolver_{case_id}"):
                st.success(
                    "Acción preparada. Conecta este botón con la misma función que actualmente utilizas "
                    "para cerrar/resolver un caso."
                )


# ============================================================
# SIDEBAR
# ============================================================

with st.sidebar:
    st.markdown(
        f"""
        <div class="sidebar-brand">
            <div class="sidebar-brand-title">Gestión Inteligente</div>
            <div class="sidebar-brand-sub">Atención y triaje bancario</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    page = st.radio(
        "Navegación",
        ["Inicio", "Bandeja de casos", "Casos cerrados", "Métricas"],
        label_visibility="collapsed",
    )

    st.divider()
    if st.button("Actualizar datos", use_container_width=True):
        st.cache_data.clear()
        st.rerun()


# ============================================================
# CARGA
# ============================================================

df, data_source = load_cases()
render_topbar(data_source)


# ============================================================
# PÁGINAS
# ============================================================

if page == "Inicio":
    st.markdown('<div class="section-title">Resumen operacional</div>', unsafe_allow_html=True)
    st.markdown(
        '<div class="section-subtitle">Vista general de la actividad del asistente y los casos registrados.</div>',
        unsafe_allow_html=True,
    )

    render_kpis(df)

    st.markdown("### Casos más recientes")

    if df.empty:
        st.info("No hay casos disponibles.")
    else:
        for _, row in df.head(5).iterrows():
            render_case_card(row)


elif page == "Bandeja de casos":
    st.markdown('<div class="section-title">Bandeja de casos</div>', unsafe_allow_html=True)
    st.markdown(
        '<div class="section-subtitle">Ordenados automáticamente desde el más reciente al más antiguo.</div>',
        unsafe_allow_html=True,
    )

    abiertos = df[df["estado"].apply(is_open_state)].copy()

    col_search, col_cat, col_priority = st.columns([2.1, 1, 1])

    with col_search:
        search = st.text_input(
            "Buscar",
            placeholder="Cliente, asunto, correo o ID...",
            label_visibility="collapsed",
        )

    with col_cat:
        categorias = ["Todas"] + sorted(
            [x for x in abiertos["categoria"].dropna().astype(str).unique().tolist() if x]
        )
        cat_filter = st.selectbox("Categoría", categorias, label_visibility="collapsed")

    with col_priority:
        priorities = ["Todas"] + sorted(
            [x for x in abiertos["prioridad"].dropna().astype(str).unique().tolist() if x]
        )
        priority_filter = st.selectbox("Prioridad", priorities, label_visibility="collapsed")

    filtered = abiertos.copy()

    if search:
        q = search.lower().strip()
        mask = (
            filtered["case_id"].astype(str).str.lower().str.contains(q, na=False)
            | filtered["cliente"].astype(str).str.lower().str.contains(q, na=False)
            | filtered["email"].astype(str).str.lower().str.contains(q, na=False)
            | filtered["asunto"].astype(str).str.lower().str.contains(q, na=False)
            | filtered["mensaje"].astype(str).str.lower().str.contains(q, na=False)
        )
        filtered = filtered[mask]

    if cat_filter != "Todas":
        filtered = filtered[filtered["categoria"].astype(str) == cat_filter]

    if priority_filter != "Todas":
        filtered = filtered[filtered["prioridad"].astype(str) == priority_filter]

    # Refuerzo del orden solicitado:
    # siempre más reciente -> más antiguo.
    filtered = filtered.sort_values("_fecha", ascending=False, na_position="last").reset_index(drop=True)

    st.caption(f"{len(filtered)} caso(s) abiertos")

    if filtered.empty:
        st.info("No hay casos que coincidan con los filtros.")
    else:
        case_options = filtered["case_id"].astype(str).tolist()

        selected_case = st.selectbox(
            "Seleccionar caso",
            case_options,
            index=0,
            key="selected_case",
        )

        left, right = st.columns([0.9, 1.25], gap="large")

        with left:
            for _, row in filtered.iterrows():
                render_case_card(row)

        with right:
            selected = filtered[filtered["case_id"].astype(str) == selected_case]
            if not selected.empty:
                render_case_detail(selected.iloc[0])


elif page == "Casos cerrados":
    st.markdown('<div class="section-title">Casos cerrados</div>', unsafe_allow_html=True)
    st.markdown(
        '<div class="section-subtitle">Historial ordenado desde el cierre o recepción más reciente.</div>',
        unsafe_allow_html=True,
    )

    closed = df[~df["estado"].apply(is_open_state)].copy()
    closed = closed.sort_values("_fecha", ascending=False, na_position="last")

    if closed.empty:
        st.info("No hay casos cerrados registrados.")
    else:
        for _, row in closed.iterrows():
            render_case_card(row)


elif page == "Métricas":
    st.markdown('<div class="section-title">Métricas</div>', unsafe_allow_html=True)
    st.markdown(
        '<div class="section-subtitle">Resumen descriptivo de los casos disponibles.</div>',
        unsafe_allow_html=True,
    )

    render_kpis(df)

    if not df.empty:
        col1, col2 = st.columns(2)

        with col1:
            st.markdown("#### Casos por categoría")
            cat_counts = (
                df["categoria"]
                .fillna("SIN CATEGORÍA")
                .astype(str)
                .value_counts()
                .rename_axis("Categoría")
                .reset_index(name="Casos")
            )
            st.bar_chart(cat_counts.set_index("Categoría"))

        with col2:
            st.markdown("#### Casos por prioridad")
            pr_counts = (
                df["prioridad"]
                .fillna("Sin prioridad")
                .astype(str)
                .value_counts()
                .rename_axis("Prioridad")
                .reset_index(name="Casos")
            )
            st.bar_chart(pr_counts.set_index("Prioridad"))

        st.markdown("#### Casos por fecha")
        valid_dates = df.dropna(subset=["_fecha"]).copy()
        if not valid_dates.empty:
            valid_dates["día"] = valid_dates["_fecha"].dt.date
            daily = valid_dates.groupby("día").size().reset_index(name="Casos")
            st.line_chart(daily.set_index("día"))
        else:
            st.info("No hay fechas válidas para construir la serie temporal.")
