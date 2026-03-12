"""
PostgreSQL Database Client for HR Email Automation
"""
import psycopg2
from psycopg2 import pool
from typing import List, Dict, Any, Optional, Tuple
import logging

logger = logging.getLogger(__name__)


class PostgresClient:
    """PostgreSQL database client with connection pooling"""

    def __init__(self, host: str, port: int, database: str, user: str, password: str, min_conn: int = 1, max_conn: int = 10):
        """
        Initialize PostgreSQL client with connection pool

        Args:
            host: Database host
            port: Database port
            database: Database name
            user: Database user
            password: Database password
            min_conn: Minimum connections in pool
            max_conn: Maximum connections in pool
        """
        self.host = host
        self.port = port
        self.database = database
        self.user = user

        try:
            self.connection_pool = pool.ThreadedConnectionPool(
                minconn=min_conn,
                maxconn=max_conn,
                host=host,
                port=port,
                database=database,
                user=user,
                password=password
            )
            logger.info(f"Database connection pool initialized: {host}:{port}/{database}")
        except Exception as e:
            logger.error(f"Failed to initialize database connection pool: {e}")
            raise

    def get_connection(self):
        """Get a connection from the pool"""
        return self.connection_pool.getconn()

    def release_connection(self, conn):
        """Release a connection back to the pool"""
        self.connection_pool.putconn(conn)

    def execute_query(self, query: str, params: Optional[Tuple] = None) -> List[Dict[str, Any]]:
        """
        Execute a SELECT query and return results as list of dicts

        Args:
            query: SQL query string
            params: Query parameters (tuple)

        Returns:
            List of dictionaries with column names as keys
        """
        conn = None
        try:
            conn = self.get_connection()
            cursor = conn.cursor()

            if params:
                cursor.execute(query, params)
            else:
                cursor.execute(query)

            # Get column names
            columns = [desc[0] for desc in cursor.description] if cursor.description else []

            # Fetch all rows
            rows = cursor.fetchall()

            # Convert to list of dicts
            results = []
            for row in rows:
                results.append(dict(zip(columns, row)))

            cursor.close()
            return results

        except Exception as e:
            logger.error(f"Query execution error: {e}")
            logger.error(f"Query: {query}")
            if params:
                logger.error(f"Params: {params}")
            raise
        finally:
            if conn:
                self.release_connection(conn)

    def execute_update(self, query: str, params: Optional[Tuple] = None) -> int:
        """
        Execute an INSERT/UPDATE/DELETE query

        Args:
            query: SQL query string
            params: Query parameters (tuple)

        Returns:
            Number of rows affected
        """
        conn = None
        try:
            conn = self.get_connection()
            cursor = conn.cursor()

            if params:
                cursor.execute(query, params)
            else:
                cursor.execute(query)

            affected_rows = cursor.rowcount
            conn.commit()

            cursor.close()
            return affected_rows

        except Exception as e:
            if conn:
                conn.rollback()
            logger.error(f"Update execution error: {e}")
            logger.error(f"Query: {query}")
            if params:
                logger.error(f"Params: {params}")
            raise
        finally:
            if conn:
                self.release_connection(conn)

    def close_all_connections(self):
        """Close all connections in the pool"""
        if self.connection_pool:
            self.connection_pool.closeall()
            logger.info("All database connections closed")

    def __del__(self):
        """Cleanup on object destruction"""
        try:
            self.close_all_connections()
        except:
            pass
