import sqlite3

from ..configs import config

def create_database(db_path=config.DATABASE_PATH, schema=config.DATABASE_SCHEMA):
    """
    Create a new SQLite database based on the provided schema.

    :param db_path: Path to the SQLite database file.
    :param schema: SQL schema to create tables.
    """
    connection = sqlite3.connect(db_path)
    with connection:
        connection.executescript(schema)

def setup_app(app_config):
    """
    Set up the application including the database.

    :param app_config: Configuration dictionary for the application.
    """
    create_database(app_config['DATABASE_PATH'], app_config['DATABASE_SCHEMA'])
    # Additional setup tasks can be added here


