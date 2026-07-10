import os
from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

# Buscamos la ruta del directorio actual donde se ejecuta el script/ejecutable
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
# Definimos que el archivo 'viamonte.db' se guardará en esa misma carpeta
DATABASE_URL = f"sqlite:///{os.path.join(BASE_DIR, 'viamonte.db')}"

# El argumento 'check_same_thread' es necesario para SQLite en entornos web (FastAPI)
engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()

# Helper para obtener la sesión de la base de datos en los routers
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()