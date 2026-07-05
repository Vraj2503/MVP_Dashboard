import pymysql
import os
from dotenv import load_dotenv

load_dotenv()

# Extract connection details
db_url = os.getenv("DATABASE_URL", "mysql+pymysql://root:password@localhost/school_db")
# parse url roughly: mysql+pymysql://root:password@localhost/school_db
user_pass = db_url.split('://')[1].split('@')[0]
user = user_pass.split(':')[0]
password = user_pass.split(':')[1] if ':' in user_pass else ""
host_db = db_url.split('@')[1]
host = host_db.split('/')[0]
db_name = host_db.split('/')[1]

try:
    connection = pymysql.connect(host=host, user=user, password=password)
    cursor = connection.cursor()
    cursor.execute(f"CREATE DATABASE IF NOT EXISTS {db_name}")
    print(f"Database {db_name} created or already exists.")
    cursor.close()
    connection.close()
except Exception as e:
    print(f"Error creating database: {e}")
