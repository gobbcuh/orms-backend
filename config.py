import os
from dotenv import load_dotenv
import mysql.connector
from mysql.connector import pooling

load_dotenv()

class Config:
    """Application configuration"""
    
    # flask
    SECRET_KEY = os.getenv('SECRET_KEY', 'dev-secret-key')
    DEBUG = os.getenv('FLASK_DEBUG', 'True') == 'True'
    
    # database
    DB_HOST = os.getenv('DB_HOST', 'localhost')
    DB_USER = os.getenv('DB_USER', 'root')
    DB_PASSWORD = os.getenv('DB_PASSWORD')
    DB_NAME = os.getenv('DB_NAME', 'orms_db')
    DB_CHARSET = os.getenv('DB_CHARSET', 'utf8mb4')
    
    # JWT
    JWT_SECRET_KEY = os.getenv('JWT_SECRET_KEY', 'dev-jwt-secret')
    JWT_EXPIRATION_HOURS = int(os.getenv('JWT_EXPIRATION_HOURS', 24))
    
    # CORS
    CORS_ORIGINS = os.getenv('CORS_ORIGINS', 'http://localhost:8080').split(',')
    
    # server
    PORT = int(os.getenv('PORT', 5000))


class Database:
    """Database connection pool manager"""
    
    _connection_pool = None
    
    @classmethod
    def initialize_pool(cls):
        """Initialize the connection pool"""
        if cls._connection_pool is None:
            try:
                cls._connection_pool = pooling.MySQLConnectionPool(
                    pool_name="orms_pool",
                    pool_size=5,
                    pool_reset_session=True,
                    host=Config.DB_HOST,
                    user=Config.DB_USER,
                    password=Config.DB_PASSWORD,
                    database=Config.DB_NAME,
                    charset=Config.DB_CHARSET,
                    collation='utf8mb4_unicode_ci'
                )
                print("- Database connection pool initialized")
            except mysql.connector.Error as err:
                print(f"- Error initializing connection pool: {err}")
                raise
    
    @classmethod
    def get_connection(cls):
        """Get a connection from the pool"""
        if cls._connection_pool is None:
            cls.initialize_pool()
        
        try:
            connection = cls._connection_pool.get_connection()
            return connection
        except mysql.connector.Error as err:
            print(f"- Error getting connection: {err}")
            raise
    
    @classmethod
    def execute_query(cls, query, params=None, fetch_one=False, fetch_all=True, commit=False):
        """
        Execute a database query
        
        Args:
            query: SQL query string
            params: Query parameters (tuple or dict)
            fetch_one: Return single row
            fetch_all: Return all rows
            commit: Commit the transaction (for INSERT/UPDATE/DELETE)
        
        Returns:
            Query results or None
        """
        connection = None
        cursor = None
        
        try:
            connection = cls.get_connection()
            cursor = connection.cursor(dictionary=True)
            
            cursor.execute(query, params or ())
            
            if commit:
                connection.commit()
                return cursor.lastrowid  # return inserted id for INSERT queries
            
            if fetch_one:
                return cursor.fetchone()
            
            if fetch_all:
                return cursor.fetchall()
            
            return None
            
        except mysql.connector.Error as err:
            print(f"- Database error: {err}")
            if connection:
                connection.rollback()
            raise
            
        finally:
            if cursor:
                cursor.close()
            if connection:
                connection.close()


# Test function
def test_connection():
    """Test database connection"""
    try:
        Database.initialize_pool()
        result = Database.execute_query("SELECT COUNT(*) as count FROM patients")
        print(f"- Connection successful! Patient count: {result[0]['count']}")
        return True
    except Exception as e:
        print(f"- Connection failed: {e}")
        return False


if __name__ == "__main__":
    print("Testing database connection...")
    test_connection()