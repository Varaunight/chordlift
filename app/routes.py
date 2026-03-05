import os
import uuid
import threading
import tempfile
from flask import (
    Blueprint, render_template, request, jsonify,
    redirect, url_for, flash, send_file, abort
)
from flask_login import login_user, logout_user, login_required, current_user
from app import db, bcrypt
from app.models import User, Track
from app.audio import process_audio
from app.export import generate_pdf, generate_txt

main = Blueprint("main", __name__)
auth = Blueprint("auth", __name__)
export = Blueprint("export", __name__)

# In-memory job store: { job_id: { status, result, error } }
jobs = {}


# ---------------------------------------------------------------------------
# Main routes
# ---------------------------------------------------------------------------

@main.route("/")
def index():
    return render_template("index.html")


@main.route("/upload", methods=["POST"])
def upload():
    if "file" not in request.files:
        return jsonify({"error": "No file provided"}), 400

    file = request.files["file"]
    if not file.filename.lower().endswith(".mp3"):
        return jsonify({"error": "Only MP3 files are accepted"}), 400

    separate_vocals = request.form.get("separate_vocals") == "true"

    # Save to a temp file
    tmp = tempfile.NamedTemporaryFile(suffix=".mp3", delete=False)
    file.save(tmp.name)
    tmp.close()

    job_id = str(uuid.uuid4())
    jobs[job_id] = {"status": "processing", "stage": "Starting…", "result": None, "error": None}

    # Capture user ID now — current_user proxy is not available inside the thread
    user_id = current_user.id if current_user.is_authenticated else None
    original_filename = file.filename

    def run():
        try:
            result = process_audio(tmp.name, separate_vocals=separate_vocals, job_id=job_id, jobs=jobs)
            jobs[job_id]["status"] = "complete"
            jobs[job_id]["result"] = result

            # Save to history if logged in
            if user_id is not None:
                from app import create_app
                with create_app().app_context():
                    track = Track(
                        user_id=user_id,
                        filename=original_filename,
                        detected_title=result.get("title"),
                        detected_artist=result.get("artist"),
                        key=result.get("key"),
                        bpm=result.get("bpm"),
                    )
                    track.set_chord_data(result.get("chords", []))
                    db.session.add(track)
                    db.session.commit()
        except Exception as e:
            jobs[job_id]["status"] = "error"
            jobs[job_id]["error"] = str(e)
        finally:
            try:
                os.unlink(tmp.name)
            except OSError:
                pass

    threading.Thread(target=run, daemon=True).start()
    return jsonify({"job_id": job_id, "status": "processing"})


@main.route("/status/<job_id>")
def status(job_id):
    job = jobs.get(job_id)
    if not job:
        return jsonify({"error": "Job not found"}), 404
    if job["status"] == "processing":
        return jsonify({"status": "processing", "stage": job.get("stage", "Processing…")})
    if job["status"] == "error":
        return jsonify({"status": "error", "message": job["error"]})
    return jsonify({"status": "complete", "result": job["result"]})


@main.route("/history")
@login_required
def history():
    tracks = Track.query.filter_by(user_id=current_user.id).order_by(Track.created_at.desc()).all()
    return render_template("history.html", tracks=tracks)


@main.route("/history/<int:track_id>")
@login_required
def history_track(track_id):
    track = Track.query.filter_by(id=track_id, user_id=current_user.id).first_or_404()
    return render_template("index.html", saved_track=track)


# ---------------------------------------------------------------------------
# Auth routes
# ---------------------------------------------------------------------------

@auth.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        if not email or not password:
            flash("Email and password are required.", "error")
            return render_template("register.html")
        if User.query.filter_by(email=email).first():
            flash("An account with that email already exists.", "error")
            return render_template("register.html")
        hashed = bcrypt.generate_password_hash(password).decode("utf-8")
        user = User(email=email, password_hash=hashed)
        db.session.add(user)
        db.session.commit()
        login_user(user)
        return redirect(url_for("main.index"))
    return render_template("register.html")


@auth.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        user = User.query.filter_by(email=email).first()
        if user and bcrypt.check_password_hash(user.password_hash, password):
            login_user(user)
            return redirect(url_for("main.index"))
        flash("Invalid email or password.", "error")
    return render_template("login.html")


@auth.route("/logout")
@login_required
def logout():
    logout_user()
    return redirect(url_for("main.index"))


# ---------------------------------------------------------------------------
# Export routes
# ---------------------------------------------------------------------------

@export.route("/export/pdf", methods=["POST"])
def export_pdf():
    data = request.get_json()
    if not data:
        abort(400)
    pdf_bytes = generate_pdf(data)
    filename = f"{data.get('title', 'track')}-chords.pdf".replace(" ", "-").lower()
    tmp = tempfile.NamedTemporaryFile(suffix=".pdf", delete=False)
    tmp.write(pdf_bytes)
    tmp.close()
    return send_file(tmp.name, mimetype="application/pdf", as_attachment=True, download_name=filename)


@export.route("/export/txt", methods=["POST"])
def export_txt():
    data = request.get_json()
    if not data:
        abort(400)
    txt = generate_txt(data)
    filename = f"{data.get('title', 'track')}-chords.txt".replace(" ", "-").lower()
    tmp = tempfile.NamedTemporaryFile(suffix=".txt", mode="w", delete=False, encoding="utf-8")
    tmp.write(txt)
    tmp.close()
    return send_file(tmp.name, mimetype="text/plain", as_attachment=True, download_name=filename)
