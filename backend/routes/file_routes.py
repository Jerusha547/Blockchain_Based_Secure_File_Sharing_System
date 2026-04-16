"""
File management routes:
  POST   /files/upload
  GET    /files/download/<file_id>
  GET    /files/verify/<file_id>
  GET    /files/list
  POST   /files/share
  DELETE /files/revoke
"""

import os
import hashlib
import uuid
from flask import Blueprint, request, jsonify, send_file
from database.db import get_db
from crypto.encryption import encrypt_file, decrypt_file
from blockchain.web3_client import store_hash, verify_hash, is_blockchain_available
from routes.auth_routes import get_current_user
import io

file_bp = Blueprint("files", __name__)

STORAGE_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "storage")
os.makedirs(STORAGE_DIR, exist_ok=True)


# ── Auth guard ────────────────────────────────────────────────────────────────

def _require_login():
    username = get_current_user()
    if not username:
        return jsonify({"success": False, "message": "Authentication required. Please login."}), 401
    return None


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


# ── Upload ────────────────────────────────────────────────────────────────────

@file_bp.route("/upload", methods=["POST"])
def upload():
    err = _require_login()
    if err: return err

    if "file" not in request.files:
        return jsonify({"success": False, "message": "No file provided."}), 400

    f             = request.files["file"]
    original_name = f.filename
    if not original_name:
        return jsonify({"success": False, "message": "Empty filename."}), 400

    raw_bytes = f.read()

    # 1. Encrypt
    encrypted_bytes, key_hex = encrypt_file(raw_bytes)

    # 2. SHA-256 of the encrypted file
    file_hash = _sha256(encrypted_bytes)

    # 3. Store on blockchain
    blockchain_available = is_blockchain_available()
    tx_hash = "BLOCKCHAIN_OFFLINE"
    if blockchain_available:
        try:
            tx_hash = store_hash(file_hash)
        except Exception as e:
            return jsonify({"success": False,
                            "message": f"Blockchain error: {str(e)}"}), 500
    else:
        print("⚠️  Ganache not running — skipping on-chain storage.")

    # 4. Save encrypted file to disk
    stored_name = f"{uuid.uuid4().hex}_{original_name}.enc"
    file_path   = os.path.join(STORAGE_DIR, stored_name)
    with open(file_path, "wb") as fp:
        fp.write(encrypted_bytes)

    # 5. Persist metadata in DB
    username = get_current_user()
    db = get_db()
    db.execute(
        """INSERT INTO files
           (owner_username, original_name, stored_name, file_path,
            blockchain_hash, aes_key_hex)
           VALUES (?,?,?,?,?,?)""",
        (username, original_name, stored_name, file_path, file_hash, key_hex)
    )
    db.commit()
    db.close()

    return jsonify({
        "success":    True,
        "message":    "File uploaded, encrypted and stored on blockchain.",
        "file_hash":  file_hash,
        "tx_hash":    tx_hash,
        "blockchain": blockchain_available
    })


# ── List ──────────────────────────────────────────────────────────────────────

@file_bp.route("/list", methods=["GET"])
def list_files():
    err = _require_login()
    if err: return err

    username = get_current_user()
    db       = get_db()

    # Files owned by user
    owned = db.execute(
        "SELECT id, original_name, blockchain_hash, uploaded_at FROM files WHERE owner_username=?",
        (username,)
    ).fetchall()

    # Files shared with user
    shared = db.execute(
        """SELECT f.id, f.original_name, f.blockchain_hash, f.uploaded_at, fp.granted_by
           FROM files f
           JOIN file_permissions fp ON f.id = fp.file_id
           WHERE fp.granted_to=?""",
        (username,)
    ).fetchall()
    db.close()

    return jsonify({
        "success": True,
        "owned":  [dict(r) for r in owned],
        "shared": [dict(r) for r in shared]
    })


# ── Download ──────────────────────────────────────────────────────────────────

@file_bp.route("/download/<int:file_id>", methods=["GET"])
def download(file_id):
    err = _require_login()
    if err: return err

    username = get_current_user()
    db       = get_db()
    row      = db.execute("SELECT * FROM files WHERE id=?", (file_id,)).fetchone()
    db.close()

    if not row:
        return jsonify({"success": False, "message": "File not found."}), 404

    # Access control
    if row["owner_username"] != username:
        db  = get_db()
        perm = db.execute(
            "SELECT 1 FROM file_permissions WHERE file_id=? AND granted_to=?",
            (file_id, username)
        ).fetchone()
        db.close()
        if not perm:
            return jsonify({"success": False,
                            "message": "Access denied. You do not have permission."}), 403

    # Read + decrypt
    try:
        with open(row["file_path"], "rb") as fp:
            encrypted_bytes = fp.read()
        original_bytes = decrypt_file(encrypted_bytes, row["aes_key_hex"])
    except FileNotFoundError:
        return jsonify({"success": False, "message": "Encrypted file missing on server."}), 500
    except ValueError as e:
        return jsonify({"success": False, "message": str(e)}), 500

    return send_file(
        io.BytesIO(original_bytes),
        as_attachment=True,
        download_name=row["original_name"],
        mimetype="application/octet-stream"
    )


# ── Verify ────────────────────────────────────────────────────────────────────

@file_bp.route("/verify/<int:file_id>", methods=["GET"])
def verify(file_id):
    err = _require_login()
    if err: return err

    username = get_current_user()
    db       = get_db()
    row      = db.execute("SELECT * FROM files WHERE id=?", (file_id,)).fetchone()
    db.close()

    if not row:
        return jsonify({"success": False, "message": "File not found."}), 404

    # Access control (owner or shared)
    if row["owner_username"] != username:
        db   = get_db()
        perm = db.execute(
            "SELECT 1 FROM file_permissions WHERE file_id=? AND granted_to=?",
            (file_id, username)
        ).fetchone()
        db.close()
        if not perm:
            return jsonify({"success": False, "message": "Access denied."}), 403

    # Recompute hash of the stored encrypted file
    try:
        with open(row["file_path"], "rb") as fp:
            current_hash = _sha256(fp.read())
    except FileNotFoundError:
        return jsonify({"success": False, "message": "File missing on server."}), 500

    db_hash       = row["blockchain_hash"]
    integrity_ok  = current_hash == db_hash
    blockchain_ok = None

    if is_blockchain_available():
        try:
            # Find which on-chain index this file sits at by iterating
            # (simple linear scan — fine for demo scale)
            from blockchain.web3_client import _load_contract, _connect
            contract        = _load_contract()
            _, account      = _connect()
            count           = contract.functions.getFileCount(account).call()
            blockchain_ok   = False
            for i in range(count):
                h, _ = contract.functions.getFile(account, i).call()
                if h == db_hash:
                    blockchain_ok = True
                    break
        except Exception:
            blockchain_ok = None

    return jsonify({
        "success":      True,
        "integrity_ok": integrity_ok,
        "blockchain_ok": blockchain_ok,
        "stored_hash":  db_hash,
        "current_hash": current_hash,
        "message": (
            "✅ File verified. Integrity intact." if integrity_ok
            else "❌ File may be tampered!"
        )
    })


# ── Share ─────────────────────────────────────────────────────────────────────

@file_bp.route("/share", methods=["POST"])
def share():
    err = _require_login()
    if err: return err

    data     = request.get_json(silent=True) or {}
    file_id  = data.get("file_id")
    share_to = data.get("share_to", "").strip()

    if not file_id or not share_to:
        return jsonify({"success": False,
                        "message": "file_id and share_to are required."}), 400

    username = get_current_user()
    db       = get_db()
    row      = db.execute("SELECT * FROM files WHERE id=?", (file_id,)).fetchone()

    if not row:
        db.close()
        return jsonify({"success": False, "message": "File not found."}), 404
    if row["owner_username"] != username:
        db.close()
        return jsonify({"success": False,
                        "message": "Only the owner can share this file."}), 403

    target = db.execute("SELECT 1 FROM users WHERE username=?", (share_to,)).fetchone()
    if not target:
        db.close()
        return jsonify({"success": False, "message": f"User '{share_to}' not found."}), 404

    try:
        db.execute(
            "INSERT INTO file_permissions(file_id, granted_to, granted_by) VALUES(?,?,?)",
            (file_id, share_to, username)
        )
        db.commit()
    except Exception:
        db.close()
        return jsonify({"success": False,
                        "message": f"Already shared with '{share_to}'."}), 409
    db.close()
    return jsonify({"success": True,
                    "message": f"File shared with '{share_to}' successfully."})


# ── Revoke ────────────────────────────────────────────────────────────────────

@file_bp.route("/revoke", methods=["DELETE"])
def revoke():
    err = _require_login()
    if err: return err

    data      = request.get_json(silent=True) or {}
    file_id   = data.get("file_id")
    revoke_from = data.get("revoke_from", "").strip()

    if not file_id or not revoke_from:
        return jsonify({"success": False,
                        "message": "file_id and revoke_from are required."}), 400

    username = get_current_user()
    db       = get_db()
    row      = db.execute("SELECT * FROM files WHERE id=?", (file_id,)).fetchone()

    if not row:
        db.close()
        return jsonify({"success": False, "message": "File not found."}), 404
    if row["owner_username"] != username:
        db.close()
        return jsonify({"success": False,
                        "message": "Only the owner can revoke access."}), 403

    db.execute(
        "DELETE FROM file_permissions WHERE file_id=? AND granted_to=?",
        (file_id, revoke_from)
    )
    db.commit()
    db.close()
    return jsonify({"success": True,
                    "message": f"Access revoked for '{revoke_from}'."})
