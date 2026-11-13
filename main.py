import os
import datetime
import psycopg2
from fastapi import FastAPI, Form
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(title="Control Asistencia QR API")

# Habilitar CORS para permitir peticiones desde la app Android
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Obtener la URL de conexión a PostgreSQL desde las variables de entorno de Render
DATABASE_URL = os.environ.get("postgresql://qr_attendance_db_rih4_user:lgg4UlNdjSSpGnaLmkniCgKHMtBnH8xk@dpg-dbi5psifngtc73cck770-a/qr_attendance_db_rih4")

def get_db_connection():
    conn = psycopg2.connect(DATABASE_URL, sslmode='require')
    return conn

# Crear la tabla automáticamente al iniciar si no existe
@app.on_event("startup")
def startup_db():
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS asistentes (
                codigo VARCHAR(50) PRIMARY KEY,
                nombre TEXT NOT NULL,
                complexion VARCHAR(20) DEFAULT 'normal',
                categoria_edad VARCHAR(20) DEFAULT 'adulto',
                ingresado INTEGER DEFAULT 0,
                timestamp TEXT
            );
        """)
        conn.commit()
        cursor.close()
        conn.close()
    except Exception as e:
        print(f"Error al inicializar la base de datos: {e}")

# 1. Endpoint para escanear y registrar asistencia
@app.post("/api/registrar")
def registrar_asistencia(codigo: str = Form(...)):
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Buscar el asistente en la base de datos
        cursor.execute(
            "SELECT nombre, complexion, categoria_edad, ingresado FROM asistentes WHERE codigo = %s", 
            (codigo,)
        )
        asistente = cursor.fetchone()

        if not asistente:
            cursor.close()
            conn.close()
            return JSONResponse(
                status_code=404, 
                content={"status": "not_found", "message": "El código no existe en la base de datos"}
            )

        nombre, complexion, categoria_edad, ingresado = asistente

        # Verificar si el QR ya fue utilizado
        if ingresado == 1:
            cursor.close()
            conn.close()
            return JSONResponse(
                status_code=400, 
                content={"status": "duplicate", "message": "¡La invitación ya fue usada!"}
            )

        # Registrar el ingreso
        hora_actual = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        hora_corta = datetime.datetime.now().strftime("%H:%M:%S")
        
        cursor.execute(
            "UPDATE asistentes SET ingresado = 1, timestamp = %s WHERE codigo = %s", 
            (hora_actual, codigo)
        )
        conn.commit()
        cursor.close()
        conn.close()

        return {
            "status": "registered",
            "nombre": nombre,
            "complexion": complexion,
            "categoria_edad": categoria_edad,
            "hora": hora_corta,
            "message": f"¡Ingreso exitoso para {nombre}!"
        }

    except Exception as e:
        return JSONResponse(status_code=500, content={"status": "error", "message": str(e)})

# 2. Endpoint para crear un asistente nuevo
@app.post("/api/crear-asistente")
def crear_asistente(
    codigo: str = Form(...),
    nombre: str = Form(...)
):
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO asistentes (codigo, nombre, complexion, categoria_edad, ingresado) 
            VALUES (%s, %s, 'normal', 'adulto', 0)
            ON CONFLICT (codigo) DO UPDATE 
            SET nombre = EXCLUDED.nombre;
        """, (codigo, nombre))
        
        conn.commit()
        cursor.close()
        conn.close()
        
        return {"status": "success", "message": f"Asistente {nombre} registrado correctamente"}
    except Exception as e:
        return JSONResponse(status_code=500, content={"status": "error", "message": str(e)})

# 3. Endpoint para obtener los datos del Dashboard
@app.get("/api/dashboard-data")
def dashboard_data():
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT codigo, nombre, complexion, categoria_edad, ingresado, timestamp FROM asistentes")
        rows = cursor.fetchall()
        cursor.close()
        conn.close()

        lista = []
        for row in rows:
            codigo, nombre, complexion, categoria_edad, ingresado, timestamp = row
            lista.append({
                "codigo": codigo,
                "name": nombre,
                "complexion": complexion,
                "categoria_edad": categoria_edad,
                "status": str(ingresado),
                "timestamp": timestamp if timestamp else ""
            })

        return {"asistentes": lista}
    except Exception as e:
        return JSONResponse(status_code=500, content={"status": "error", "message": str(e)})