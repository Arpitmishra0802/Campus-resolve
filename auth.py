"""
Campus Resolve - Authentication & Security Layer (auth.py)
Session management, role-based authorization, CSRF validation, and input verification.
"""

import re
import secrets
from functools import wraps
from flask import session, redirect, url_for, flash, request, abort, jsonify
from werkzeug.security import check_password_hash
from models import get_user_by_email, get_user_by_id, create_user

def generate_csrf_token():
    """Generates or retrieves CSRF token stored in current user session."""
    if '_csrf_token' not in session:
        session['_csrf_token'] = secrets.token_hex(24)
    return session['_csrf_token']

def validate_csrf():
    """Validates incoming CSRF token on state-changing requests."""
    if request.method in ['POST', 'PUT', 'DELETE', 'PATCH']:
        # Support token from form field or header
        token = request.form.get('csrf_token') or request.headers.get('X-CSRFToken')
        expected_token = session.get('_csrf_token')
        if not expected_token or not token or token != expected_token:
            if request.is_json or request.path.startswith('/api/'):
                return jsonify({'error': 'Invalid or missing CSRF token', 'status': 'forbidden'}), 403
            flash('Security validation failed (CSRF token mismatch). Please try again.', 'error')
            abort(403)

def get_current_user():
    """Returns the authenticated user dict from session or None."""
    user_id = session.get('user_id')
    if not user_id:
        return None
    return get_user_by_id(user_id)

def login_user(user):
    """Sets up a secure user session."""
    session.clear()
    session['user_id'] = user['id']
    session['user_name'] = user['name']
    session['user_email'] = user['email']
    session['user_role'] = user['role']
    generate_csrf_token()

def logout_user():
    """Clears the session."""
    session.clear()

def login_required(f):
    """Decorator requiring an authenticated user."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get('user_id'):
            flash('Please log in to access this page.', 'warning')
            return redirect(url_for('login_view', next=request.url))
        return f(*args, **kwargs)
    return decorated_function

def student_required(f):
    """Decorator ensuring only students can access."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get('user_id'):
            flash('Please log in to continue.', 'warning')
            return redirect(url_for('login_view', next=request.url))
        if session.get('user_role') != 'student':
            flash('Access denied. This section is reserved for students.', 'error')
            return redirect(url_for('management_portal_view'))
        return f(*args, **kwargs)
    return decorated_function

def management_required(f):
    """Decorator ensuring only management accounts can access."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get('user_id'):
            flash('Please log in with management credentials.', 'warning')
            return redirect(url_for('login_view', next=request.url))
        if session.get('user_role') != 'management':
            flash('Unauthorized access. Management privileges required.', 'error')
            return redirect(url_for('student_dashboard_view'))
        return f(*args, **kwargs)
    return decorated_function

def validate_registration_input(name, email, password, confirm_password):
    """Validates registration input fields."""
    errors = []
    
    if not name or len(name.strip()) < 2:
        errors.append("Full name must be at least 2 characters.")
        
    email_clean = email.strip() if email else ""
    email_regex = r'^[\w\.-]+@[\w\.-]+\.\w+$'
    if not email_clean or not re.match(email_regex, email_clean):
        errors.append("Please enter a valid email address.")
        
    if not password or len(password) < 6:
        errors.append("Password must be at least 6 characters.")
        
    if password != confirm_password:
        errors.append("Passwords do not match.")
        
    return errors

