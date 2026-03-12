"""HR Email Automation System"""

__version__ = "1.0.0"

from .email_parser import EmailParser, EmailProcessor
from .database import PostgresClient

__all__ = ['EmailParser', 'EmailProcessor', 'PostgresClient']
