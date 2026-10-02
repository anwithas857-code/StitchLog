from flask import Flask, render_template, request, redirect, url_for, flash, jsonify
import sqlite3
from pathlib import Path
from werkzeug.utils import secure_filename
from datetime import datetime
import uuid

BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "stitchlog.db"
UPLOAD_DIR = BASE_DIR / "uploads"
UPLOAD_DIR.mkdir(exist_ok=True)

ALLOWED_EXTENSIONS = {"jpg", "jpeg", "png", "webp"}

app = Flask(__name__)
app.secret_key = "change-this-later"

def db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = db()
    conn.executescript("""
    CREATE TABLE IF NOT EXISTS dresses (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        dress_name TEXT NOT NULL,
        dress_type TEXT,
        unit TEXT DEFAULT 'in',
        notes TEXT,
        photo TEXT,
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL
    );

    CREATE TABLE IF NOT EXISTS measurements (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        dress_id INTEGER NOT NULL,
        name TEXT NOT NULL,
        value TEXT NOT NULL,
        unit TEXT NOT NULL,
        FOREIGN KEY (dress_id) REFERENCES dresses(id) ON DELETE CASCADE
    );

    CREATE TABLE IF NOT EXISTS alterations (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        dress_id INTEGER NOT NULL,
        description TEXT NOT NULL,
        amount TEXT,
        unit TEXT,
        status TEXT DEFAULT 'Pending',
        FOREIGN KEY (dress_id) REFERENCES dresses(id) ON DELETE CASCADE
    );
    """)
    conn.commit()
    conn.close()

def allowed(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS

def save_photo(file):
    if not file or not file.filename:
        return None
    if not allowed(file.filename):
        return None
    ext = file.filename.rsplit(".", 1)[1].lower()
    name = f"{uuid.uuid4().hex}.{ext}"
    file.save(UPLOAD_DIR / name)
    return name

def get_dress(dress_id):
    conn = db()
    dress = conn.execute("SELECT * FROM dresses WHERE id=?", (dress_id,)).fetchone()
    measurements = conn.execute(
        "SELECT * FROM measurements WHERE dress_id=? ORDER BY id", (dress_id,)
    ).fetchall()
    alterations = conn.execute(
        "SELECT * FROM alterations WHERE dress_id=? ORDER BY id", (dress_id,)
    ).fetchall()
    conn.close()
    return dress, measurements, alterations

@app.route("/")
def index():
    q = request.args.get("q", "").strip()
    conn = db()
    if q:
        dresses = conn.execute("""
            SELECT * FROM dresses
            WHERE dress_name LIKE ? OR dress_type LIKE ? OR notes LIKE ?
            ORDER BY updated_at DESC
        """, (f"%{q}%", f"%{q}%", f"%{q}%")).fetchall()
    else:
        dresses = conn.execute(
            "SELECT * FROM dresses ORDER BY updated_at DESC"
        ).fetchall()
    count = conn.execute("SELECT COUNT(*) FROM dresses").fetchone()[0]
    conn.close()
    return render_template("index.html", dresses=dresses, count=count, q=q)

@app.route("/dress/<int:dress_id>")
def dress_detail(dress_id):
    dress, measurements, alterations = get_dress(dress_id)
    if not dress:
        return "Dress not found", 404
    return render_template(
        "detail.html",
        dress=dress,
        measurements=measurements,
        alterations=alterations
    )

@app.route("/add", methods=["GET", "POST"])
def add_dress():
    if request.method == "GET":
        return render_template("form.html", dress=None, measurements=[], alterations=[])

    name = request.form.get("dress_name", "").strip()
    if not name:
        flash("Dress name is required.")
        return redirect(url_for("add_dress"))

    now = datetime.now().isoformat(timespec="seconds")
    photo = save_photo(request.files.get("photo"))

    conn = db()
    cur = conn.execute("""
        INSERT INTO dresses (dress_name, dress_type, unit, notes, photo, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (
        name,
        request.form.get("dress_type", "").strip(),
        request.form.get("unit", "in"),
        request.form.get("notes", "").strip(),
        photo,
        now, now
    ))
    dress_id = cur.lastrowid

    save_measurements(conn, dress_id, request.form)
    save_alterations(conn, dress_id, request.form)
    conn.commit()
    conn.close()

    flash("Dress saved successfully.")
    return redirect(url_for("dress_detail", dress_id=dress_id))

@app.route("/edit/<int:dress_id>", methods=["GET", "POST"])
def edit_dress(dress_id):
    dress, measurements, alterations = get_dress(dress_id)
    if not dress:
        return "Dress not found", 404

    if request.method == "GET":
        return render_template(
            "form.html",
            dress=dress,
            measurements=measurements,
            alterations=alterations
        )

    name = request.form.get("dress_name", "").strip()
    if not name:
        flash("Dress name is required.")
        return redirect(url_for("edit_dress", dress_id=dress_id))

    photo = dress["photo"]
    new_photo = request.files.get("photo")
    saved = save_photo(new_photo)
    if saved:
        if photo:
            old = UPLOAD_DIR / photo
            if old.exists():
                old.unlink()
        photo = saved

    now = datetime.now().isoformat(timespec="seconds")
    conn = db()
    conn.execute("""
        UPDATE dresses
        SET dress_name=?, dress_type=?, unit=?, notes=?, photo=?, updated_at=?
        WHERE id=?
    """, (
        name,
        request.form.get("dress_type", "").strip(),
        request.form.get("unit", "in"),
        request.form.get("notes", "").strip(),
        photo,
        now,
        dress_id
    ))
    conn.execute("DELETE FROM measurements WHERE dress_id=?", (dress_id,))
    conn.execute("DELETE FROM alterations WHERE dress_id=?", (dress_id,))
    save_measurements(conn, dress_id, request.form)
    save_alterations(conn, dress_id, request.form)
    conn.commit()
    conn.close()

    flash("Dress updated successfully.")
    return redirect(url_for("dress_detail", dress_id=dress_id))

def save_measurements(conn, dress_id, form):
    names = form.getlist("measurement_name")
    values = form.getlist("measurement_value")
    units = form.getlist("measurement_unit")
    for name, value, unit in zip(names, values, units):
        name = name.strip()
        value = value.strip()
        if name and value:
            conn.execute("""
                INSERT INTO measurements (dress_id, name, value, unit)
                VALUES (?, ?, ?, ?)
            """, (dress_id, name, value, unit or "in"))

def save_alterations(conn, dress_id, form):
    descriptions = form.getlist("alteration_description")
    amounts = form.getlist("alteration_amount")
    units = form.getlist("alteration_unit")
    statuses = form.getlist("alteration_status")
    for desc, amount, unit, status in zip(descriptions, amounts, units, statuses):
        desc = desc.strip()
        if desc:
            conn.execute("""
                INSERT INTO alterations (dress_id, description, amount, unit, status)
                VALUES (?, ?, ?, ?, ?)
            """, (dress_id, desc, amount.strip(), unit, status or "Pending"))

@app.route("/copy/<int:dress_id>", methods=["POST"])
def copy_dress(dress_id):
    dress, measurements, _ = get_dress(dress_id)
    if not dress:
        return "Dress not found", 404

    now = datetime.now().isoformat(timespec="seconds")
    conn = db()
    cur = conn.execute("""
        INSERT INTO dresses (dress_name, dress_type, unit, notes, photo, created_at, updated_at)
        VALUES (?, ?, ?, ?, NULL, ?, ?)
    """, (
        f"{dress['dress_name']} - Copy",
        dress["dress_type"],
        dress["unit"],
        "",
        now, now
    ))
    new_id = cur.lastrowid

    for m in measurements:
        conn.execute("""
            INSERT INTO measurements (dress_id, name, value, unit)
            VALUES (?, ?, ?, ?)
        """, (new_id, m["name"], m["value"], m["unit"]))

    conn.commit()
    conn.close()
    return redirect(url_for("edit_dress", dress_id=new_id))

@app.route("/alteration/<int:alteration_id>/toggle", methods=["POST"])
def toggle_alteration(alteration_id):
    conn = db()
    row = conn.execute(
        "SELECT dress_id, status FROM alterations WHERE id=?", (alteration_id,)
    ).fetchone()
    if not row:
        conn.close()
        return jsonify({"error": "Not found"}), 404
    new_status = "Completed" if row["status"] != "Completed" else "Pending"
    conn.execute(
        "UPDATE alterations SET status=? WHERE id=?",
        (new_status, alteration_id)
    )
    conn.commit()
    conn.close()
    return jsonify({"status": new_status})

@app.route("/delete/<int:dress_id>", methods=["POST"])
def delete_dress(dress_id):
    conn = db()
    row = conn.execute("SELECT photo FROM dresses WHERE id=?", (dress_id,)).fetchone()
    if row and row["photo"]:
        p = UPLOAD_DIR / row["photo"]
        if p.exists():
            p.unlink()
    conn.execute("DELETE FROM measurements WHERE dress_id=?", (dress_id,))
    conn.execute("DELETE FROM alterations WHERE dress_id=?", (dress_id,))
    conn.execute("DELETE FROM dresses WHERE id=?", (dress_id,))
    conn.commit()
    conn.close()
    flash("Dress deleted.")
    return redirect(url_for("index"))

@app.route("/uploads/<filename>")
def uploaded_file(filename):
    from flask import send_from_directory
    return send_from_directory(UPLOAD_DIR, filename)

 init_db()
if __name__ == "__main__":
    app.run(debug=True)
