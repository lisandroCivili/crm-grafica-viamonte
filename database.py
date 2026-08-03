import os
from sqlalchemy import create_engine, event
from sqlalchemy.orm import declarative_base, sessionmaker

# La carpeta donde persiste viamonte.db la resuelve rutas.py (junto al .exe
# cuando corre empaquetado, la carpeta del proyecto en desarrollo). Se conserva
# el nombre BASE_DIR porque main.py lo importa de acá para la ruta del backup.
from rutas import DIR_DATOS as BASE_DIR

# Definimos que el archivo 'viamonte.db' se guardará en esa misma carpeta
DATABASE_URL = f"sqlite:///{os.path.join(BASE_DIR, 'viamonte.db')}"

# El argumento 'check_same_thread' es necesario para SQLite en entornos web (FastAPI).
# 'timeout': cuántos segundos espera una escritura a que se libere el lock de
# SQLite antes de tirar "database is locked". El default (5s) es corto para
# varios puestos escribiendo a la vez.
engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False, "timeout": 30},
)


@event.listens_for(engine, "connect")
def _configurar_conexion(dbapi_connection, connection_record):
    cursor = dbapi_connection.cursor()
    # SQLite tiene las FOREIGN KEYS desactivadas por defecto: sin este PRAGMA,
    # los ForeignKey de models.py son decorativos y se pueden insertar filas
    # huérfanas (ej: un trabajo con cliente_id inexistente) sin ningún error.
    cursor.execute("PRAGMA foreign_keys=ON")
    # WAL: los lectores dejan de bloquearse contra el escritor. Sin esto, abrir
    # el Kanban mientras alguien guarda un pago puede dar "database is locked".
    cursor.execute("PRAGMA journal_mode=WAL")
    # NORMAL con WAL es seguro ante caída de la app (no ante corte de luz) y
    # evita un fsync por transacción, que es lo que hace lento el guardado.
    cursor.execute("PRAGMA synchronous=NORMAL")
    cursor.close()

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()

# Helper para obtener la sesión de la base de datos en los routers
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()