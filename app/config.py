import os

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'dev-key-default'
    TEMPLATES_AUTO_RELOAD = True
    DEBUG = True