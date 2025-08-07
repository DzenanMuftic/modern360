from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
from flask_mail import Mail, Message
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from datetime import datetime, timedelta
import secrets
import os
from werkzeug.security import generate_password_hash, check_password_hash
import uuid
import random
import string
import json
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'dev-secret-key-change-in-production')

# Database configuration
database_url = os.environ.get('DATABASE_URL', 'sqlite:///modern360.db')
# Fix for Render.com PostgreSQL URL format
if database_url and database_url.startswith('postgres://'):
    database_url = database_url.replace('postgres://', 'postgresql://', 1)
app.config['SQLALCHEMY_DATABASE_URI'] = database_url
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Mail configuration
app.config['MAIL_SERVER'] = os.environ.get('MAIL_SERVER', 'smtp.gmail.com')
app.config['MAIL_PORT'] = int(os.environ.get('MAIL_PORT', 587))
# Use SSL for port 465, TLS for port 587
mail_port = int(os.environ.get('MAIL_PORT', 587))
if mail_port == 465:
    app.config['MAIL_USE_SSL'] = True
    app.config['MAIL_USE_TLS'] = False
else:
    app.config['MAIL_USE_TLS'] = True
    app.config['MAIL_USE_SSL'] = False
app.config['MAIL_USERNAME'] = os.environ.get('MAIL_USERNAME')
app.config['MAIL_PASSWORD'] = os.environ.get('MAIL_PASSWORD')
app.config['MAIL_DEFAULT_SENDER'] = os.environ.get('MAIL_DEFAULT_SENDER')

# Initialize extensions
db = SQLAlchemy(app)
migrate = Migrate(app, db)
mail = Mail(app)

# Database Models
class Company(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(150), unique=True, nullable=False)
    description = db.Column(db.Text)
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
    verification_codes = db.relationship('EmailVerification', backref='user', lazy=True)

class EmailVerification(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)  # nullable for new users
    email = db.Column(db.String(120), nullable=False)
    code = db.Column(db.String(6), nullable=False)  # 6-digit verification code
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    expires_at = db.Column(db.DateTime, nullable=False)
    is_used = db.Column(db.Boolean, default=False)
    login_token = db.Column(db.String(100), unique=True, nullable=False)  # unique token for email link

class Assessment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text)
    creator_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    company_id = db.Column(db.Integer, db.ForeignKey('company.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    deadline = db.Column(db.DateTime)
    is_active = db.Column(db.Boolean, default=True)
    is_self_assessment = db.Column(db.Boolean, default=False)  # New field for self-assessment
    
    # Relationships
    invitations = db.relationship('Invitation', backref='assessment', lazy=True)
    responses = db.relationship('AssessmentResponse', backref='assessment', lazy=True)
    questions = db.relationship('Question', backref='assessment', lazy=True)

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
    
    # Relationships
    assessee = db.relationship('User', foreign_keys=[assessee_id], backref='assessee_participations')
    assessor = db.relationship('User', foreign_keys=[assessor_id], backref='assessor_participations')
    assessment = db.relationship('Assessment', backref='participants')

class AssessmentResponse(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    assessment_id = db.Column(db.Integer, db.ForeignKey('assessment.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    invitation_id = db.Column(db.Integer, db.ForeignKey('invitation.id'))
    participant_id = db.Column(db.Integer, db.ForeignKey('assessment_participant.id'), nullable=True)
    responses = db.Column(db.Text)  # JSON string of responses
    response_type = db.Column(db.String(20), default='assessor')  # 'self' or 'assessor'
    submitted_at = db.Column(db.DateTime, default=datetime.utcnow)

# Routes
@app.route('/')
def index():
    if 'user' in session:
        return redirect(url_for('dashboard'))
    return render_template('index.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form.get('email', '').strip().lower()
        
        if not email:
            flash('Please enter your email address.', 'error')
            return render_template('login.html')
        
        # Generate 6-digit verification code
        verification_code = ''.join(random.choices(string.digits, k=6))
        login_token = secrets.token_urlsafe(32)
        
        # Create verification record
        verification = EmailVerification(
            email=email,
            code=verification_code,
            expires_at=datetime.utcnow() + timedelta(minutes=15),  # 15 minutes expiry
            login_token=login_token
        )
        
        # Check if user exists, if not we'll create them after verification
        user = User.query.filter_by(email=email).first()
        if user:
            verification.user_id = user.id
        
        db.session.add(verification)
        db.session.commit()
        
        # Send verification email
        send_verification_email(email, verification_code, login_token)
        
        flash(f'Verification code sent to {email}. Please check your email.', 'success')
        return redirect(url_for('verify_email', token=login_token))
    
    return render_template('login.html')

@app.route('/verify/<token>')
def verify_email(token):
    verification = EmailVerification.query.filter_by(login_token=token, is_used=False).first()
    
    if not verification:
        flash('Invalid or expired verification link.', 'error')
        return redirect(url_for('login'))
    
    if verification.expires_at < datetime.utcnow():
        flash('Verification code has expired. Please request a new one.', 'error')
        return redirect(url_for('login'))
    
    return render_template('verify_email.html', verification=verification)

@app.route('/verify/<token>', methods=['POST'])
def verify_code(token):
    verification = EmailVerification.query.filter_by(login_token=token, is_used=False).first()
    
    if not verification:
        flash('Invalid or expired verification link.', 'error')
        return redirect(url_for('login'))
    
    if verification.expires_at < datetime.utcnow():
        flash('Verification code has expired. Please request a new one.', 'error')
        return redirect(url_for('login'))
    
    entered_code = request.form.get('code', '').strip()
    
    if entered_code != verification.code:
        flash('Invalid verification code. Please try again.', 'error')
        return render_template('verify_email.html', verification=verification)
    
    # Mark verification as used
    verification.is_used = True
    
    # Get or create user
    user = verification.user
    if not user:
        # Create new user
        user = User(
            email=verification.email,
            name=verification.email.split('@')[0].title()  # Use email prefix as default name
        )
        db.session.add(user)
        verification.user = user
    
    # Update last login
    user.last_login = datetime.utcnow()
    db.session.commit()
    
    # Create session
    session['user'] = {
        'id': user.id,
        'email': user.email,
        'name': user.name,
        'company': user.company,
        'role': user.role
    }
    
    flash(f'Welcome{" back" if verification.user_id else ""}, {user.name}!', 'success')
    return redirect(url_for('dashboard'))

@app.route('/auth/direct/<token>')
def direct_login(token):
    """Direct login from email link without code entry"""
    verification = EmailVerification.query.filter_by(login_token=token, is_used=False).first()
    
    if not verification:
        flash('Invalid or expired login link.', 'error')
        return redirect(url_for('login'))
    
    if verification.expires_at < datetime.utcnow():
        flash('Login link has expired. Please request a new one.', 'error')
        return redirect(url_for('login'))
    
    # Mark verification as used
    verification.is_used = True
    
    # Get or create user
    user = verification.user
    if not user:
        # Create new user
        user = User(
            email=verification.email,
            name=verification.email.split('@')[0].title()  # Use email prefix as default name
        )
        db.session.add(user)
        verification.user = user
    
    # Update last login
    user.last_login = datetime.utcnow()
    db.session.commit()
    
    # Create session
    session['user'] = {
        'id': user.id,
        'email': user.email,
        'name': user.name,
        'company': user.company,
        'role': user.role
    }
    
    flash(f'Welcome{" back" if verification.user_id else ""}, {user.name}!', 'success')
    return redirect(url_for('dashboard'))

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('index'))

@app.route('/dashboard')
def dashboard():
    if 'user' not in session:
        return redirect(url_for('login'))
    
    user_id = session['user']['id']
    assessments = Assessment.query.filter_by(creator_id=user_id).order_by(Assessment.created_at.desc()).all()
    recent_responses = AssessmentResponse.query.join(Assessment).filter(Assessment.creator_id == user_id).order_by(AssessmentResponse.submitted_at.desc()).limit(5).all()
    
    return render_template('dashboard.html', assessments=assessments, recent_responses=recent_responses)

@app.route('/assessment/create', methods=['GET', 'POST'])
def create_assessment():
    if 'user' not in session:
        return redirect(url_for('login'))
    
    if request.method == 'POST':
        is_self_assessment = request.form.get('is_self_assessment') == 'on'
        assessment = Assessment(
            title=request.form['title'],
            description=request.form['description'],
            creator_id=session['user']['id'],
            deadline=datetime.strptime(request.form['deadline'], '%Y-%m-%d') if request.form['deadline'] else None,
            is_self_assessment=is_self_assessment
        )
        db.session.add(assessment)
        db.session.commit()
        
        if is_self_assessment:
            flash('Self-assessment created successfully! You can now complete it yourself.', 'success')
            # For self-assessment, redirect directly to the assessment response
            return redirect(url_for('self_assess', id=assessment.id))
        else:
            flash('Assessment created successfully!', 'success')
            return redirect(url_for('edit_assessment', id=assessment.id))
    
    return render_template('create_assessment.html')

@app.route('/assessment/<int:id>/edit')
def edit_assessment(id):
    if 'user' not in session:
        return redirect(url_for('login'))
    
    assessment = Assessment.query.get_or_404(id)
    if assessment.creator_id != session['user']['id']:
        flash('Access denied.', 'error')
        return redirect(url_for('dashboard'))
    
    return render_template('edit_assessment.html', assessment=assessment)

@app.route('/assessment/<int:id>/invite', methods=['GET', 'POST'])
def invite_users(id):
    if 'user' not in session:
        return redirect(url_for('login'))
    
    assessment = Assessment.query.get_or_404(id)
    if assessment.creator_id != session['user']['id']:
        flash('Access denied.', 'error')
        return redirect(url_for('dashboard'))
    
    if request.method == 'POST':
        emails = request.form['emails'].split(',')
        emails = [email.strip() for email in emails if email.strip()]
        
        for email in emails:
            # Check if invitation already exists
            existing = Invitation.query.filter_by(assessment_id=id, email=email).first()
            if not existing:
                token = secrets.token_urlsafe(32)
                invitation = Invitation(
                    assessment_id=id,
                    sender_id=session['user']['id'],
                    email=email,
                    token=token
                )
                db.session.add(invitation)
                
                # Send email
                send_invitation_email(email, assessment.title, token)
        
        db.session.commit()
        flash(f'Invitations sent to {len(emails)} recipients!', 'success')
        return redirect(url_for('assessment_details', id=id))
    
    return render_template('invite_users.html', assessment=assessment)

@app.route('/assessment/<int:id>')
def assessment_details(id):
    if 'user' not in session:
        return redirect(url_for('login'))
    
    assessment = Assessment.query.get_or_404(id)
    if assessment.creator_id != session['user']['id']:
        flash('Access denied.', 'error')
        return redirect(url_for('dashboard'))
    
    invitations = Invitation.query.filter_by(assessment_id=id).all()
    responses = AssessmentResponse.query.filter_by(assessment_id=id).all()
    
    return render_template('assessment_details.html', assessment=assessment, invitations=invitations, responses=responses)

@app.route('/respond/<token>')
def respond_to_assessment(token):
    invitation = Invitation.query.filter_by(token=token).first_or_404()
    assessment = invitation.assessment
    
    if invitation.is_completed:
        return render_template('already_completed.html')
    
    # Get questions for this assessment
    questions = Question.query.filter_by(assessment_id=assessment.id).order_by(Question.question_group, Question.order, Question.id).all()
    
    # Get participant information
    participant = None
    assessee_name = "Unknown"
    assessor_relationship = None
    
    # Try to find participant by invitation email
    participants = AssessmentParticipant.query.filter_by(assessment_id=assessment.id).all()
    for p in participants:
        if p.assessor and p.assessor.email == invitation.email:
            participant = p
            assessee_name = p.assessee.name
            assessor_relationship = p.assessor_relationship
            break
        elif p.assessee and p.assessee.email == invitation.email and not p.assessor_id:
            # Self-assessment
            participant = p
            assessee_name = p.assessee.name
            assessor_relationship = "Self Assessment"
            break
    
    return render_template('assessment_questionnaire.html', 
                         assessment=assessment, 
                         invitation=invitation,
                         questions=questions,
                         participant=participant,
                         assessee_name=assessee_name,
                         assessor_relationship=assessor_relationship)

@app.route('/submit_assessment/<token>', methods=['POST'])
def submit_assessment(token):
    invitation = Invitation.query.filter_by(token=token).first_or_404()
    
    if invitation.is_completed:
        return jsonify({'success': False, 'message': 'Assessment already completed'}), 400
    
    try:
        data = request.get_json()
        responses = data.get('responses', {})
        participant_id = data.get('participant_id')
        
        # Determine response type
        response_type = 'assessor'
        if participant_id:
            participant = AssessmentParticipant.query.get(participant_id)
            if participant and not participant.assessor_id:
                response_type = 'self'
        
        # Save response
        response = AssessmentResponse(
            assessment_id=invitation.assessment_id,
            invitation_id=invitation.id,
            participant_id=participant_id,
            responses=json.dumps(responses),
            response_type=response_type
        )
        
        # Mark invitation as completed
        invitation.is_completed = True
        invitation.responded_at = datetime.utcnow()
        
        # Update participant status
        if participant_id:
            participant = AssessmentParticipant.query.get(participant_id)
            if participant:
                if response_type == 'self':
                    participant.self_assessment_completed = True
                    participant.self_assessment_date = datetime.utcnow()
                else:
                    participant.assessor_assessment_completed = True
                    participant.assessor_assessment_date = datetime.utcnow()
        
        db.session.add(response)
        db.session.commit()
        
        return jsonify({'success': True, 'message': 'Assessment submitted successfully'})
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': f'Error submitting assessment: {str(e)}'}), 500

@app.route('/assessment/<int:id>/self-assess')
def self_assess(id):
    if 'user' not in session:
        return redirect(url_for('login'))
    
    assessment = Assessment.query.get_or_404(id)
    
    # Check if user is the creator and if it's a self-assessment
    if assessment.creator_id != session['user']['id']:
        flash('Access denied.', 'error')
        return redirect(url_for('dashboard'))
    
    if not assessment.is_self_assessment:
        flash('This is not a self-assessment.', 'error')
        return redirect(url_for('assessment_details', id=id))
    
    # Check if user has already completed the self-assessment
    existing_response = AssessmentResponse.query.filter_by(
        assessment_id=id, 
        user_id=session['user']['id']
    ).first()
    
    if existing_response:
        flash('You have already completed this self-assessment.', 'info')
        return redirect(url_for('assessment_details', id=id))
    
    return render_template('self_assessment.html', assessment=assessment)

@app.route('/submit_self_assessment/<int:id>', methods=['POST'])
def submit_self_assessment(id):
    if 'user' not in session:
        return redirect(url_for('login'))
    
    assessment = Assessment.query.get_or_404(id)
    
    # Verify permissions
    if assessment.creator_id != session['user']['id'] or not assessment.is_self_assessment:
        return jsonify({'error': 'Access denied'}), 403
    
    # Check if already completed
    existing_response = AssessmentResponse.query.filter_by(
        assessment_id=id, 
        user_id=session['user']['id']
    ).first()
    
    if existing_response:
        return jsonify({'error': 'Self-assessment already completed'}), 400
    
    # Save response
    response = AssessmentResponse(
        assessment_id=id,
        user_id=session['user']['id'],
        responses=request.get_json()
    )
    
    db.session.add(response)
    db.session.commit()
    
    return jsonify({'success': True})

def send_verification_email(email, verification_code, login_token):
    """Send verification email with code and direct login link"""
    try:
        msg = Message(
            subject='Your Modern360 Login Code',
            recipients=[email]
        )
        
        direct_login_url = url_for('direct_login', token=login_token, _external=True)
        verify_url = url_for('verify_email', token=login_token, _external=True)
        
        msg.html = f"""
        <div style="font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; max-width: 600px; margin: 0 auto; background-color: #f8f9fa;">
            <div style="background: linear-gradient(135deg, #1976d2 0%, #1565c0 100%); padding: 30px; text-align: center;">
                <h1 style="color: white; margin: 0; font-size: 28px; font-weight: 300;">Modern360</h1>
                <p style="color: white; margin: 10px 0 0 0; opacity: 0.9;">Assessment Platform</p>
            </div>
            
            <div style="padding: 40px 30px; background-color: white;">
                <h2 style="color: #333; margin-bottom: 20px; font-size: 24px; font-weight: 400;">Your Login Code</h2>
                
                <p style="color: #666; font-size: 16px; line-height: 1.6; margin-bottom: 30px;">
                    Use this verification code to log in to your Modern360 account:
                </p>
                
                <div style="text-align: center; margin: 30px 0;">
                    <div style="display: inline-block; background-color: #f5f5f5; padding: 20px 30px; border-radius: 8px; border: 2px dashed #1976d2;">
                        <span style="font-size: 32px; font-weight: bold; color: #1976d2; letter-spacing: 4px; font-family: 'Courier New', monospace;">{verification_code}</span>
                    </div>
                </div>
                
                <div style="text-align: center; margin: 30px 0;">
                    <a href="{verify_url}" style="display: inline-block; background-color: #1976d2; color: white; padding: 14px 28px; text-decoration: none; border-radius: 6px; font-size: 16px; font-weight: 500;">Enter Code</a>
                </div>
                
                <div style="border-top: 1px solid #eee; margin: 30px 0; padding-top: 20px;">
                    <p style="color: #666; font-size: 14px; margin-bottom: 15px;">
                        <strong>Quick Login:</strong> Click the button below to log in instantly without entering the code:
                    </p>
                    <div style="text-align: center;">
                        <a href="{direct_login_url}" style="display: inline-block; background-color: #4caf50; color: white; padding: 12px 24px; text-decoration: none; border-radius: 6px; font-size: 14px;">Login Instantly</a>
                    </div>
                </div>
                
                <div style="margin-top: 30px; padding: 15px; background-color: #fff3cd; border-radius: 6px; border-left: 4px solid #ffc107;">
                    <p style="color: #856404; font-size: 14px; margin: 0;">
                        <strong>Security Note:</strong> This code expires in 15 minutes. If you didn't request this login, please ignore this email.
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
        print(f"Error sending verification email: {e}")

def send_invitation_email(email, assessment_title, token):
    """Send invitation email to user"""
    try:
        msg = Message(
            subject=f'You have been invited to complete: {assessment_title}',
            recipients=[email]
        )
        
        invitation_url = url_for('respond_to_assessment', token=token, _external=True)
        
        msg.html = f"""
        <div style="font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; max-width: 600px; margin: 0 auto; background-color: #f8f9fa;">
            <div style="background: linear-gradient(135deg, #1976d2 0%, #1565c0 100%); padding: 30px; text-align: center;">
                <h1 style="color: white; margin: 0; font-size: 28px; font-weight: 300;">Modern360</h1>
                <p style="color: white; margin: 10px 0 0 0; opacity: 0.9;">Assessment Platform</p>
            </div>
            
            <div style="padding: 40px 30px; background-color: white;">
                <h2 style="color: #333; margin-bottom: 20px; font-size: 24px; font-weight: 400;">Assessment Invitation</h2>
                
                <p style="color: #666; font-size: 16px; line-height: 1.6; margin-bottom: 20px;">
                    You have been invited to complete the assessment:
                </p>
                
                <div style="background-color: #f8f9fa; padding: 20px; border-radius: 8px; margin: 20px 0; border-left: 4px solid #1976d2;">
                    <h3 style="color: #1976d2; margin: 0; font-size: 18px; font-weight: 500;">{assessment_title}</h3>
                </div>
                
                <p style="color: #666; font-size: 16px; line-height: 1.6; margin-bottom: 30px;">
                    Click the button below to start the assessment:
                </p>
                
                <div style="text-align: center; margin: 30px 0;">
                    <a href="{invitation_url}" style="display: inline-block; background-color: #1976d2; color: white; padding: 14px 28px; text-decoration: none; border-radius: 6px; font-size: 16px; font-weight: 500;">Start Assessment</a>
                </div>
                
                <div style="margin-top: 30px; padding: 15px; background-color: #e7f3ff; border-radius: 6px; border-left: 4px solid #1976d2;">
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
        print(f"Error sending email: {e}")

@app.route('/metrics')
def metrics():
    """Basic metrics endpoint for monitoring"""
    try:
        # Basic application metrics
        metrics_data = {
            'status': 'healthy',
            'timestamp': datetime.utcnow().isoformat(),
            'database_status': 'connected',
            'version': '1.0.0'
        }
        
        # Try to check database connection
        try:
            db.session.execute('SELECT 1')
            metrics_data['database_status'] = 'connected'
        except Exception:
            metrics_data['database_status'] = 'disconnected'
        
        # Return metrics in plain text format (Prometheus style)
        response_text = f"""# HELP app_status Application status
# TYPE app_status gauge
app_status{{status="{metrics_data['status']}"}} 1

# HELP database_status Database connection status
# TYPE database_status gauge
database_status{{status="{metrics_data['database_status']}"}} 1

# HELP app_info Application information
# TYPE app_info gauge
app_info{{version="{metrics_data['version']}"}} 1
"""
        
        return response_text, 200, {'Content-Type': 'text/plain'}
    
    except Exception as e:
        return f"# Error generating metrics: {str(e)}", 500, {'Content-Type': 'text/plain'}

@app.route('/favicon.ico')
def favicon():
    """Handle favicon requests to prevent 404 errors"""
    # Return a simple response or redirect to a static favicon if you have one
    from flask import make_response
    response = make_response('')
    response.status_code = 204  # No Content
    return response

@app.route('/health')
def health_check():
    """Simple health check endpoint"""
    try:
        # Check database connection
        db.session.execute('SELECT 1')
        return jsonify({
            'status': 'healthy',
            'timestamp': datetime.utcnow().isoformat(),
            'database': 'connected'
        }), 200
    except Exception as e:
        return jsonify({
            'status': 'unhealthy',
            'timestamp': datetime.utcnow().isoformat(),
            'database': 'disconnected',
            'error': str(e)
        }), 503

@app.before_request
def create_tables():
    if not hasattr(create_tables, '_called'):
        db.create_all()
        create_tables._called = True

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=os.environ.get('FLASK_ENV') == 'development')
