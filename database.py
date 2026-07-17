import os
import sys
from sqlalchemy import create_engine, event
from sqlalchemy.orm import declarative_base, sessionmaker

# Cuando corre empaquetado (PyInstaller --onefile), sys.executable apunta al
# .exe real y __file__ apunta a una carpeta temporal (_MEIPASS) que se borra
# al cerrar el programa. Usamos la carpeta del .exe para que la base de datos
# persista entre ejecuciones; en desarrollo (`python main.py`), usamos la
# carpeta del proyecto como antes.
if getattr(sys, "frozen", False):
    BASE_DIR = os.path.dirname(sys.executable)
else:
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# Definimos que el archivo 'viamonte.db' se guardará en esa misma carpeta
DATABASE_URL = f"sqlite:///{os.path.join(BASE_DIR, 'viamonte.db')}"

# El argumento 'check_same_thread' es necesario para SQLite en entornos web (FastAPI)
engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})


# SQLite tiene las FOREIGN KEYS desactivadas por defecto: sin este PRAGMA,
# los ForeignKey de models.py son decorativos y se pueden insertar filas
# huérfanas (ej: un trabajo con cliente_id inexistente) sin ningún error.
@event.listens_for(engine, "connect")
def _activar_foreign_keys(dbapi_connection, connection_record):
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
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