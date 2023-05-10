import os
import psycopg2
from psycopg2 import pool

DATABASE_URL = os.environ['DATABASE_URL']

def init_db_pool():
    return psycopg2.pool.SimpleConnectionPool(1, 20, DATABASE_URL)

db_pool = init_db_pool()

def get_connection():
    return db_pool.getconn()

def release_connection(conn):
    db_pool.putconn(conn)
