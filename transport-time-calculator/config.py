import os

class Config:
    DEBUG = os.getenv('DEBUG', True)
    # Add other global configurations here
