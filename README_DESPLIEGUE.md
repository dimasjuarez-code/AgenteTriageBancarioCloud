# Agente Triage Bancario — Prototipo Cloud simple

Arquitectura elegida:

- **Dashboard:** Streamlit Community Cloud.
- **Base compartida:** Supabase PostgreSQL.
- **Agente:** sigue ejecutándose en el computador de Dimas.
- **OpenAI + correo:** siguen siendo usados por el agente local.

Esto permite que los ejecutivos entren desde ciudades distintas sin mantener un servidor propio.

## Archivos

- `agente_bancario.py`: agente actual adaptado a PostgreSQL compartido.
- `dashboard.py`: dashboard multiusuario adaptado a Supabase/Streamlit Cloud.
- `database.py`: capa de conexión PostgreSQL.
- `setup_cloud_db.py`: crea/verifica la tabla en Supabase.
- `migrar_sqlite_a_supabase.py`: opcional; copia los casos del SQLite actual.
- `requirements.txt`: dependencias para local y Streamlit Cloud.
- `.env.example`: plantilla local sin secretos.
- `.streamlit/secrets.example.toml`: plantilla de secretos cloud sin secretos.

## Implementación en el menor número de pasos

### 1. Crear Supabase

Crea un proyecto en Supabase y copia **la URI de conexión PostgreSQL**. Si el panel ofrece una URI de pooler compatible con IPv4, úsala para evitar problemas desde redes IPv4.

En tu `.env` local agrega:

```env
DATABASE_URL=postgresql://...
```

No compartas esta URI porque contiene la contraseña de la base.

### 2. Instalar dependencias y crear la tabla

Con el entorno virtual activado:

```powershell
pip install -r requirements.txt
python setup_cloud_db.py
```

Debes obtener:

```text
OK: tabla 'interacciones' disponible. Base cloud lista.
```

### 3. Migrar los casos actuales (opcional, una sola vez)

Copia tu `banco_auditoria.db` a esta carpeta y ejecuta:

```powershell
python migrar_sqlite_a_supabase.py
```

Si prefieres comenzar el prototipo cloud vacío, omite este paso.

### 4. Probar todo localmente contra Supabase

Terminal 1:

```powershell
python agente_bancario.py
```

Terminal 2:

```powershell
streamlit run dashboard.py
```

Aunque ambos estén en tu PC, ya trabajan sobre Supabase. Confirma que un correo nuevo aparece en el dashboard.

### 5. Subir el código a GitHub

Sube únicamente los archivos del proyecto. `.env`, `banco_auditoria.db`, `logs/` y secretos están excluidos por `.gitignore`.

Nunca subas `OPENAI_API_KEY`, `EMAIL_PASS`, `DATABASE_URL` ni contraseñas reales.

### 6. Desplegar dashboard en Streamlit Community Cloud

Conecta el repositorio de GitHub y selecciona:

```text
dashboard.py
```

En la sección **Secrets** de la aplicación pega las variables de `.streamlit/secrets.example.toml`, reemplazando los valores vacíos por los reales.

Para el dashboard son imprescindibles:

```toml
DATABASE_URL = "..."
DASH_PASS_DIMAS = "..."
DASH_PASS_PABLO = "..."
DASH_PASS_DANIEL = "..."
DASH_PASS_CRISTOBAL = "..."
DASH_PASS_ADMIN = "..."
```

Si quieres mantener el envío de correo por reasignación desde el dashboard, también agrega `EMAIL_USER` y `EMAIL_PASS`.

### 7. Compartir la URL

Streamlit entregará una URL pública HTTPS. Cada ejecutivo usa la misma URL, pero entra con su propia cuenta. El código V8.5 limita la bandeja por `responsable_asignado`; el administrador ve todos los casos.

## Qué queda local

El agente continúa en tu computador:

```powershell
python agente_bancario.py
```

Si tu PC está apagado, el dashboard seguirá disponible y los casos ya guardados podrán revisarse, pero **no se procesarán correos nuevos** hasta que vuelvas a iniciar el agente.

## Seguridad del prototipo

Esta solución es apropiada para una demostración académica. No es una arquitectura bancaria productiva. No uses datos reales de clientes ni credenciales corporativas. Para producción harían falta autenticación empresarial, gestión formal de secretos, autorización a nivel de base de datos, auditoría reforzada y revisión de cumplimiento.
