import os
import logging
from functools import wraps
from flask import request, jsonify

AUTH_USERNAME = os.environ.get('AUTH_USERNAME')
AUTH_PASSWORD = os.environ.get('AUTH_PASSWORD')

# assert that both are set, otherwise app would run without authentication
assert (AUTH_USERNAME and AUTH_PASSWORD), "Error: AUTH_USERNAME and AUTH_PASSWORD must be set in environment variables or .env file"


def check_auth(username, password):
    # validates credentials against env vars
    return username == AUTH_USERNAME and password == AUTH_PASSWORD


def authenticate():
    # returns 401 with WWW-Authenticate header, which triggers the browser's login popup
    return jsonify({'message': 'Authentication required.'}), 401, {'WWW-Authenticate': 'Basic realm="Login Required"'}


def requires_auth(f):
    # decorator — put @requires_auth above any route that should require login
    @wraps(f)
    def decorated(*args, **kwargs):
        auth = request.authorization
        if not auth or not check_auth(auth.username, auth.password):
            logging.warning(f"Failed auth attempt for user: {auth.username if auth else 'no credentials'}")
            return authenticate()
        return f(*args, **kwargs)
    return decorated
