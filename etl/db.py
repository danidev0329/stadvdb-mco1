import mysql.connector
from etl import config

def connect(database: str):
    return mysql.connector.connect(database=database, **config.MYSQL)

def source():
    return connect(config.SOURCE_DB)

def warehouse():
    return connect(config.WAREHOUSE_DB)
