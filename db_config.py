import psycopg2
from psycopg2 import pool
from flask import current_app

db_configs = [
    {
        'host': 'localhost',
        'user': 'postgres',
        'password': 'enter database password',
        'dbname': 'todo_db'
    },

]

# Create a connection pool for each database
connection_pools = {}

def init_db_pools():
    for config in db_configs:
        try:
            pool_name = f"pool_{config['dbname']}"
            connection_pools[pool_name] = psycopg2.pool.SimpleConnectionPool(
                minconn=1,
                maxconn=10,
                **config
            )
            current_app.logger.info(f"Successfully created connection pool for {config['dbname']}")
        except Exception as e:
            current_app.logger.error(f"Failed to create pool for database {config['dbname']}: {e}")

def get_db_connection():
    for pool_name, pool in connection_pools.items():
        try:
            connection = pool.getconn()
            if connection:
                return connection
        except Exception as e:
            current_app.logger.error(f"Failed to get connection from pool {pool_name}: {e}")
    raise Exception("Could not connect to any database.")

def release_connection(connection):
    for pool in connection_pools.values():
        try:
            pool.putconn(connection)
            return
        except Exception as e:
            current_app.logger.error(f"Failed to release connection: {e}")
