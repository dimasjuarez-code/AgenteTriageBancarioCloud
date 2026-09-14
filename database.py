import os
from urllib.parse import urlparse, urlunparse, parse_qsl, urlencode

from dotenv import load_dotenv
import psycopg
from psycopg.rows import dict_row


load_dotenv()


def _streamlit_secret(name: str) -> str:
    """Lee un secreto de Streamlit Cloud sin obligar a importar Streamlit localmente."""
    try:
        import streamlit as st
        value = st.secrets.get(name, "")
        return str(value).strip() if value is not None else ""
    except Exception:
        return ""


def get_setting(name: str, default: str = "") -> str:
    """Prioridad: variable de entorno/.env -> Streamlit secrets -> valor por defecto."""
    value = os.getenv(name)
    if value is not None and str(value).strip():
        return str(value).strip()
    value = _streamlit_secret(name)
    if value:
        return value
    return default


def get_database_url() -> str:
    url = get_setting("DATABASE_URL") or get_setting("SUPABASE_DB_URL")
    if not url:
        raise RuntimeError(
            "Falta DATABASE_URL (o SUPABASE_DB_URL). Copia la URI PostgreSQL de "
            "Supabase en tu .env local y en Secrets de Streamlit Cloud."
        )
    return _ensure_sslmode(url)


def _ensure_sslmode(url: str) -> str:
    """Supabase requiere TLS; agrega sslmode=require si la URI no lo trae."""
    if "sslmode=" in url:
        return url
    parsed = urlparse(url)
    query = dict(parse_qsl(parsed.query, keep_blank_values=True))
    query["sslmode"] = "require"
    return urlunparse(parsed._replace(query=urlencode(query)))


def _translate_placeholders(sql: str) -> str:
    # El código original usa placeholders SQLite '?'. Psycopg usa '%s'.
    # En este proyecto los '?' aparecen exclusivamente como placeholders SQL.
    return sql.replace("?", "%s")


class CursorAdapter:
    def __init__(self, cursor):
        self._cursor = cursor

    def execute(self, sql, params=None):
        self._cursor.execute(_translate_placeholders(sql), params or ())
        return self

    def fetchone(self):
        return self._cursor.fetchone()

    def fetchall(self):
        return self._cursor.fetchall()

    def close(self):
        self._cursor.close()


class ConnectionAdapter:
    """Adaptador pequeño para conservar casi intacto el código SQLite original."""
    def __init__(self, connection):
        self._connection = connection

    def cursor(self):
        return CursorAdapter(self._connection.cursor(row_factory=dict_row))

    def execute(self, sql, params=None):
        cursor = self.cursor()
        cursor.execute(sql, params)
        return cursor

    def commit(self):
        self._connection.commit()

    def rollback(self):
        self._connection.rollback()

    def close(self):
        self._connection.close()


CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS interacciones (
    id BIGSERIAL PRIMARY KEY,
    message_id TEXT,
    ticket_id TEXT,
    fecha_hora TEXT,
    fecha_recepcion TEXT,
    fecha_clasificacion TEXT,
    fecha_asignacion TEXT,
    remitente TEXT,
    asunto TEXT,
    cuerpo_original TEXT,
    cuerpo_anonimizado TEXT,
    pii_detectada INTEGER DEFAULT 0,
    pii_tipos TEXT,
    nombre_cliente TEXT,
    categoria TEXT,
    sentimiento TEXT,
    prioridad TEXT,
    area_derivada TEXT,
    responsable_asignado TEXT,
    correo_responsable_asignado TEXT,
    estado TEXT,
    prompt_injection INTEGER DEFAULT 0,
    prompt_injection_motivo TEXT,
    ofensivo_detectado INTEGER DEFAULT 0,
    ofensivo_motivo TEXT,
    amenaza_detectada INTEGER DEFAULT 0,
    amenaza_motivo TEXT,
    fraude_detectado INTEGER DEFAULT 0,
    fraude_motivo TEXT,
    requiere_revision_humana INTEGER DEFAULT 0,
    confianza_modelo DOUBLE PRECISION,
    revision_baja_confianza INTEGER DEFAULT 0,
    respuesta_cliente_enviada INTEGER DEFAULT 0,
    notificacion_responsable_enviada INTEGER DEFAULT 0,
    estado_envio_cliente TEXT DEFAULT 'PENDIENTE',
    detalle_envio_cliente TEXT,
    reintentos_envio_cliente INTEGER DEFAULT 0,
    fecha_ultimo_intento_cliente TEXT,
    estado_envio_responsable TEXT DEFAULT 'PENDIENTE',
    detalle_envio_responsable TEXT,
    reintentos_envio_responsable INTEGER DEFAULT 0,
    fecha_ultimo_intento_responsable TEXT,
    estado_notificacion_reasignacion TEXT,
    detalle_notificacion_reasignacion TEXT,
    fecha_notificacion_reasignacion TEXT,
    fecha_ultima_reasignacion TEXT,
    ultimo_error TEXT,
    intentos INTEGER DEFAULT 0,
    automatizacion_completada INTEGER DEFAULT 0,
    fecha_actualizacion_estado TEXT,
    fecha_respuesta_cliente TEXT,
    fecha_notificacion_responsable TEXT,
    fecha_en_gestion TEXT,
    fecha_resolucion TEXT,
    fecha_cierre TEXT,
    sla_objetivo_min INTEGER,
    fecha_limite_sla TEXT,
    nota_ejecutivo TEXT,
    respuesta_cliente_texto TEXT,
    feedback_clasificacion TEXT DEFAULT 'PENDIENTE',
    categoria_corregida TEXT,
    sentimiento_corregido TEXT,
    ruteo_correcto TEXT DEFAULT 'PENDIENTE',
    comentario_feedback TEXT,
    fecha_feedback TEXT,
    revision_ejecutivo_confirmada INTEGER DEFAULT 0,
    fecha_revision_ejecutivo TEXT,
    validacion_prompt_injection TEXT DEFAULT 'PENDIENTE',
    validacion_ofensivo TEXT DEFAULT 'PENDIENTE',
    validacion_amenaza TEXT DEFAULT 'PENDIENTE',
    comentario_validacion_guardrail TEXT,
    fecha_validacion_guardrail TEXT
)
"""

REQUIRED_COLUMNS = {
    "message_id": "TEXT",
    "ticket_id": "TEXT",
    "fecha_hora": "TEXT",
    "fecha_recepcion": "TEXT",
    "fecha_clasificacion": "TEXT",
    "fecha_asignacion": "TEXT",
    "remitente": "TEXT",
    "asunto": "TEXT",
    "cuerpo_original": "TEXT",
    "cuerpo_anonimizado": "TEXT",
    "pii_detectada": "INTEGER DEFAULT 0",
    "pii_tipos": "TEXT",
    "nombre_cliente": "TEXT",
    "categoria": "TEXT",
    "sentimiento": "TEXT",
    "prioridad": "TEXT",
    "area_derivada": "TEXT",
    "responsable_asignado": "TEXT",
    "correo_responsable_asignado": "TEXT",
    "estado": "TEXT",
    "prompt_injection": "INTEGER DEFAULT 0",
    "prompt_injection_motivo": "TEXT",
    "ofensivo_detectado": "INTEGER DEFAULT 0",
    "ofensivo_motivo": "TEXT",
    "amenaza_detectada": "INTEGER DEFAULT 0",
    "amenaza_motivo": "TEXT",
    "fraude_detectado": "INTEGER DEFAULT 0",
    "fraude_motivo": "TEXT",
    "requiere_revision_humana": "INTEGER DEFAULT 0",
    "confianza_modelo": "DOUBLE PRECISION",
    "revision_baja_confianza": "INTEGER DEFAULT 0",
    "respuesta_cliente_enviada": "INTEGER DEFAULT 0",
    "notificacion_responsable_enviada": "INTEGER DEFAULT 0",
    "estado_envio_cliente": "TEXT DEFAULT 'PENDIENTE'",
    "detalle_envio_cliente": "TEXT",
    "reintentos_envio_cliente": "INTEGER DEFAULT 0",
    "fecha_ultimo_intento_cliente": "TEXT",
    "estado_envio_responsable": "TEXT DEFAULT 'PENDIENTE'",
    "detalle_envio_responsable": "TEXT",
    "reintentos_envio_responsable": "INTEGER DEFAULT 0",
    "fecha_ultimo_intento_responsable": "TEXT",
    "estado_notificacion_reasignacion": "TEXT",
    "detalle_notificacion_reasignacion": "TEXT",
    "fecha_notificacion_reasignacion": "TEXT",
    "fecha_ultima_reasignacion": "TEXT",
    "ultimo_error": "TEXT",
    "intentos": "INTEGER DEFAULT 0",
    "automatizacion_completada": "INTEGER DEFAULT 0",
    "fecha_actualizacion_estado": "TEXT",
    "fecha_respuesta_cliente": "TEXT",
    "fecha_notificacion_responsable": "TEXT",
    "fecha_en_gestion": "TEXT",
    "fecha_resolucion": "TEXT",
    "fecha_cierre": "TEXT",
    "sla_objetivo_min": "INTEGER",
    "fecha_limite_sla": "TEXT",
    "nota_ejecutivo": "TEXT",
    "respuesta_cliente_texto": "TEXT",
    "feedback_clasificacion": "TEXT DEFAULT 'PENDIENTE'",
    "categoria_corregida": "TEXT",
    "sentimiento_corregido": "TEXT",
    "ruteo_correcto": "TEXT DEFAULT 'PENDIENTE'",
    "comentario_feedback": "TEXT",
    "fecha_feedback": "TEXT",
    "revision_ejecutivo_confirmada": "INTEGER DEFAULT 0",
    "fecha_revision_ejecutivo": "TEXT",
    "validacion_prompt_injection": "TEXT DEFAULT 'PENDIENTE'",
    "validacion_ofensivo": "TEXT DEFAULT 'PENDIENTE'",
    "validacion_amenaza": "TEXT DEFAULT 'PENDIENTE'",
    "comentario_validacion_guardrail": "TEXT",
    "fecha_validacion_guardrail": "TEXT",
}


def connect_db() -> ConnectionAdapter:
    raw = psycopg.connect(get_database_url(), row_factory=dict_row, connect_timeout=15)
    return ConnectionAdapter(raw)


def table_exists() -> bool:
    conn = connect_db()
    try:
        row = conn.execute(
            """
            SELECT EXISTS (
                SELECT 1
                FROM information_schema.tables
                WHERE table_schema = 'public' AND table_name = 'interacciones'
            ) AS existe
            """
        ).fetchone()
        return bool(row and row.get("existe"))
    finally:
        conn.close()


def get_columns() -> set[str]:
    conn = connect_db()
    try:
        rows = conn.execute(
            """
            SELECT column_name
            FROM information_schema.columns
            WHERE table_schema = 'public' AND table_name = 'interacciones'
            """
        ).fetchall()
        return {r["column_name"] for r in rows}
    finally:
        conn.close()


def ensure_schema() -> None:
    conn = connect_db()
    try:
        conn.execute(CREATE_TABLE_SQL)
        conn.commit()

        existing = get_columns()
        for name, definition in REQUIRED_COLUMNS.items():
            if name not in existing:
                conn.execute(f"ALTER TABLE interacciones ADD COLUMN {name} {definition}")

        # PostgreSQL permite múltiples NULL en índices UNIQUE, por eso no hace falta
        # un índice parcial como en la versión SQLite.
        conn.execute(
            "CREATE UNIQUE INDEX IF NOT EXISTS idx_interacciones_message_id "
            "ON interacciones(message_id)"
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_interacciones_responsable "
            "ON interacciones(responsable_asignado)"
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_interacciones_estado "
            "ON interacciones(estado)"
        )

        conn.execute(
            """
            UPDATE interacciones
            SET estado_envio_cliente = CASE
                    WHEN COALESCE(respuesta_cliente_enviada, 0) = 1 THEN 'ACEPTADO_SMTP'
                    ELSE COALESCE(estado_envio_cliente, 'PENDIENTE')
                END,
                estado_envio_responsable = CASE
                    WHEN COALESCE(notificacion_responsable_enviada, 0) = 1 THEN 'ACEPTADO_SMTP'
                    ELSE COALESCE(estado_envio_responsable, 'PENDIENTE')
                END
            """
        )
        conn.execute(
            """
            UPDATE interacciones
            SET estado = 'ASIGNADO_HITL', automatizacion_completada = 1
            WHERE estado IN ('COMPLETADO', 'NOTIFICADO_HITL')
            """
        )
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
