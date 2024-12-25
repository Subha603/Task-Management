import os
from datetime import timedelta

class Config:
    # Flask configuration
    SECRET_KEY = os.environ.get('SECRET_KEY', '123')  # Change this in production
    
    # Session configuration
    PERMANENT_SESSION_LIFETIME = timedelta(days=5)
    SESSION_TYPE = 'filesystem'
    
    # Database configuration
    DATABASE_CONFIG = {
        'host': os.environ.get('DB_HOST', 'localhost'),
        'user': os.environ.get('DB_USER', 'postgres'),
        'password': os.environ.get('DB_PASSWORD', 'db password'),
        'dbname': os.environ.get('DB_NAME', 'todo_db')
    }
    
    # Google OAuth configuration
    GOOGLE_CLIENT_ID = os.environ.get('GOOGLE_CLIENT_ID')
    GOOGLE_CLIENT_SECRET = os.environ.get('GOOGLE_CLIENT_SECRET')