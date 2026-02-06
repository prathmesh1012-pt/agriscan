
from mysql.connector import Error
import os
import mysql.connector
from dotenv import load_dotenv

load_dotenv()
def get_db_connection():
    try:
        connection = mysql.connector.connect(
        host=os.getenv("DB_HOST"),
        user=os.getenv("DB_USER"),
        password=os.getenv("DB_PASSWORD"),
        port=os.getenv("DB_PORT"),
        database=os.getenv("DB_NAME")
        )
        
        if connection.is_connected():
            return connection

    except Error as e:
        print(f"Error while connecting to MySQL: {e}")
        return None