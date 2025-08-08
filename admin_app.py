from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify, send_file, make_response
from flask_mail import Mail, Message
from flask_sqlalchemy import SQLAlchemy
from werkzeug.middleware.dispatcher import DispatcherMiddleware
from datetime import datetime, timedelta
import secrets
import os
from werkzeug.security import generate_password_hash, check_password_hash
import uuid
import random
import string
from dotenv import load_dotenv
import json
import io
import csv

# Load environment variables from .env file
load_dotenv()

admin_app = Flask(__name__, template_folder='admin_templates', static_folder='static')
admin_app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'admin-secret-key-change-in-production')

# Database configuration - use same database as main app
database_url = os.environ.get('DATABASE_URL', 'sqlite:///modern360.db')
# Fix for Render.com PostgreSQL URL format
if database_url and database_url.startswith('postgres://'):
    database_url = database_url.replace('postgres://', 'postgresql://', 1)
admin_app.config['SQLALCHEMY_DATABASE_URI'] = database_url
admin_app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Mail configuration
admin_app.config['MAIL_SERVER'] = os.environ.get('MAIL_SERVER', 'smtp.gmail.com')
admin_app.config['MAIL_PORT'] = int(os.environ.get('MAIL_PORT', 587))
# Use SSL for port 465, TLS for port 587
mail_port = int(os.environ.get('MAIL_PORT', 587))
if mail_port == 465:
    admin_app.config['MAIL_USE_SSL'] = True
    admin_app.config['MAIL_USE_TLS'] = False
else:
    admin_app.config['MAIL_USE_TLS'] = True
    admin_app.config['MAIL_USE_SSL'] = False
admin_app.config['MAIL_USERNAME'] = os.environ.get('MAIL_USERNAME')
admin_app.config['MAIL_PASSWORD'] = os.environ.get('MAIL_PASSWORD')
admin_app.config['MAIL_DEFAULT_SENDER'] = os.environ.get('MAIL_DEFAULT_SENDER')

# Initialize extensions
db = SQLAlchemy(admin_app)
mail = Mail(admin_app)

# Add custom Jinja2 functions
@admin_app.template_global()
def moment():
    """Return current datetime for template comparisons"""
    return datetime.utcnow()

@admin_app.template_filter('datetime')
def datetime_filter(dt, format='%Y-%m-%d %H:%M'):
    """Format datetime for templates"""
    if dt is None:
        return ""
    return dt.strftime(format)

# Import models from main app (we'll use the same database)
class Company(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(150), unique=True, nullable=False)
    description = db.Column(db.Text)
    industry = db.Column(db.String(100))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    is_active = db.Column(db.Boolean, default=True)
    
    # Relationships
    users = db.relationship('User', backref='company_ref', lazy=True)
    assessments = db.relationship('Assessment', backref='company_ref', lazy=True)

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False)
    name = db.Column(db.String(100), nullable=False)
    company = db.Column(db.String(150), nullable=True)  # Legacy field
    company_id = db.Column(db.Integer, db.ForeignKey('company.id'), nullable=True)  # New company reference
    role = db.Column(db.String(20), default='user')  # admin, manager, user, assessee, assessor
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    is_active = db.Column(db.Boolean, default=True)
    last_login = db.Column(db.DateTime)
    
    # Relationships
    created_assessments = db.relationship('Assessment', backref='creator', lazy=True)
    invitations_sent = db.relationship('Invitation', backref='sender', lazy=True)
    responses = db.relationship('AssessmentResponse', backref='user', lazy=True)
    assessee_participations = db.relationship('AssessmentParticipant', 
                                            foreign_keys='AssessmentParticipant.assessee_id', 
                                            backref='assessee', lazy=True)
    assessor_participations = db.relationship('AssessmentParticipant', 
                                            foreign_keys='AssessmentParticipant.assessor_id', 
                                            backref='assessor', lazy=True)

class Assessment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text)
    creator_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    company_id = db.Column(db.Integer, db.ForeignKey('company.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    deadline = db.Column(db.DateTime)
    is_active = db.Column(db.Boolean, default=True)
    is_self_assessment = db.Column(db.Boolean, default=False)
    
    # Relationships
    invitations = db.relationship('Invitation', backref='assessment', lazy=True)
    responses = db.relationship('AssessmentResponse', backref='assessment', lazy=True)
    questions = db.relationship('Question', backref='assessment', lazy=True)
    participants = db.relationship('AssessmentParticipant', backref='assessment', lazy=True)

class AssessmentParticipant(db.Model):
    """Link between Assessment, Assessee, and Assessors"""
    id = db.Column(db.Integer, primary_key=True)
    assessment_id = db.Column(db.Integer, db.ForeignKey('assessment.id'), nullable=False)
    assessee_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    assessor_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)  # Null for self-assessment
    assessor_relationship = db.Column(db.String(50), nullable=True)  # Manager, Peer, Direct Report
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Status tracking
    self_assessment_completed = db.Column(db.Boolean, default=False)
    assessor_assessment_completed = db.Column(db.Boolean, default=False)
    self_assessment_date = db.Column(db.DateTime)
    assessor_assessment_date = db.Column(db.DateTime)

class Question(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    assessment_id = db.Column(db.Integer, db.ForeignKey('assessment.id'), nullable=False)
    question_text = db.Column(db.Text, nullable=False)
    question_group = db.Column(db.String(100), nullable=True)  # Question category/group
    question_type = db.Column(db.String(50), nullable=False)  # rating, text, multiple_choice
    language = db.Column(db.String(10), default='en')  # Language code (en, bs, etc.)
    options = db.Column(db.Text)  # JSON string for multiple choice options
    order = db.Column(db.Integer, default=0)

class Invitation(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    assessment_id = db.Column(db.Integer, db.ForeignKey('assessment.id'), nullable=False)
    sender_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    email = db.Column(db.String(120), nullable=False)
    token = db.Column(db.String(100), unique=True, nullable=False)
    sent_at = db.Column(db.DateTime, default=datetime.utcnow)
    responded_at = db.Column(db.DateTime)
    is_completed = db.Column(db.Boolean, default=False)

class AssessmentResponse(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    assessment_id = db.Column(db.Integer, db.ForeignKey('assessment.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    invitation_id = db.Column(db.Integer, db.ForeignKey('invitation.id'))
    participant_id = db.Column(db.Integer, db.ForeignKey('assessment_participant.id'), nullable=True)
    responses = db.Column(db.Text)  # JSON string of responses
    response_type = db.Column(db.String(20), default='assessor')  # 'self' or 'assessor'
    submitted_at = db.Column(db.DateTime, default=datetime.utcnow)

# Admin credentials
ADMIN_USERNAME = "admin"
ADMIN_PASSWORD = "admin123"

# Admin authentication decorator
def admin_required(f):
    def decorated_function(*args, **kwargs):
        if 'admin_logged_in' not in session:
            return redirect(url_for('admin_login'))
        return f(*args, **kwargs)
    decorated_function.__name__ = f.__name__
    return decorated_function

# Admin Routes
@admin_app.route('/')
def admin_index():
    if 'admin_logged_in' in session:
        return redirect(url_for('admin_dashboard'))
    return redirect(url_for('admin_login'))

@admin_app.route('/login', methods=['GET', 'POST'])
def admin_login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        if username == ADMIN_USERNAME and password == ADMIN_PASSWORD:
            session['admin_logged_in'] = True
            session['admin_username'] = username
            flash('Successfully logged in as admin!', 'success')
            return redirect(url_for('admin_dashboard'))
        else:
            flash('Invalid admin credentials!', 'error')
    
    return render_template('admin_login.html')

@admin_app.route('/logout')
def admin_logout():
    session.pop('admin_logged_in', None)
    session.pop('admin_username', None)
    flash('You have been logged out.', 'info')
    return redirect(url_for('admin_login'))

@admin_app.route('/dashboard')
@admin_required
def admin_dashboard():
    # Get statistics
    total_companies = Company.query.count()
    total_users = User.query.count()
    total_assessments = Assessment.query.count()
    active_assessments = Assessment.query.filter_by(is_active=True).count()
    total_responses = AssessmentResponse.query.count()
    pending_invitations = Invitation.query.filter_by(is_completed=False).count()
    
    # Recent activity
    recent_companies = Company.query.order_by(Company.created_at.desc()).limit(5).all()
    recent_users = User.query.order_by(User.created_at.desc()).limit(5).all()
    recent_assessments = Assessment.query.order_by(Assessment.created_at.desc()).limit(5).all()
    recent_responses = AssessmentResponse.query.order_by(AssessmentResponse.submitted_at.desc()).limit(5).all()
    
    return render_template('admin_dashboard.html',
                         total_companies=total_companies,
                         total_users=total_users,
                         total_assessments=total_assessments,
                         active_assessments=active_assessments,
                         total_responses=total_responses,
                         pending_invitations=pending_invitations,
                         recent_companies=recent_companies,
                         recent_users=recent_users,
                         recent_assessments=recent_assessments,
                         recent_responses=recent_responses)

@admin_app.route('/companies')
@admin_required
def admin_companies():
    page = request.args.get('page', 1, type=int)
    companies = Company.query.order_by(Company.created_at.desc()).paginate(
        page=page, per_page=20, error_out=False)
    return render_template('admin_companies.html', companies=companies)

@admin_app.route('/companies/create', methods=['GET', 'POST'])
@admin_required
def admin_create_company():
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        description = request.form.get('description', '').strip()
        industry = request.form.get('industry', '').strip()
        
        if not name:
            flash('Company name is required!', 'error')
            return render_template('admin_create_company.html')
        
        # Check if company already exists
        existing_company = Company.query.filter_by(name=name).first()
        if existing_company:
            flash('Company with this name already exists!', 'error')
            return render_template('admin_create_company.html')
        
        # Create new company
        company = Company(name=name, description=description, industry=industry)
        db.session.add(company)
        db.session.commit()
        
        flash(f'Company "{name}" created successfully!', 'success')
        return redirect(url_for('admin_companies'))
    
    return render_template('admin_create_company.html')

@admin_app.route('/companies/<int:company_id>/edit', methods=['GET', 'POST'])
@admin_required
def admin_edit_company(company_id):
    company = Company.query.get_or_404(company_id)
    
    if request.method == 'POST':
        company.name = request.form.get('name', '').strip()
        company.description = request.form.get('description', '').strip()
        company.industry = request.form.get('industry', '').strip()
        company.is_active = 'is_active' in request.form
        
        db.session.commit()
        flash(f'Company "{company.name}" updated successfully!', 'success')
        return redirect(url_for('admin_companies'))
    
    return render_template('admin_edit_company.html', company=company)

@admin_app.route('/companies/<int:company_id>/delete', methods=['POST'])
@admin_required
def admin_delete_company(company_id):
    company = Company.query.get_or_404(company_id)
    
    # Check if company has users or assessments
    if company.users or company.assessments:
        flash('Cannot delete company with existing users or assessments!', 'error')
        return redirect(url_for('admin_companies'))
    
    name = company.name
    db.session.delete(company)
    db.session.commit()
    
    flash(f'Company "{name}" deleted successfully!', 'success')
    return redirect(url_for('admin_companies'))

@admin_app.route('/users')
@admin_required
def admin_users():
    page = request.args.get('page', 1, type=int)
    company_id = request.args.get('company_id', type=int)
    
    query = User.query
    if company_id:
        query = query.filter_by(company_id=company_id)
    
    users = query.order_by(User.created_at.desc()).paginate(
        page=page, per_page=20, error_out=False)
    
    companies = Company.query.filter_by(is_active=True).all()
    selected_company = Company.query.get(company_id) if company_id else None
    
    return render_template('admin_users.html', users=users, companies=companies, selected_company=selected_company)

@admin_app.route('/users/create', methods=['GET', 'POST'])
@admin_required
def admin_create_user():
    if request.method == 'POST':
        email = request.form.get('email', '').strip().lower()
        name = request.form.get('name', '').strip()
        company_id = request.form.get('company_id', type=int)
        role = request.form.get('role', 'user')
        
        if not email or not name or not company_id:
            flash('Email, name, and company are required!', 'error')
            companies = Company.query.filter_by(is_active=True).all()
            return render_template('admin_create_user.html', companies=companies)
        
        # Check if user already exists
        existing_user = User.query.filter_by(email=email).first()
        if existing_user:
            flash('User with this email already exists!', 'error')
            companies = Company.query.filter_by(is_active=True).all()
            return render_template('admin_create_user.html', companies=companies)
        
        # Get company name for legacy field
        company = Company.query.get(company_id)
        
        # Create new user
        user = User(
            email=email, 
            name=name, 
            company=company.name if company else None,  # Legacy field
            company_id=company_id, 
            role=role
        )
        db.session.add(user)
        db.session.commit()
        
        flash(f'User {name} created successfully!', 'success')
        return redirect(url_for('admin_users'))
    
    companies = Company.query.filter_by(is_active=True).all()
    return render_template('admin_create_user.html', companies=companies)

@admin_app.route('/users/<int:user_id>/edit', methods=['GET', 'POST'])
@admin_required
def admin_edit_user(user_id):
    user = User.query.get_or_404(user_id)
    
    if request.method == 'POST':
        user.name = request.form.get('name', '').strip()
        company_id = request.form.get('company_id', type=int)
        user.role = request.form.get('role', 'user')
        user.is_active = 'is_active' in request.form
        
        # Update company references
        if company_id:
            company = Company.query.get(company_id)
            user.company_id = company_id
            user.company = company.name if company else None
        else:
            # No company selected - clear company references
            user.company_id = None
            user.company = None
        
        db.session.commit()
        flash(f'User {user.name} updated successfully!', 'success')
        return redirect(url_for('admin_users'))
    
    companies = Company.query.filter_by(is_active=True).all()
    return render_template('admin_edit_user.html', user=user, companies=companies)

@admin_app.route('/users/<int:user_id>/delete', methods=['POST'])
@admin_required
def admin_delete_user(user_id):
    user = User.query.get_or_404(user_id)
    
    # Check if user has active assessments as creator
    active_created_assessments = Assessment.query.filter_by(creator_id=user_id, is_active=True).count()
    
    # Check if user is participating in active assessments as assessee
    active_assessee_participations = db.session.query(AssessmentParticipant).join(Assessment).filter(
        AssessmentParticipant.assessee_id == user_id,
        Assessment.is_active == True
    ).count()
    
    # Check if user is participating in active assessments as assessor
    active_assessor_participations = db.session.query(AssessmentParticipant).join(Assessment).filter(
        AssessmentParticipant.assessor_id == user_id,
        Assessment.is_active == True
    ).count()
    
    # Check if user has pending invitations for active assessments
    active_invitations = db.session.query(Invitation).join(Assessment).filter(
        Invitation.email == user.email,
        Invitation.is_completed == False,
        Assessment.is_active == True
    ).count()
    
    # If user has any active assessment involvement, prevent deletion
    if active_created_assessments > 0 or active_assessee_participations > 0 or active_assessor_participations > 0 or active_invitations > 0:
        error_details = []
        if active_created_assessments > 0:
            error_details.append(f"{active_created_assessments} active assessment(s) as creator")
        if active_assessee_participations > 0:
            error_details.append(f"{active_assessee_participations} active assessment(s) as assessee")
        if active_assessor_participations > 0:
            error_details.append(f"{active_assessor_participations} active assessment(s) as assessor")
        if active_invitations > 0:
            error_details.append(f"{active_invitations} pending invitation(s)")
        
        flash(f'Cannot delete user {user.name}! User has {", ".join(error_details)}. Please deactivate or complete these assessments first.', 'error')
        return redirect(url_for('admin_users'))
    
    # If no active assessments, proceed with deletion
    # Delete related records first
    AssessmentResponse.query.filter_by(user_id=user_id).delete()
    Invitation.query.filter_by(sender_id=user_id).delete()
    
    # Delete user's inactive assessments and their related data
    for assessment in user.created_assessments:
        if not assessment.is_active:  # Only delete inactive assessments
            Question.query.filter_by(assessment_id=assessment.id).delete()
            Invitation.query.filter_by(assessment_id=assessment.id).delete()
            AssessmentResponse.query.filter_by(assessment_id=assessment.id).delete()
            AssessmentParticipant.query.filter_by(assessment_id=assessment.id).delete()
            db.session.delete(assessment)
    
    # Delete user's participation records in inactive assessments only
    # First get the participation records, then delete them individually
    participation_records = db.session.query(AssessmentParticipant).join(Assessment).filter(
        db.or_(
            AssessmentParticipant.assessee_id == user_id,
            AssessmentParticipant.assessor_id == user_id
        ),
        Assessment.is_active == False
    ).all()
    
    # Delete each participation record individually
    for record in participation_records:
        db.session.delete(record)
    
    db.session.delete(user)
    db.session.commit()
    
    flash(f'User {user.name} deleted successfully!', 'success')
    return redirect(url_for('admin_users'))

@admin_app.route('/assessments')
@admin_required
def admin_assessments():
    page = request.args.get('page', 1, type=int)
    company_id = request.args.get('company_id', type=int)
    
    query = Assessment.query
    if company_id:
        query = query.filter_by(company_id=company_id)
    
    assessments = query.order_by(Assessment.created_at.desc()).paginate(
        page=page, per_page=20, error_out=False)
    
    companies = Company.query.filter_by(is_active=True).all()
    selected_company = Company.query.get(company_id) if company_id else None
    
    return render_template('admin_assessments.html', assessments=assessments, 
                         companies=companies, selected_company=selected_company)

@admin_app.route('/api/company/<int:company_id>/users')
@admin_required
def api_company_users(company_id):
    """API endpoint to get users for a specific company"""
    users = User.query.filter_by(company_id=company_id, is_active=True).all()
    return jsonify({
        'users': [
            {
                'id': user.id,
                'name': user.name,
                'email': user.email,
                'role': user.role,
                'is_active': user.is_active
            }
            for user in users
        ]
    })

@admin_app.route('/api/companies', methods=['POST'])
@admin_required
def api_create_company():
    """API endpoint to create a new company"""
    data = request.get_json()
    name = data.get('name', '').strip()
    description = data.get('description', '').strip()
    industry = data.get('industry', '').strip()
    
    if not name:
        return jsonify({'success': False, 'message': 'Company name is required!'})
    
    if not industry:
        return jsonify({'success': False, 'message': 'Industry is required!'})
    
    # Check if company already exists
    existing_company = Company.query.filter_by(name=name).first()
    if existing_company:
        return jsonify({'success': False, 'message': 'Company with this name already exists!'})
    
    # Create new company
    company = Company(name=name, description=description, industry=industry)
    db.session.add(company)
    db.session.commit()
    
    return jsonify({
        'success': True,
        'company': {
            'id': company.id,
            'name': company.name,
            'description': company.description,
            'industry': company.industry
        }
    })

@admin_app.route('/api/users', methods=['POST'])
@admin_required
def api_create_user():
    """API endpoint to create a new user"""
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({'success': False, 'message': 'No JSON data received!'})
        
        email = data.get('email', '').strip().lower()
        name = data.get('name', '').strip()
        company_id = data.get('company_id')
        role = data.get('role', 'user')
        
        print(f"DEBUG: Received data - name: {name}, email: {email}, company_id: {company_id}, role: {role}")
        
        if not email or not name or not company_id:
            return jsonify({'success': False, 'message': 'Email, name, and company are required!'})
        
        # Convert company_id to int
        try:
            company_id = int(company_id)
        except (ValueError, TypeError):
            return jsonify({'success': False, 'message': 'Invalid company ID!'})
        
        # Check if user already exists
        existing_user = User.query.filter_by(email=email).first()
        if existing_user:
            return jsonify({'success': False, 'message': 'User with this email already exists!'})
        
        # Get company name for legacy field
        company = Company.query.get(company_id)
        if not company:
            return jsonify({'success': False, 'message': 'Company not found!'})
        
        # Create new user
        user = User(
            email=email, 
            name=name, 
            company=company.name,  # Legacy field
            company_id=company_id, 
            role=role
        )
        db.session.add(user)
        db.session.commit()
        
        print(f"DEBUG: Successfully created user - ID: {user.id}, Name: {user.name}, Email: {user.email}")
        
        return jsonify({
            'success': True,
            'user': {
                'id': user.id,
                'name': user.name,
                'email': user.email,
                'role': user.role
            }
        })
        
    except Exception as e:
        print(f"ERROR: Exception in api_create_user: {e}")
        db.session.rollback()
        return jsonify({'success': False, 'message': f'Server error: {str(e)}'})

@admin_app.route('/assessments/create', methods=['GET', 'POST'])
@admin_required
def admin_create_assessment():
    if request.method == 'POST':
        title = request.form.get('title', '').strip()
        description = request.form.get('description', '').strip()
        company_id = request.form.get('company_id', type=int)
        deadline_str = request.form.get('deadline')
        creator_id = request.form.get('creator_id', type=int)
        language = 'bs'  # Default to Bosnian
        use_template = 'use_template' in request.form
        send_invitations = 'send_invitations' in request.form
        allow_self_registration = 'allow_self_registration' in request.form
        
        # Get selected participants
        assessee_ids_str = request.form.get('assessees', '')
        assessor_data_str = request.form.get('assessors', '')
        
        assessee_ids = [int(id.strip()) for id in assessee_ids_str.split(',') if id.strip()]
        
        # Parse assessor data (now includes relationships)
        assessor_data = []
        if assessor_data_str:
            try:
                assessor_data = json.loads(assessor_data_str)
            except json.JSONDecodeError:
                # Fallback to old format (just IDs)
                assessor_ids = [int(id.strip()) for id in assessor_data_str.split(',') if id.strip()]
                assessor_data = [{'id': id, 'relationship': ''} for id in assessor_ids]
        
        if not title or not company_id:
            flash('Assessment title and company are required!', 'error')
            companies = Company.query.filter_by(is_active=True).all()
            users = User.query.filter_by(is_active=True).all()
            return render_template('admin_create_assessment.html', companies=companies, users=users)
        
        if not assessee_ids:
            flash('One assessee must be selected!', 'error')
            companies = Company.query.filter_by(is_active=True).all()
            users = User.query.filter_by(is_active=True).all()
            return render_template('admin_create_assessment.html', companies=companies, users=users)
        
        if len(assessee_ids) > 1:
            flash('Only one assessee can be selected per assessment!', 'error')
            companies = Company.query.filter_by(is_active=True).all()
            users = User.query.filter_by(is_active=True).all()
            return render_template('admin_create_assessment.html', companies=companies, users=users)
        
        if not assessor_data:
            flash('At least one assessor must be selected!', 'error')
            companies = Company.query.filter_by(is_active=True).all()
            users = User.query.filter_by(is_active=True).all()
            return render_template('admin_create_assessment.html', companies=companies, users=users)
        
        deadline = None
        if deadline_str:
            try:
                deadline = datetime.strptime(deadline_str, '%Y-%m-%dT%H:%M')
            except ValueError:
                flash('Invalid deadline format!', 'error')
                companies = Company.query.filter_by(is_active=True).all()
                users = User.query.filter_by(is_active=True).all()
                return render_template('admin_create_assessment.html', companies=companies, users=users)
        
        # Create assessment
        assessment = Assessment(
            title=title,
            description=description,
            company_id=company_id,
            deadline=deadline,
            creator_id=creator_id or 1  # Default to first user if not specified
        )
        db.session.add(assessment)
        db.session.flush()  # Get the ID
        
        # Add questions
        questions = []
        question_index = 0
        
        if use_template:
            # Copy predefined questions from template (assessment_id = 0)
            template_questions = Question.query.filter_by(assessment_id=0, language=language).order_by(Question.order).all()
            for template_q in template_questions:
                question = Question(
                    assessment_id=assessment.id,
                    question_text=template_q.question_text,
                    question_group=template_q.question_group,
                    question_type=template_q.question_type,
                    language=template_q.language,
                    order=template_q.order
                )
                questions.append(question)
                db.session.add(question)
        else:
            # Add custom questions from form
            while f'question_{question_index}_text' in request.form:
                question_text = request.form.get(f'question_{question_index}_text', '').strip()
                question_type = request.form.get(f'question_{question_index}_type', 'rating')
                question_group = request.form.get(f'question_{question_index}_group', '').strip()
                
                if question_text:
                    question = Question(
                        assessment_id=assessment.id,
                        question_text=question_text,
                        question_group=question_group,
                        question_type=question_type,
                        language=language,
                        order=question_index
                    )
                    questions.append(question)
                    db.session.add(question)
                
                question_index += 1
        
        if not questions:
            flash('At least one question is required!', 'error')
            db.session.rollback()
            companies = Company.query.filter_by(is_active=True).all()
            users = User.query.filter_by(is_active=True).all()
            return render_template('admin_create_assessment.html', companies=companies, users=users)
        
        # Create assessment participants
        participants_created = 0
        
        for assessee_id in assessee_ids:
            assessee_id = int(assessee_id)
            
            # Add self-assessment participant (assessee assessing themselves)
            self_participant = AssessmentParticipant(
                assessment_id=assessment.id,
                assessee_id=assessee_id,
                assessor_id=None  # Self-assessment
            )
            db.session.add(self_participant)
            participants_created += 1
            
            # Add assessor participants (each assessor assesses this assessee)
            for assessor_info in assessor_data:
                assessor_id = int(assessor_info['id'])
                relationship = assessor_info.get('relationship', '')
                if assessor_id != assessee_id:  # Don't add assessee as their own assessor
                    assessor_participant = AssessmentParticipant(
                        assessment_id=assessment.id,
                        assessee_id=assessee_id,
                        assessor_id=assessor_id,
                        assessor_relationship=relationship
                    )
                    db.session.add(assessor_participant)
                    participants_created += 1
        
        db.session.commit()
        
        # Send invitations if requested
        sent_count = 0
        if send_invitations:
            participants = AssessmentParticipant.query.filter_by(assessment_id=assessment.id).all()
            
            for participant in participants:
                # Send invitation to assessee for self-assessment
                if not participant.assessor_id:  # Self-assessment
                    token = secrets.token_urlsafe(32)
                    invitation = Invitation(
                        assessment_id=assessment.id,
                        sender_id=1,  # Admin sender
                        email=participant.assessee.email,
                        token=token
                    )
                    db.session.add(invitation)
                    
                    try:
                        send_self_assessment_invitation(participant.assessee.email, assessment, token)
                        sent_count += 1
                    except Exception as e:
                        print(f"Error sending self-assessment invitation: {e}")
                
                # Send invitation to assessor
                else:
                    token = secrets.token_urlsafe(32)
                    invitation = Invitation(
                        assessment_id=assessment.id,
                        sender_id=1,  # Admin sender
                        email=participant.assessor.email,
                        token=token
                    )
                    db.session.add(invitation)
                    
                    try:
                        send_assessor_invitation(participant.assessor.email, assessment, 
                                               participant.assessee.name, token)
                        sent_count += 1
                    except Exception as e:
                        print(f"Error sending assessor invitation: {e}")
            
            db.session.commit()
        
        if send_invitations and sent_count > 0:
            flash(f'Assessment "{title}" created successfully with {len(questions)} questions and {participants_created} participants! {sent_count} invitations sent.', 'success')
        else:
            flash(f'Assessment "{title}" created successfully with {len(questions)} questions and {participants_created} participants! Invitations can be sent later.', 'success')
        return redirect(url_for('admin_assessments'))
    
    companies = Company.query.filter_by(is_active=True).all()
    users = User.query.filter_by(is_active=True).all()
    
    # Get template question groups for preview
    bosnian_groups = db.session.query(Question.question_group).filter_by(assessment_id=0, language='bs').distinct().all()
    english_groups = db.session.query(Question.question_group).filter_by(assessment_id=0, language='en').distinct().all()
    
    return render_template('admin_create_assessment.html', 
                         companies=companies, users=users,
                         bosnian_groups=[g[0] for g in bosnian_groups],
                         english_groups=[g[0] for g in english_groups])

@admin_app.route('/assessments/<int:assessment_id>/edit', methods=['GET', 'POST'])
@admin_required
def admin_edit_assessment(assessment_id):
    assessment = Assessment.query.get_or_404(assessment_id)
    
    if request.method == 'POST':
        assessment.title = request.form.get('title', '').strip()
        assessment.description = request.form.get('description', '').strip()
        company_id = request.form.get('company_id', type=int)
        deadline_str = request.form.get('deadline')
        
        if not assessment.title or not company_id:
            flash('Assessment title and company are required!', 'error')
            companies = Company.query.filter_by(is_active=True).all()
            users = User.query.filter_by(is_active=True).all()
            return render_template('admin_edit_assessment.html', assessment=assessment, companies=companies, users=users)
        
        assessment.company_id = company_id
        
        # Handle deadline
        if deadline_str:
            try:
                assessment.deadline = datetime.strptime(deadline_str, '%Y-%m-%dT%H:%M')
            except ValueError:
                flash('Invalid deadline format!', 'error')
                companies = Company.query.filter_by(is_active=True).all()
                users = User.query.filter_by(is_active=True).all()
                return render_template('admin_edit_assessment.html', assessment=assessment, companies=companies, users=users)
        else:
            assessment.deadline = None
        
        # Handle active status
        assessment.is_active = 'is_active' in request.form
        
        db.session.commit()
        flash(f'Assessment "{assessment.title}" updated successfully!', 'success')
        return redirect(url_for('admin_assessments'))
    
    companies = Company.query.filter_by(is_active=True).all()
    users = User.query.filter_by(is_active=True).all()
    
    return render_template('admin_edit_assessment.html', assessment=assessment, companies=companies, users=users)

@admin_app.route('/questions/templates')
@admin_required
def admin_question_templates():
    """View predefined question templates"""
    bosnian_questions = Question.query.filter_by(assessment_id=0, language='bs').order_by(Question.order).all()
    english_questions = Question.query.filter_by(assessment_id=0, language='en').order_by(Question.order).all()
    
    # Group questions by category, but maintain order within each group
    bosnian_groups = {}
    for q in bosnian_questions:
        if q.question_group not in bosnian_groups:
            bosnian_groups[q.question_group] = []
        bosnian_groups[q.question_group].append(q)
    
    english_groups = {}
    for q in english_questions:
        if q.question_group not in english_groups:
            english_groups[q.question_group] = []
        english_groups[q.question_group].append(q)
    
    return render_template('admin_question_templates.html', 
                         bosnian_groups=bosnian_groups, 
                         english_groups=english_groups)

@admin_app.route('/assessments/<int:assessment_id>/participants')
@admin_required
def admin_assessment_participants(assessment_id):
    assessment = Assessment.query.get_or_404(assessment_id)
    participants = AssessmentParticipant.query.filter_by(assessment_id=assessment_id).all()
    
    # Get users from the same company as the assessment
    company_users = User.query.filter_by(company_id=assessment.company_id, is_active=True).all()
    assessees = [u for u in company_users if u.role in ['assessee', 'user']]
    assessors = [u for u in company_users if u.role in ['assessor', 'manager', 'user']]
    
    return render_template('admin_assessment_participants.html', 
                         assessment=assessment, participants=participants,
                         assessees=assessees, assessors=assessors)

@admin_app.route('/assessments/<int:assessment_id>/add-participant', methods=['POST'])
@admin_required
def admin_add_participant(assessment_id):
    assessment = Assessment.query.get_or_404(assessment_id)
    assessee_id = request.form.get('assessee_id', type=int)
    assessor_ids = request.form.getlist('assessor_ids')  # Multiple assessors
    
    if not assessee_id:
        flash('Assessee is required!', 'error')
        return redirect(url_for('admin_assessment_participants', assessment_id=assessment_id))
    
    # Note: Removed check for existing assessee to allow duplicates
    # This allows the same person to be added multiple times as an assessee
    
    # Add self-assessment participant (assessee assessing themselves)
    self_participant = AssessmentParticipant(
        assessment_id=assessment_id,
        assessee_id=assessee_id,
        assessor_id=None  # Self-assessment
    )
    db.session.add(self_participant)
    
    # Add assessor participants
    for assessor_id in assessor_ids:
        if assessor_id and int(assessor_id) != assessee_id:  # Don't add assessee as their own assessor
            assessor_participant = AssessmentParticipant(
                assessment_id=assessment_id,
                assessee_id=assessee_id,
                assessor_id=int(assessor_id)
            )
            db.session.add(assessor_participant)
    
    db.session.commit()
    
    # Send invitations
    assessee = User.query.get(assessee_id)
    flash(f'Participants added successfully for {assessee.name}!', 'success')
    
    return redirect(url_for('admin_assessment_participants', assessment_id=assessment_id))

@admin_app.route('/assessments/<int:assessment_id>/send-invitations', methods=['POST'])
@admin_required
def admin_send_assessment_invitations(assessment_id):
    assessment = Assessment.query.get_or_404(assessment_id)
    participants = AssessmentParticipant.query.filter_by(assessment_id=assessment_id).all()
    
    sent_count = 0
    
    for participant in participants:
        # Send invitation to assessee for self-assessment
        if not participant.assessor_id:  # Self-assessment
            token = secrets.token_urlsafe(32)
            invitation = Invitation(
                assessment_id=assessment_id,
                sender_id=1,  # Admin sender
                email=participant.assessee.email,
                token=token
            )
            db.session.add(invitation)
            
            try:
                send_self_assessment_invitation(participant.assessee.email, assessment, token, participant.assessee.name)
                sent_count += 1
            except Exception as e:
                print(f"Error sending self-assessment invitation: {e}")
        
        # Send invitation to assessor
        else:
            token = secrets.token_urlsafe(32)
            invitation = Invitation(
                assessment_id=assessment_id,
                sender_id=1,  # Admin sender
                email=participant.assessor.email,
                token=token
            )
            db.session.add(invitation)
            
            try:
                send_assessor_invitation(participant.assessor.email, assessment, 
                                       participant.assessee.name, token, participant.assessor_relationship)
                sent_count += 1
            except Exception as e:
                print(f"Error sending assessor invitation: {e}")
    
    db.session.commit()
    flash(f'Sent {sent_count} invitations successfully!', 'success')
    return redirect(url_for('admin_assessment_participants', assessment_id=assessment_id))

@admin_app.route('/assessments/<int:assessment_id>/delete', methods=['POST'])
@admin_required
def admin_delete_assessment(assessment_id):
    assessment = Assessment.query.get_or_404(assessment_id)
    title = assessment.title
    
    try:
        # Delete related records in proper order (to handle foreign key constraints)
        # First delete responses that reference participants
        AssessmentResponse.query.filter_by(assessment_id=assessment_id).delete()
        
        # Then delete participants (which might be referenced by responses)
        AssessmentParticipant.query.filter_by(assessment_id=assessment_id).delete()
        
        # Delete other related records
        Question.query.filter_by(assessment_id=assessment_id).delete()
        Invitation.query.filter_by(assessment_id=assessment_id).delete()
        
        # Finally delete the assessment itself
        db.session.delete(assessment)
        db.session.commit()
        
        flash(f'Assessment "{title}" deleted successfully!', 'success')
        
    except Exception as e:
        db.session.rollback()
        print(f"Error deleting assessment: {e}")
        flash(f'Error deleting assessment: {str(e)}', 'error')
    
    return redirect(url_for('admin_assessments'))

# Export Assessment to Excel
@admin_app.route('/assessments/<int:assessment_id>/export/excel')
@admin_required
def admin_export_assessment_excel(assessment_id):
    assessment = Assessment.query.get_or_404(assessment_id)
    
    # Check if all participants have responded
    total_participants = len(assessment.invitations)
    completed_responses = len(assessment.responses)
    
    if total_participants == 0 or completed_responses != total_participants:
        flash('Export is only available when all participants have completed the assessment.', 'warning')
        return redirect(url_for('admin_assessments'))
    
    # Create CSV content
    output = io.StringIO()
    writer = csv.writer(output)
    
    # Get company information
    company = assessment.company_ref
    
    # Get all assessment questions sorted by order
    questions = sorted(assessment.questions, key=lambda q: q.order)
    
    # Create header row with basic info + questions 1-39
    header = [
        'Assessment ID',
        'Company ID', 
        'Company Name',
        'Industry',
        'Participant ID',
        'Assessee Name',
        'Participant Name',
        'Email',
        'Participant Role',
    ]
    
    # Add question columns (1-39 based on order)
    for i in range(1, 40):  # Questions 1-39
        header.append(str(i))
    
    writer.writerow(header)
    
    # Write data for each response
    for response in assessment.responses:
        try:
            response_data = json.loads(response.responses) if response.responses else {}
            
            # Get participant information
            participant = AssessmentParticipant.query.get(response.participant_id) if response.participant_id else None
            
            # Initialize assessee name (this will be the same for all participants in this assessment)
            assessee_name = ""
            
            if participant:
                # Get the assessee name (this is always available from the participant record)
                assessee_name = participant.assessee.name if participant.assessee else ""
                
                if participant.assessor_id:  # Assessor response
                    participant_id = participant.assessor_id
                    participant_name = participant.assessor.name
                    participant_email = participant.assessor.email
                    # Ensure we always have a meaningful role
                    if participant.assessor_relationship and participant.assessor_relationship.strip():
                        participant_role = participant.assessor_relationship.strip()
                    else:
                        participant_role = "Assessor"
                else:  # Self-assessment response
                    participant_id = participant.assessee_id
                    participant_name = participant.assessee.name
                    participant_email = participant.assessee.email
                    participant_role = "Self-Assessment"
            else:
                # Fallback to user if participant not found
                participant_id = response.user_id if response.user else None
                participant_name = response.user.name if response.user else "Anonymous"
                participant_email = response.user.email if response.user else "N/A"
                # Ensure we always have a meaningful role, never null
                if response.user and response.user.role and response.user.role.strip():
                    participant_role = response.user.role.strip()
                else:
                    participant_role = "User"
            
            # Create row with basic participant info
            row = [
                assessment.id,
                company.id if company else "",
                company.name if company else "",
                company.industry if company else "",
                participant_id or "",
                assessee_name,
                participant_name,
                participant_email,
                participant_role,
            ]
            
            # Add responses for questions 1-39
            for i in range(1, 40):
                # Find question with this order (now questions have order 1-39, not 0-38)
                question = next((q for q in questions if q.order == i), None)
                if question:
                    question_key = f"question_{question.id}"
                    raw_answer = response_data.get(question_key, "")
                    
                    # Clean up the answer
                    if raw_answer and str(raw_answer).strip():
                        answer = str(raw_answer).strip()
                    else:
                        answer = ""
                    row.append(answer)
                else:
                    row.append("")  # No question for this position
            
            writer.writerow(row)
            
        except Exception as e:
            print(f"Error processing response {response.id}: {e}")
            continue
    
    # Get assessee names for filename
    assessees = []
    for response in assessment.responses:
        participant = AssessmentParticipant.query.get(response.participant_id) if response.participant_id else None
        if participant and not participant.assessor_id:  # Self-assessment response (assessee)
            assessee_name = participant.assessee.name.replace(" ", "_")
            if assessee_name not in assessees:
                assessees.append(assessee_name)
    
    # Create filename with assessment and assessee names
    assessee_part = "_".join(assessees) if assessees else "NoAssessee"
    safe_title = assessment.title.replace(" ", "_").replace("/", "_").replace("\\", "_")
    filename = f"assessment_{assessment_id}_{safe_title}_{assessee_part}_export.csv"
    
    # Create response
    output.seek(0)
    response = make_response(output.getvalue())
    response.headers['Content-Type'] = 'text/csv'
    response.headers['Content-Disposition'] = f'attachment; filename={filename}'
    
    return response

# Export Assessment Detailed Report
@admin_app.route('/assessments/<int:assessment_id>/export/detailed')
@admin_required
def admin_export_assessment_detailed(assessment_id):
    assessment = Assessment.query.get_or_404(assessment_id)
    
    # Check if all participants have responded
    total_participants = len(assessment.invitations)
    completed_responses = len(assessment.responses)
    
    if total_participants == 0 or completed_responses != total_participants:
        flash('Export is only available when all participants have completed the assessment.', 'warning')
        return redirect(url_for('admin_assessments'))
    
    # Create detailed report content
    output = io.StringIO()
    
    # Write header information
    output.write(f"ASSESSMENT DETAILED REPORT\n")
    output.write(f"=" * 50 + "\n\n")
    output.write(f"Assessment ID: {assessment.id}\n")
    output.write(f"Title: {assessment.title}\n")
    output.write(f"Description: {assessment.description or 'No description'}\n")
    output.write(f"Creator: {assessment.creator.name}\n")
    output.write(f"Created: {assessment.created_at.strftime('%Y-%m-%d %H:%M:%S')}\n")
    output.write(f"Type: {'Self-Assessment' if assessment.is_self_assessment else '360 Assessment'}\n")
    output.write(f"Status: {'Active' if assessment.is_active else 'Inactive'}\n")
    output.write(f"Total Participants: {total_participants}\n")
    output.write(f"Completed Responses: {completed_responses}\n")
    output.write(f"Completion Rate: 100%\n\n")
    
    # Group responses by question groups
    question_groups = {}
    for question in assessment.questions:
        group = question.question_group or "General"
        if group not in question_groups:
            question_groups[group] = []
        question_groups[group].append(question)
    
    # Write responses by group
    for group_name, questions in question_groups.items():
        output.write(f"QUESTION GROUP: {group_name.upper()}\n")
        output.write(f"-" * 40 + "\n\n")
        
        for question in sorted(questions, key=lambda q: q.order):
            output.write(f"Question {question.order + 1}: {question.question_text}\n")
            output.write(f"Type: {question.question_type}\n")
            output.write(f"Responses:\n")
            
            for response in assessment.responses:
                try:
                    response_data = json.loads(response.responses) if response.responses else {}
                    
                    # Get participant information from the participant relationship
                    participant = AssessmentParticipant.query.get(response.participant_id) if response.participant_id else None
                    
                    if participant:
                        # For assessor responses, show assessor as participant and assessee in role
                        if participant.assessor_id:  # Assessor response
                            participant_name = f"{participant.assessor.name} (Assessor for {participant.assessee.name})"
                        else:  # Self-assessment response
                            participant_name = f"{participant.assessee.name} (Self-Assessment)"
                    else:
                        # Fallback to user if participant not found
                        participant_name = response.user.name if response.user else "Anonymous"
                    
                    answer = response_data.get(str(question.id), "No response")
                    
                    output.write(f"  - {participant_name}: {answer}\n")
                except Exception as e:
                    print(f"Error processing response: {e}")
                    continue
            
            output.write("\n")
        
        output.write("\n")
    
    # Get assessee names for filename
    assessees = []
    for response in assessment.responses:
        participant = AssessmentParticipant.query.get(response.participant_id) if response.participant_id else None
        if participant and not participant.assessor_id:  # Self-assessment response (assessee)
            assessee_name = participant.assessee.name.replace(" ", "_")
            if assessee_name not in assessees:
                assessees.append(assessee_name)
    
    # Create filename with assessment and assessee names
    assessee_part = "_".join(assessees) if assessees else "NoAssessee"
    safe_title = assessment.title.replace(" ", "_").replace("/", "_").replace("\\", "_")
    filename = f"assessment_{assessment_id}_{safe_title}_{assessee_part}_detailed_report.txt"
    
    # Create response
    output.seek(0)
    response = make_response(output.getvalue())
    response.headers['Content-Type'] = 'text/plain'
    response.headers['Content-Disposition'] = f'attachment; filename={filename}'
    
    return response

# Assessment Analytics/Reports Page
@admin_app.route('/assessments/<int:assessment_id>/reports')
@admin_required
def admin_assessment_reports(assessment_id):
    assessment = Assessment.query.get_or_404(assessment_id)
    
    # Calculate analytics
    total_participants = len(assessment.invitations)
    completed_responses = len(assessment.responses)
    completion_rate = (completed_responses / total_participants * 100) if total_participants > 0 else 0
    
    # Group analysis by question groups
    question_groups = {}
    response_analysis = {}
    
    for question in assessment.questions:
        group = question.question_group or "General"
        if group not in question_groups:
            question_groups[group] = []
            response_analysis[group] = {}
        question_groups[group].append(question)
        
        # Analyze responses for this question
        responses_for_question = []
        for response in assessment.responses:
            try:
                response_data = json.loads(response.responses) if response.responses else {}
                answer = response_data.get(str(question.id))
                if answer:
                    responses_for_question.append(answer)
            except:
                continue
        
        response_analysis[group][question.id] = {
            'question': question,
            'responses': responses_for_question,
            'response_count': len(responses_for_question)
        }
    
    return render_template('admin_assessment_reports.html',
                         assessment=assessment,
                         total_participants=total_participants,
                         completed_responses=completed_responses,
                         completion_rate=completion_rate,
                         question_groups=question_groups,
                         response_analysis=response_analysis)

# All Data View - New comprehensive data view
@admin_app.route('/all-data')
@admin_required
def admin_all_data():
    # Get all assessments with their responses
    assessments = Assessment.query.order_by(Assessment.created_at.desc()).all()
    
    # Collect all data
    all_data = []
    
    for assessment in assessments:
        for response in assessment.responses:
            try:
                response_data = json.loads(response.responses) if response.responses else {}
                
                # Get participant information
                participant = AssessmentParticipant.query.get(response.participant_id) if response.participant_id else None
                
                if participant:
                    if participant.assessor_id:  # Assessor response
                        participant_name = participant.assessor.name
                        participant_email = participant.assessor.email
                        participant_role = participant.assessor_relationship or "Assessor"
                        assessee_name = participant.assessee.name
                        response_type = "Assessor Evaluation"
                    else:  # Self-assessment response
                        participant_name = participant.assessee.name
                        participant_email = participant.assessee.email
                        participant_role = "Self-Assessment"
                        assessee_name = participant.assessee.name
                        response_type = "Self-Assessment"
                else:
                    # Fallback
                    participant_name = response.user.name if response.user else "Anonymous"
                    participant_email = response.user.email if response.user else "N/A"
                    participant_role = response.user.role if response.user else "N/A"
                    assessee_name = "Unknown"
                    response_type = "Unknown"
                
                for question in assessment.questions:
                    # Try multiple possible keys for the question response
                    question_keys = [
                        str(question.id),
                        f"question_{question.id}",
                        f"q{question.id}"
                    ]
                    
                    raw_answer = ""
                    for key in question_keys:
                        if key in response_data:
                            raw_answer = response_data[key]
                            break
                    
                    if raw_answer and str(raw_answer).strip():
                        answer = str(raw_answer).strip()
                    else:
                        answer = "No response"
                    
                    all_data.append({
                        'assessment_id': assessment.id,
                        'assessment_title': assessment.title,
                        'assessment_created': assessment.created_at,
                        'company_name': assessment.company_ref.name if assessment.company_ref else 'N/A',
                        'participant_name': participant_name,
                        'participant_email': participant_email,
                        'participant_role': participant_role,
                        'assessee_name': assessee_name,
                        'response_type': response_type,
                        'question_group': question.question_group or "General",
                        'question_text': question.question_text,
                        'question_type': question.question_type,
                        'response': answer,
                        'submitted_at': response.submitted_at
                    })
            except Exception as e:
                print(f"Error processing response {response.id}: {e}")
                continue
    
    # Get summary statistics
    total_assessments = len(assessments)
    total_responses = len([data for data in all_data])
    total_participants = len(set([(data['participant_name'], data['participant_email']) for data in all_data]))
    total_companies = len(set([data['company_name'] for data in all_data if data['company_name'] != 'N/A']))
    
    # Group by assessment for summary
    assessment_summary = {}
    for data in all_data:
        assessment_key = f"{data['assessment_id']}-{data['assessment_title']}"
        if assessment_key not in assessment_summary:
            assessment_summary[assessment_key] = {
                'assessment': {
                    'id': data['assessment_id'],
                    'title': data['assessment_title'],
                    'created': data['assessment_created'],
                    'company': data['company_name']
                },
                'participants': set(),
                'responses': 0,
                'question_groups': set()
            }
        
        assessment_summary[assessment_key]['participants'].add((data['participant_name'], data['participant_email']))
        assessment_summary[assessment_key]['responses'] += 1
        assessment_summary[assessment_key]['question_groups'].add(data['question_group'])
    
    return render_template('admin_all_data.html',
                         all_data=all_data,
                         total_assessments=total_assessments,
                         total_responses=total_responses,
                         total_participants=total_participants,
                         total_companies=total_companies,
                         assessment_summary=assessment_summary)

@admin_app.route('/invitations')
@admin_required
def admin_invitations():
    page = request.args.get('page', 1, type=int)
    invitations = Invitation.query.order_by(Invitation.sent_at.desc()).paginate(
        page=page, per_page=20, error_out=False)
    return render_template('admin_invitations.html', invitations=invitations)

@admin_app.route('/invitations/send', methods=['GET', 'POST'])
@admin_required
def admin_send_invitations():
    if request.method == 'POST':
        assessment_id = request.form.get('assessment_id', type=int)
        emails = request.form.get('emails', '').strip()
        sender_id = request.form.get('sender_id', type=int)
        
        if not assessment_id or not emails:
            flash('Assessment and email addresses are required!', 'error')
            assessments = Assessment.query.filter_by(is_active=True).all()
            users = User.query.filter_by(is_active=True).all()
            return render_template('admin_send_invitations.html', assessments=assessments, users=users)
        
        assessment = Assessment.query.get(assessment_id)
        if not assessment:
            flash('Assessment not found!', 'error')
            assessments = Assessment.query.filter_by(is_active=True).all()
            users = User.query.filter_by(is_active=True).all()
            return render_template('admin_send_invitations.html', assessments=assessments, users=users)
        
        # Parse emails
        email_list = [email.strip().lower() for email in emails.replace(',', '\n').split('\n') if email.strip()]
        
        sent_count = 0
        for email in email_list:
            # Check if invitation already exists
            existing = Invitation.query.filter_by(assessment_id=assessment_id, email=email).first()
            if existing:
                continue
            
            # Create invitation
            token = secrets.token_urlsafe(32)
            invitation = Invitation(
                assessment_id=assessment_id,
                sender_id=sender_id or 1,
                email=email,
                token=token
            )
            db.session.add(invitation)
            sent_count += 1
            
            # Send email (implement email sending here)
            try:
                send_invitation_email(email, assessment, token)
            except Exception as e:
                print(f"Error sending email to {email}: {e}")
        
        db.session.commit()
        flash(f'Sent {sent_count} invitations successfully!', 'success')
        return redirect(url_for('admin_invitations'))
    
    assessments = Assessment.query.filter_by(is_active=True).all()
    users = User.query.filter_by(is_active=True).all()
    return render_template('admin_send_invitations.html', assessments=assessments, users=users)

@admin_app.route('/invitations/<int:invitation_id>/delete', methods=['POST'])
@admin_required
def admin_delete_invitation(invitation_id):
    invitation = Invitation.query.get_or_404(invitation_id)
    
    # Check if invitation has already been responded to
    if invitation.is_completed:
        flash('Cannot delete invitation that has already been completed!', 'error')
        return redirect(url_for('admin_invitations'))
    
    # Store invitation details for flash message
    assessment_title = invitation.assessment.title
    recipient_email = invitation.email
    
    try:
        # Delete the invitation
        db.session.delete(invitation)
        db.session.commit()
        
        flash(f'Invitation for "{assessment_title}" sent to {recipient_email} has been deleted successfully!', 'success')
    except Exception as e:
        db.session.rollback()
        print(f"Error deleting invitation: {e}")
        flash(f'Error deleting invitation: {str(e)}', 'error')
    
    return redirect(url_for('admin_invitations'))

@admin_app.route('/invitations/bulk-delete', methods=['POST'])
@admin_required
def admin_bulk_delete_invitations():
    invitation_ids = request.json.get('invitation_ids', [])
    
    if not invitation_ids:
        return jsonify({'success': False, 'message': 'No invitations selected'})
    
    try:
        deleted_count = 0
        for invitation_id in invitation_ids:
            invitation = Invitation.query.get(invitation_id)
            if invitation and not invitation.is_completed:
                db.session.delete(invitation)
                deleted_count += 1
        
        db.session.commit()
        
        return jsonify({
            'success': True, 
            'message': f'Successfully deleted {deleted_count} invitation(s)',
            'deleted_count': deleted_count
        })
    except Exception as e:
        db.session.rollback()
        print(f"Error bulk deleting invitations: {e}")
        return jsonify({'success': False, 'message': f'Error deleting invitations: {str(e)}'})

@admin_app.route('/reports')
@admin_required
def admin_reports():
    # Assessment completion rates
    assessments_with_stats = []
    assessments = Assessment.query.all()
    
    for assessment in assessments:
        total_invitations = len(assessment.invitations)
        completed_responses = len(assessment.responses)
        completion_rate = (completed_responses / total_invitations * 100) if total_invitations > 0 else 0
        
        assessments_with_stats.append({
            'assessment': assessment,
            'total_invitations': total_invitations,
            'completed_responses': completed_responses,
            'completion_rate': round(completion_rate, 1)
        })
    
    # User activity stats
    user_stats = []
    users = User.query.all()
    
    for user in users:
        assessments_created = len(user.created_assessments)
        responses_submitted = len(user.responses)
        invitations_sent = len(user.invitations_sent)
        
        user_stats.append({
            'user': user,
            'assessments_created': assessments_created,
            'responses_submitted': responses_submitted,
            'invitations_sent': invitations_sent
        })
    
    return render_template('admin_reports.html', 
                         assessments_with_stats=assessments_with_stats,
                         user_stats=user_stats)

@admin_app.route('/notifications')
@admin_required
def admin_notifications():
    # Get pending invitations (notifications to send)
    pending_invitations = Invitation.query.filter_by(is_completed=False).all()
    
    # Get overdue assessments
    overdue_assessments = Assessment.query.filter(
        Assessment.deadline < datetime.utcnow(),
        Assessment.is_active == True
    ).all()
    
    return render_template('admin_notifications.html',
                         pending_invitations=pending_invitations,
                         overdue_assessments=overdue_assessments)

@admin_app.route('/send-reminder/<int:invitation_id>', methods=['POST'])
@admin_required
def send_reminder(invitation_id):
    invitation = Invitation.query.get_or_404(invitation_id)
    
    try:
        send_invitation_email(invitation.email, invitation.assessment, invitation.token, is_reminder=True)
        flash(f'Reminder sent to {invitation.email}!', 'success')
    except Exception as e:
        flash(f'Failed to send reminder: {str(e)}', 'error')
    
    return redirect(url_for('admin_notifications'))

def send_self_assessment_invitation(email, assessment, token, assessee_name=None):
    """Send self-assessment invitation email"""
    try:
        msg = Message(
            subject=f'Complete Your Self-Assessment - {assessment.title}',
            recipients=[email]
        )
        
        # Create the invitation URL (pointing to main app)
        main_app_url = os.environ.get('MAIN_APP_URL', 'https://asistentica.online')
        invitation_url = f"{main_app_url}/respond/{token}"
        
        display_name = assessee_name or "yourself"
        
        msg.html = f"""
        <div style="font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; max-width: 600px; margin: 0 auto; background-color: #f8f9fa;">
            <div style="background: linear-gradient(135deg, #1976d2 0%, #1565c0 100%); padding: 30px; text-align: center;">
                <h1 style="color: white; margin: 0; font-size: 28px; font-weight: 300;">Modern360</h1>
                <p style="color: white; margin: 10px 0 0 0; opacity: 0.9;">Assessment Platform</p>
            </div>
            
            <div style="padding: 40px 30px; background-color: white;">
                <h2 style="color: #333; margin-bottom: 20px; font-size: 24px; font-weight: 400;">Self-Assessment Invitation</h2>
                
                <p style="color: #666; font-size: 16px; line-height: 1.6; margin-bottom: 20px;">
                    You have been invited to complete a self-assessment for <strong>{display_name}</strong>:
                </p>
                
                <div style="background-color: #f8f9fa; padding: 20px; border-radius: 8px; margin: 20px 0; border-left: 4px solid #1976d2;">
                    <h3 style="color: #1976d2; margin: 0; font-size: 18px; font-weight: 500;">{assessment.title}</h3>
                    <p style="color: #666; margin: 10px 0 0 0; font-size: 14px;">Company: {assessment.company_ref.name if assessment.company_ref else 'N/A'}</p>
                </div>
                
                <p style="color: #666; font-size: 16px; line-height: 1.6; margin-bottom: 20px;">
                    {assessment.description or 'Please complete this self-assessment to evaluate your own performance and professional development.'}
                </p>
                
                <p style="color: #666; font-size: 16px; line-height: 1.6; margin-bottom: 30px;">
                    Click the button below to start your self-assessment:
                </p>
                
                <div style="text-align: center; margin: 30px 0;">
                    <a href="{invitation_url}" style="display: inline-block; background-color: #4caf50; color: white; padding: 14px 28px; text-decoration: none; border-radius: 6px; font-size: 16px; font-weight: 500;">Complete Self-Assessment</a>
                </div>
                
                <div style="margin-top: 30px; padding: 15px; background-color: #e8f5e8; border-radius: 6px; border-left: 4px solid #4caf50;">
                    <p style="color: #2e7d32; font-size: 14px; margin: 0;">
                        <strong>Assessment Type:</strong> Self-Assessment<br>
                        <strong>Your Role:</strong> Evaluate your own performance<br>
                        <strong>Time Required:</strong> Approximately 10-15 minutes
                    </p>
                </div>
                
                <div style="margin-top: 20px; padding: 15px; background-color: #e7f3ff; border-radius: 6px; border-left: 4px solid #1976d2;">
                    <p style="color: #0d47a1; font-size: 14px; margin: 0;">
                        If the button doesn't work, copy and paste this link into your browser:<br>
                        <span style="word-break: break-all; font-family: monospace;">{invitation_url}</span>
                    </p>
                </div>
            </div>
            
            <div style="padding: 20px 30px; background-color: #f8f9fa; text-align: center; border-top: 1px solid #dee2e6;">
                <p style="color: #6c757d; font-size: 12px; margin: 0;">
                    This is an automated email from Modern360 Assessment Platform.<br>
                    Your responses are confidential and will be used for professional development purposes only.
                </p>
            </div>
        </div>
        """
        
        mail.send(msg)
    except Exception as e:
        print(f"Error sending self-assessment email: {e}")
        raise

def send_assessor_invitation(email, assessment, assessee_name, token, assessor_relationship=None):
    """Send assessor invitation email"""
    try:
        msg = Message(
            subject=f'Assess {assessee_name} - {assessment.title}',
            recipients=[email]
        )
        
        # Create the invitation URL (pointing to main app)
        main_app_url = os.environ.get('MAIN_APP_URL', 'https://asistentica.online')
        invitation_url = f"{main_app_url}/respond/{token}"
        
        relationship_text = f"as their {assessor_relationship}" if assessor_relationship else "as an assessor"
        
        msg.html = f"""
        <div style="font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; max-width: 600px; margin: 0 auto; background-color: #f8f9fa;">
            <div style="background: linear-gradient(135deg, #1976d2 0%, #1565c0 100%); padding: 30px; text-align: center;">
                <h1 style="color: white; margin: 0; font-size: 28px; font-weight: 300;">Modern360</h1>
                <p style="color: white; margin: 10px 0 0 0; opacity: 0.9;">Assessment Platform</p>
            </div>
            
            <div style="padding: 40px 30px; background-color: white;">
                <h2 style="color: #333; margin-bottom: 20px; font-size: 24px; font-weight: 400;">Assessment Invitation</h2>
                
                <p style="color: #666; font-size: 16px; line-height: 1.6; margin-bottom: 20px;">
                    You have been invited to assess <strong>{assessee_name}</strong> {relationship_text} in the following assessment:
                </p>
                
                <div style="background-color: #f8f9fa; padding: 20px; border-radius: 8px; margin: 20px 0; border-left: 4px solid #1976d2;">
                    <h3 style="color: #1976d2; margin: 0; font-size: 18px; font-weight: 500;">{assessment.title}</h3>
                    <p style="color: #666; margin: 10px 0 0 0; font-size: 14px;">Company: {assessment.company_ref.name if assessment.company_ref else 'N/A'}</p>
                </div>
                
                <p style="color: #666; font-size: 16px; line-height: 1.6; margin-bottom: 20px;">
                    {assessment.description or 'Please complete this assessment to provide valuable feedback on the selected individual\'s performance.'}
                </p>
                
                <p style="color: #666; font-size: 16px; line-height: 1.6; margin-bottom: 30px;">
                    Click the button below to start the assessment:
                </p>
                
                <div style="text-align: center; margin: 30px 0;">
                    <a href="{invitation_url}" style="display: inline-block; background-color: #ff9800; color: white; padding: 14px 28px; text-decoration: none; border-radius: 6px; font-size: 16px; font-weight: 500;">Start Assessment</a>
                </div>
                
                <div style="margin-top: 30px; padding: 15px; background-color: #fff3e0; border-radius: 6px; border-left: 4px solid #ff9800;">
                    <p style="color: #e65100; font-size: 14px; margin: 0;">
                        <strong>Assessment Details:</strong><br>
                        <strong>Assessing:</strong> {assessee_name}<br>
                        <strong>Your Role:</strong> {assessor_relationship or 'Assessor'}<br>
                        <strong>Time Required:</strong> Approximately 10-15 minutes
                    </p>
                </div>
                
                <div style="margin-top: 20px; padding: 15px; background-color: #e7f3ff; border-radius: 6px; border-left: 4px solid #1976d2;">
                    <p style="color: #0d47a1; font-size: 14px; margin: 0;">
                        If the button doesn't work, copy and paste this link into your browser:<br>
                        <span style="word-break: break-all; font-family: monospace;">{invitation_url}</span>
                    </p>
                </div>
            </div>
            
            <div style="padding: 20px 30px; background-color: #f8f9fa; text-align: center; border-top: 1px solid #dee2e6;">
                <p style="color: #6c757d; font-size: 12px; margin: 0;">
                    This is an automated email from Modern360 Assessment Platform.<br>
                    Your feedback is valuable and will help in professional development.
                </p>
            </div>
        </div>
        """
        
        mail.send(msg)
    except Exception as e:
        print(f"Error sending assessor email: {e}")
        raise

def send_invitation_email(email, assessment, token, is_reminder=False):
    """Send invitation email"""
    try:
        msg = Message(
            subject=f"{'Reminder: ' if is_reminder else ''}Assessment Invitation - {assessment.title}",
            recipients=[email]
        )
        
        # Create the invitation URL (pointing to main app)
        main_app_url = os.environ.get('MAIN_APP_URL', 'https://asistentica.online')
        invitation_url = f"{main_app_url}/respond/{token}"
        
        msg.html = f"""
        <div style="font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; max-width: 600px; margin: 0 auto; background-color: #f8f9fa;">
            <div style="background: linear-gradient(135deg, #1976d2 0%, #1565c0 100%); padding: 30px; text-align: center;">
                <h1 style="color: white; margin: 0; font-size: 28px; font-weight: 300;">Modern360</h1>
                <p style="color: white; margin: 10px 0 0 0; opacity: 0.9;">Assessment Platform</p>
            </div>
            
            <div style="padding: 40px 30px; background-color: white;">
                <h2 style="color: #333; margin-bottom: 20px; font-size: 24px; font-weight: 400;">
                    {'Assessment Reminder' if is_reminder else 'Assessment Invitation'}
                </h2>
                
                <p style="color: #666; font-size: 16px; line-height: 1.6; margin-bottom: 20px;">
                    {'This is a reminder that you have' if is_reminder else 'You have'} been invited to complete the assessment:
                </p>
                
                <div style="background-color: #f8f9fa; padding: 20px; border-radius: 8px; margin: 20px 0; border-left: 4px solid #1976d2;">
                    <h3 style="color: #1976d2; margin: 0; font-size: 18px; font-weight: 500;">{assessment.title}</h3>
                    <p style="color: #666; margin: 10px 0 0 0; font-size: 14px;">Company: {assessment.company_ref.name if hasattr(assessment, 'company_ref') and assessment.company_ref else 'N/A'}</p>
                </div>
                
                <p style="color: #666; font-size: 16px; line-height: 1.6; margin-bottom: 20px;">
                    {assessment.description or 'Please complete this assessment.'}
                </p>
                
                <p style="color: #666; font-size: 16px; line-height: 1.6; margin-bottom: 30px;">
                    Click the button below to start the assessment:
                </p>
                
                <div style="text-align: center; margin: 30px 0;">
                    <a href="{invitation_url}" style="display: inline-block; background-color: {'#f44336' if is_reminder else '#1976d2'}; color: white; padding: 14px 28px; text-decoration: none; border-radius: 6px; font-size: 16px; font-weight: 500;">
                        {'Complete Assessment Now' if is_reminder else 'Start Assessment'}
                    </a>
                </div>
                
                <div style="margin-top: 30px; padding: 15px; background-color: {'#ffebee' if is_reminder else '#e7f3ff'}; border-radius: 6px; border-left: 4px solid {'#f44336' if is_reminder else '#1976d2'};">
                    <p style="color: {'#c62828' if is_reminder else '#0d47a1'}; font-size: 14px; margin: 0;">
                        {'Please complete this assessment as soon as possible.' if is_reminder else 'Thank you for your participation.'}
                    </p>
                </div>
                
                <div style="margin-top: 20px; padding: 15px; background-color: #e7f3ff; border-radius: 6px; border-left: 4px solid #1976d2;">
                    <p style="color: #0d47a1; font-size: 14px; margin: 0;">
                        If the button doesn't work, copy and paste this link into your browser:<br>
                        <span style="word-break: break-all; font-family: monospace;">{invitation_url}</span>
                    </p>
                </div>
            </div>
            
            <div style="padding: 20px 30px; background-color: #f8f9fa; text-align: center; border-top: 1px solid #dee2e6;">
                <p style="color: #6c757d; font-size: 12px; margin: 0;">
                    This is an automated email from Modern360 Assessment Platform.
                </p>
            </div>
        </div>
        """
        
        mail.send(msg)
    except Exception as e:
        print(f"Error sending invitation email: {e}")
        raise

@admin_app.route('/favicon.ico')
def favicon():
    """Handle favicon requests - serve the actual favicon file"""
    from flask import send_from_directory, abort
    import os
    
    try:
        # Try to serve the favicon from the static folder
        return send_from_directory(
            os.path.join(admin_app.root_path, 'static'),
            'favicon.ico',
            mimetype='image/vnd.microsoft.icon'
        )
    except FileNotFoundError:
        # If favicon doesn't exist, return a 204 No Content response
        from flask import make_response
        response = make_response('')
        response.status_code = 204
        return response

@admin_app.before_request
def create_tables():
    if not hasattr(create_tables, '_called'):
        db.create_all()
        create_tables._called = True

# Mount the admin app under /admin using DispatcherMiddleware
application = DispatcherMiddleware(None, {
    '/admin': admin_app
})

if __name__ == '__main__':
    admin_port = int(os.environ.get('ADMIN_PORT', 5001))
    admin_app.run(host='0.0.0.0', port=admin_port, debug=os.environ.get('FLASK_ENV') == 'development')
