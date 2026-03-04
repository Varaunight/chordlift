from flask_login import UserMixin
from app import db
import json
from datetime import datetime


class User(UserMixin, db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(150), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    tracks = db.relationship("Track", backref="user", lazy=True)


class Track(db.Model):
    __tablename__ = "tracks"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    filename = db.Column(db.String(255), nullable=False)
    detected_title = db.Column(db.String(255))
    detected_artist = db.Column(db.String(255))
    key = db.Column(db.String(10))
    bpm = db.Column(db.Float)
    chord_data = db.Column(db.Text)  # JSON string
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def set_chord_data(self, data):
        self.chord_data = json.dumps(data)

    def get_chord_data(self):
        if self.chord_data:
            return json.loads(self.chord_data)
        return []
