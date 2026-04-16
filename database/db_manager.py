import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from dotenv import load_dotenv

load_dotenv()

# Забираємо URL з .env (переконайся, що він починається з postgresql+psycopg2://)
DB_URL = os.getenv("DATABASE_URL")

if not DB_URL:
    raise ValueError("❌ Не знайдено DATABASE_URL у файлі .env!")

# Налаштовуємо підключення до Neon (PostgreSQL)
engine = create_engine(DB_URL, pool_pre_ping=True)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()