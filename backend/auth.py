"""
NuroTrack — Firebase Authentication Module
Handles:
- Token verification
- Auth middleware
- Auth-related API routes
"""

import functools
from datetime import datetime
from flask import request, jsonify
import firebase_admin.auth as fb_auth


# ─────────────────────────────────────────────
# TOKEN VERIFICATION
# ─────────────────────────────────────────────
def verify_token(id_token: str):
    """
    Verify Firebase ID token from frontend.
    Returns decoded token dict or None.
    """
    if not id_token or not isinstance(id_token, str):
        print("[Auth] Empty or invalid token format")
        return None

    try:
        decoded = fb_auth.verify_id_token(id_token, clock_skew_seconds=60)
        return decoded

    except fb_auth.ExpiredIdTokenError:
        print("[Auth] Token expired — frontend should refresh")
        return None

    except fb_auth.InvalidIdTokenError as e:
        print(f"[Auth] Invalid token: {e}")
        return None

    except fb_auth.CertificateFetchError as e:
        print(f"[Auth] Firebase cert fetch failed: {e}")
        return None

    except ValueError as e:
        print(f"[Auth] Malformed token: {e}")
        return None

    except Exception as e:
        print(f"[Auth] Unexpected error ({type(e).__name__}): {e}")
        return None


# ─────────────────────────────────────────────
# AUTH DECORATOR
# ─────────────────────────────────────────────
def require_auth(f):
    """
    Protect routes using Firebase ID token.

    Requires:
    Authorization: Bearer <id_token>
    """
    @functools.wraps(f)
    def decorated(*args, **kwargs):
        auth_header = request.headers.get("Authorization", "")

        if not auth_header.startswith("Bearer "):
            return jsonify({"error": "Missing or invalid Authorization header"}), 401

        token = auth_header.split(" ", 1)[1].strip()
        decoded = verify_token(token)

        if not decoded:
            return jsonify({"error": "Unauthorized — invalid or expired token"}), 401

        # Attach user info to request
        request.uid = decoded.get("uid")
        request.email = decoded.get("email", "unknown")

        return f(*args, **kwargs)

    return decorated


# ─────────────────────────────────────────────
# REGISTER ROUTES
# ─────────────────────────────────────────────
def register_auth_routes(app):
    """Call once inside Flask app setup"""

    @app.route("/api/auth/verify", methods=["POST"])
    def auth_verify():
        data = request.get_json(silent=True) or {}
        token = data.get("idToken", "")

        if not token:
            return jsonify({"valid": False, "error": "No token provided"}), 400

        decoded = verify_token(token)

        if not decoded:
            return jsonify({"valid": False, "error": "Invalid token"}), 401

        return jsonify({
            "valid": True,
            "uid": decoded.get("uid"),
            "email": decoded.get("email"),
            "name": decoded.get("name", ""),
            "verified_at": datetime.now().isoformat()
        })


    @app.route("/api/auth/me", methods=["GET"])
    @require_auth
    def auth_me():
        return jsonify({
            "uid": request.uid,
            "email": request.email
        })


    # ─────────────────────────────────────────────
    # DEBUG ROUTE (REMOVE IN PRODUCTION)
    # ─────────────────────────────────────────────
    @app.route("/api/auth/debug", methods=["GET"])
    def auth_debug():
        import base64
        import json as _json

        token = request.args.get("token", "")

        if not token:
            return jsonify({"error": "Provide ?token=<id_token>"}), 400

        # Decode without verification (just for inspection)
        try:
            parts = token.split(".")
            payload = parts[1] + "=="
            decoded_raw = _json.loads(base64.urlsafe_b64decode(payload))
        except Exception as e:
            decoded_raw = {"decode_error": str(e)}

        verified = verify_token(token)

        return jsonify({
            "jwt_payload_unverified": decoded_raw,
            "verify_result": verified if verified else "FAILED",
            "server_time_utc": datetime.utcnow().isoformat(),
            "token_iat": decoded_raw.get("iat"),
            "token_exp": decoded_raw.get("exp"),
            "token_aud": decoded_raw.get("aud"),
        })


    print("[Auth] Routes registered: /api/auth/verify, /api/auth/me, /api/auth/debug")