"""
Campus Resolve — Smart Complaint & Grievance Management System
Main Flask Application Entry Point (app.py)
"""

import os
import uuid
from flask import (
    Flask, render_template, request, redirect, url_for, flash, 
    session, jsonify, abort, send_from_directory
)
from werkzeug.utils import secure_filename
from werkzeug.security import check_password_hash

from models import (
    init_db, get_db, create_user, get_user_by_email, get_user_by_id,
    create_complaint, get_complaint_by_ticket_id, get_complaint_timeline,
    get_student_complaints, get_all_complaints, get_complaint_counts,
    update_complaint_status_and_remarks, UPLOAD_DIR
)
from auth import (
    generate_csrf_token, validate_csrf, login_user, logout_user,
    get_current_user, login_required, student_required, management_required,
    validate_registration_input
)
from ai_model.classifier import predict_complaint_category

# Detect Vercel environment
IS_VERCEL = bool(os.environ.get("VERCEL") or os.environ.get("VERCEL_ENV"))

# Initialize Flask App
app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'campus-resolve-dev-secret-key-2026')
app.config['MAX_CONTENT_LENGTH'] = 5 * 1024 * 1024  # 5 MB max limit
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'webp'}

# Upload folder: /tmp/uploads on Vercel, static/uploads locally
if IS_VERCEL:
    app.config['UPLOAD_FOLDER'] = '/tmp/uploads'
else:
    app.config['UPLOAD_FOLDER'] = os.path.join(app.root_path, 'static', 'uploads')

# Ensure upload directory exists
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

# Auto-initialize database and create admin account on every cold start
def _bootstrap():
    init_db()
    # Ensure management account always exists (important on Vercel cold starts)
    admin = get_user_by_email("admin@campus.edu")
    if not admin:
        create_user("Estate & Facilities Officer", "admin@campus.edu",
                    os.environ.get("ADMIN_PASSWORD", "Admin@123"), role="management")

_bootstrap()

# Helper function to validate file extensions
def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# Route to serve uploaded complaint photos (from /tmp on Vercel, static/uploads locally)
@app.route('/uploads/<path:filename>')
@login_required
def serve_upload(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

# Helper function to validate file extensions
def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# Template context processors
@app.context_processor
def inject_global_template_data():
    return {
        'csrf_token': generate_csrf_token,
        'current_user': get_current_user(),
        'year': 2026
    }

# CSRF Protection Middleware
@app.before_request
def csrf_protect():
    # Only validate on unsafe methods
    if request.method in ['POST', 'PUT', 'DELETE', 'PATCH']:
        # Exempt predicting API if user is authenticated and token in header
        validate_csrf()

# --- Public & Auth Routes ---

@app.route('/')
def landing_view():
    """Screen 1: Landing Page."""
    return render_template('landing.html')

@app.route('/login', methods=['GET', 'POST'])
def login_view():
    """Screen 2: Login Page."""
    if request.method == 'POST':
        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')

        if not email or not password:
            flash('Please provide both your email address and password.', 'error')
            return render_template('login.html'), 400

        user = get_user_by_email(email)
        if not user or not check_password_hash(user['password_hash'], password):
            flash('Invalid email address or password. Please try again.', 'error')
            return render_template('login.html'), 401

        # Establish session
        login_user(user)
        flash(f'Welcome back, {user["name"]}! Successfully authenticated.', 'success')

        # Role-based redirection
        next_page = request.args.get('next')
        if next_page and not next_page.startswith('http'):
            return redirect(next_page)

        if user['role'] == 'management':
            return redirect(url_for('management_portal_view'))
        else:
            return redirect(url_for('student_dashboard_view'))

    # If already logged in, redirect to appropriate portal
    if session.get('user_id'):
        if session.get('user_role') == 'management':
            return redirect(url_for('management_portal_view'))
        return redirect(url_for('student_dashboard_view'))

    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register_view():
    """Screen 3: Student Registration Page."""
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')
        confirm_password = request.form.get('confirm_password', '')

        # Server-side validation
        errors = validate_registration_input(name, email, password, confirm_password)
        if errors:
            for err in errors:
                flash(err, 'error')
            return render_template('register.html'), 400

        # Check existing email
        existing_user = get_user_by_email(email)
        if existing_user:
            flash('An account with this email address already exists. Please log in.', 'warning')
            return render_template('register.html'), 409

        # Create student account
        user_id = create_user(name, email, password, role='student')
        if not user_id:
            flash('Failed to create account due to a database error. Please try again.', 'error')
            return render_template('register.html'), 500

        # Auto-login newly registered student
        new_user = get_user_by_id(user_id)
        login_user(new_user)
        flash('Registration successful! Welcome to Campus Resolve.', 'success')
        return redirect(url_for('student_dashboard_view'))

    if session.get('user_id'):
        return redirect(url_for('student_dashboard_view'))

    return render_template('register.html')

@app.route('/logout')
def logout_view():
    """Logs out user and clears session."""
    logout_user()
    flash('You have been logged out securely.', 'info')
    return redirect(url_for('landing_view'))

# --- Student Features ---

@app.route('/dashboard')
@student_required
def student_dashboard_view():
    """Screen 4: Student Dashboard with real database counts, complaints feed, search and filters."""
    student_id = session['user_id']
    search = request.args.get('search', '').strip()
    status = request.args.get('status', 'All')
    category = request.args.get('category', 'All')

    counts = get_complaint_counts(student_id=student_id)
    complaints = get_student_complaints(
        student_id=student_id,
        search=search if search else None,
        status=status,
        category=category
    )

    return render_template(
        'student_dashboard.html',
        counts=counts,
        complaints=complaints,
        search=search,
        selected_status=status,
        selected_category=category
    )

@app.route('/complaints/new', methods=['GET', 'POST'])
@student_required
def new_complaint_view():
    """Screen 5: Submit a Complaint with photo upload and AI suggestion."""
    if request.method == 'POST':
        student_id = session['user_id']
        title = request.form.get('title', '').strip()
        location = request.form.get('location', '').strip()
        description = request.form.get('description', '').strip()
        category = request.form.get('category', '').strip()

        # Input validation
        if not title or len(title) < 3:
            flash('Grievance title must be at least 3 characters.', 'error')
            return render_template('new_complaint.html'), 400

        if not location:
            flash('Please specify the campus location or room.', 'error')
            return render_template('new_complaint.html'), 400

        if not description or len(description) < 10:
            flash('Please provide a detailed incident description (at least 10 characters).', 'error')
            return render_template('new_complaint.html'), 400

        if not category:
            flash('Please select an incident category.', 'error')
            return render_template('new_complaint.html'), 400

        # Handle photo upload safely
        image_db_path = None
        photo_file = request.files.get('photo')
        if photo_file and photo_file.filename != '':
            if not allowed_file(photo_file.filename):
                flash('Invalid image format! Only JPG, JPEG, PNG, and WEBP are permitted.', 'error')
                return render_template('new_complaint.html'), 400

            # Safe random filename to prevent collisions and path traversal
            ext = photo_file.filename.rsplit('.', 1)[1].lower()
            safe_name = f"{uuid.uuid4().hex}_{secure_filename(photo_file.filename)}"
            if not safe_name.endswith(f".{ext}"):
                safe_name = f"{safe_name}.{ext}"

            save_dest = os.path.join(app.config['UPLOAD_FOLDER'], safe_name)
            photo_file.save(save_dest)
            # Store relative path for template serving
            image_db_path = f"uploads/{safe_name}"

        # Create complaint in database
        try:
            ticket_id = create_complaint(
                student_id=student_id,
                title=title,
                description=description,
                category=category,
                location=location,
                image=image_db_path,
                priority='Medium'
            )
            flash(f'Grievance submitted successfully! Ticket ID #{ticket_id} has been generated.', 'success')
            return redirect(url_for('complaint_detail_view', ticket_id=ticket_id))
        except Exception as e:
            flash(f'An unexpected error occurred while saving your grievance: {str(e)}', 'error')
            return render_template('new_complaint.html'), 500

    return render_template('new_complaint.html')

@app.route('/complaints/<ticket_id>')
@login_required
def complaint_detail_view(ticket_id):
    """Screen 6: Complaint details and tracking timeline with authorization checks."""
    complaint = get_complaint_by_ticket_id(ticket_id)
    if not complaint:
        abort(404)

    # Authorization Check: Students can only view their own complaints
    current_user_role = session.get('user_role')
    current_user_id = session.get('user_id')

    if current_user_role == 'student' and complaint['student_id'] != current_user_id:
        flash('Unauthorized access: You are only permitted to view your own grievances.', 'error')
        abort(403)

    timeline = get_complaint_timeline(complaint['id'])
    return render_template('complaint_detail.html', complaint=complaint, timeline=timeline)

# --- Management Features ---

@app.route('/management')
@management_required
def management_portal_view():
    """Screen 7: Management Dashboard and queue triage view matching Stitch original."""
    search = request.args.get('search', '').strip()
    status = request.args.get('status', 'All')
    category = request.args.get('category', 'All')
    priority = request.args.get('priority', 'All')

    counts = get_complaint_counts()
    complaints = get_all_complaints(
        search=search if search else None,
        status=status,
        category=category,
        priority=priority
    )

    return render_template(
        'management_portal.html',
        counts=counts,
        complaints=complaints,
        search=search,
        selected_status=status,
        selected_category=category,
        selected_priority=priority
    )

@app.route('/management/update/<ticket_id>', methods=['POST'])
@management_required
def update_complaint_status_view(ticket_id):
    """Processes management triage: status changes, priority adjustments, remarks."""
    complaint = get_complaint_by_ticket_id(ticket_id)
    if not complaint:
        abort(404)

    management_id = session['user_id']
    action = request.form.get('action')
    new_status = request.form.get('status')
    new_priority = request.form.get('priority')
    remarks = request.form.get('remarks', '').strip()

    # Handle quick buttons
    if action == 'resolve':
        new_status = 'Resolved'
        if not remarks:
            remarks = 'Issue inspected and resolved by campus facilities team.'
    elif action == 'close':
        new_status = 'Closed'
        if not remarks:
            remarks = 'Grievance ticket concluded and archived.'

    # Server-side validation
    valid_statuses = ['Submitted', 'In Progress', 'Resolved', 'Closed']
    valid_priorities = ['Low', 'Medium', 'High', 'Critical']

    if new_status and new_status not in valid_statuses:
        flash('Invalid status stage supplied.', 'error')
        return redirect(url_for('complaint_detail_view', ticket_id=ticket_id))

    if new_priority and new_priority not in valid_priorities:
        flash('Invalid priority level supplied.', 'error')
        return redirect(url_for('complaint_detail_view', ticket_id=ticket_id))

    # Update in SQLite
    success = update_complaint_status_and_remarks(
        complaint_id=complaint['id'],
        management_id=management_id,
        new_status=new_status,
        remarks=remarks,
        new_priority=new_priority
    )

    if success:
        flash(f'Ticket #{ticket_id} updated successfully (Status: {new_status or complaint["status"]}, Priority: {new_priority or complaint["priority"]}).', 'success')
    else:
        flash('Failed to update ticket. Please try again.', 'error')

    # Return to referring view (management portal or complaint detail)
    referer = request.referrer
    if referer and 'management' in referer:
        return redirect(url_for('management_portal_view'))
    return redirect(url_for('complaint_detail_view', ticket_id=ticket_id))

# --- AI/ML Category Suggestion API ---

@app.route('/api/predict-category', methods=['POST'])
def api_predict_category():
    """
    API endpoint: accepts complaint description and returns AI category suggestion.
    """
    data = request.get_json(silent=True) or {}
    description = data.get('description', '')
    
    result = predict_complaint_category(description)
    return jsonify(result)

# --- Error Handlers ---

@app.errorhandler(400)
def bad_request_error(e):
    return render_template('base.html', content="<div class='p-8 text-center'><h1 class='text-2xl font-bold text-error'>400 Bad Request</h1><p class='text-sm mt-2'>The request could not be processed due to invalid parameters.</p></div>"), 400

@app.errorhandler(403)
def forbidden_error(e):
    return render_template('base.html', content="<div class='p-8 text-center'><h1 class='text-2xl font-bold text-error'>403 Forbidden</h1><p class='text-sm mt-2'>You do not have permission to view or manage this record.</p></div>"), 403

@app.errorhandler(404)
def not_found_error(e):
    return render_template('base.html', content="<div class='p-8 text-center'><h1 class='text-2xl font-bold text-on-surface'>404 Not Found</h1><p class='text-sm mt-2'>The requested grievance or page does not exist.</p></div>"), 404

@app.errorhandler(413)
def file_too_large_error(e):
    flash('Attached photo exceeds the 5MB size limit. Please upload a smaller image.', 'error')
    return redirect(request.url)

@app.errorhandler(500)
def internal_server_error(e):
    return render_template('base.html', content="<div class='p-8 text-center'><h1 class='text-2xl font-bold text-error'>500 Internal Server Error</h1><p class='text-sm mt-2'>A system error occurred. Please try again later.</p></div>"), 500

# App Runner
if __name__ == '__main__':
    init_db()
    port = int(os.environ.get('PORT', 5000))
    app.run(host='127.0.0.1', port=port, debug=True)

