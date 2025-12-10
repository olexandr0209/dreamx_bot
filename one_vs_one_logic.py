# one_vs_one_logic.py
import os
import psycopg2
from psycopg2.extras import RealDictCursor
from datetime import datetime

from config import DATABASE_URL

def _get_conn():
    return psycopg2.connect(
        DATABASE_URL,
        sslmode=os.getenv("PG_SSLMODE", "require")
    )
