import os


class Config:
    SECRET_KEY = os.getenv("SECRET_KEY", "dev-secret-key")
    SQLALCHEMY_DATABASE_URI = os.getenv("DATABASE_URL", "sqlite:///chordlift.db")
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    MAX_UPLOAD_MB = int(os.getenv("MAX_UPLOAD_MB", 10))
    MAX_CONTENT_LENGTH = MAX_UPLOAD_MB * 1024 * 1024
    ACOUSTID_API_KEY = os.getenv("ACOUSTID_API_KEY", "")
