# app.py - Flask survey app (PostgreSQL version)
#
#  PostgreSQL integration by Saksham.
#
# This application:
#   - Accepts survey definition files (CSV / Excel).
#   - Dynamically builds HTML forms from those files.
#   - Stores responses in a PostgreSQL database via SQLAlchemy.
#   - Sends survey links via email.
#   - Exports collected responses back to Excel.
#1111111111111111     
# Requirements (install in your virtual environment):
#   pip install psycopg2-binary flask flask-mail flask-sqlalchemy pandas openpyxl

import os
import uuid
import pandas as pd
from datetime import datetime, timedelta
import json
from flask import Flask, request, render_template, jsonify, send_from_directory, abort, url_for, redirect, flash
from flask_mail import Mail, Message
from flask_sqlalchemy import SQLAlchemy
# ---- SECURE DATABASE CONFIGURATION ----Author: SAMANT
from urllib.parse import quote_plus
# ---- NEW IMPORTS FOR AUTH ----Author: SAMANT
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
# Add these imports
from authlib.integrations.flask_client import OAuth
import secrets


# -----------------------------------------------------------------------------
# Flask App Setup
# -----------------------------------------------------------------------------

app = Flask(__name__)

# --- OAUTH SETUP ---
oauth = OAuth(app)
google = oauth.register(
    name='google',
    client_id=os.environ.get('GOOGLE_CLIENT_ID'),
    client_secret=os.environ.get('GOOGLE_CLIENT_SECRET'),
    access_token_url='https://accounts.google.com/o/oauth2/token',
    access_token_params=None,
    authorize_url='https://accounts.google.com/o/oauth2/auth',
    authorize_params=None,
    api_base_url='https://www.googleapis.com/oauth2/v1/',
    userinfo_endpoint='https://openidconnect.googleapis.com/v1/userinfo',
    client_kwargs={'scope': 'email profile'},
    jwks_uri='https://www.googleapis.com/oauth2/v3/certs' # Enhances security
)

# 1. Get the absolute path to the folder where app.py lives
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# 2. Define folders using that absolute path
UPLOAD_FOLDER = os.path.join(BASE_DIR, 'uploads')
RESPONSES_FOLDER = os.path.join(BASE_DIR, 'responses')

# Ensure folders exist (development friendly).
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)
if not os.path.exists(RESPONSES_FOLDER):
    os.makedirs(RESPONSES_FOLDER)

# --- SECURE DATABASE / EMAIL CONFIG --- Author: SAMANT
# Prefer environment variables for deployment; fall back to private_config.py for local development.
try:
    from private_config import (
        DB_PASSWORD as PC_DB_PASSWORD,
        MAIL_EMAIL as PC_MAIL_EMAIL,
        MAIL_PASSWORD as PC_MAIL_PASSWORD,
    )
except ImportError:
    # On Render or any environment where private_config.py is not present,
    # these values will be provided via environment variables instead.
    PC_DB_PASSWORD = None
    PC_MAIL_EMAIL = None
    PC_MAIL_PASSWORD = None

# Read from environment first, then from private_config.py as a fallback.
DB_PASSWORD = os.environ.get("DB_PASSWORD", PC_DB_PASSWORD)
MAIL_EMAIL = os.environ.get("MAIL_EMAIL", PC_MAIL_EMAIL)
MAIL_PASSWORD = os.environ.get("MAIL_PASSWORD", PC_MAIL_PASSWORD)

# In cloud deployments we usually rely on DATABASE_URL, so DB_PASSWORD is optional.
encoded_password = quote_plus(DB_PASSWORD) if DB_PASSWORD is not None else ""

# -----------------------------------------------------------------------------
# Database Configuration (PostgreSQL)
# -----------------------------------------------------------------------------
# Modified by Saksham: switched from MySQL to PostgreSQL and added support
# for using an environment variable to configure the connection string.
#
# Example DATABASE_URL:
#   postgresql+psycopg2://flask_user:your_secure_password@localhost:5432/survey_db


# --- SECRET KEY IS REQUIRED FOR LOGIN SESSIONS ---
app.config['SECRET_KEY'] = 'change_this_to_something_secret_key_123'


# --- FIX FOR RENDER DEPLOYMENT ---
database_url = os.environ.get('DATABASE_URL')

# Render provides 'postgres://' but SQLAlchemy needs 'postgresql://'
if database_url and database_url.startswith("postgres://"):
    database_url = database_url.replace("postgres://", "postgresql://", 1)

app.config['SQLALCHEMY_DATABASE_URI'] = database_url or f'postgresql+psycopg2://flask_user:{encoded_password}@127.0.0.1/survey_db'

db = SQLAlchemy(app)

# -----------------------------------------------------------------------------
# Email Configuration
# -----------------------------------------------------------------------------
# In production, MAIL_* values should be set via environment variables and not
# hard-coded. Defaults below are for local development and testing only.

app.config['MAIL_SERVER'] = os.environ.get('MAIL_SERVER', 'smtp.gmail.com')
app.config['MAIL_PORT'] = int(os.environ.get('MAIL_PORT', 587))
app.config['MAIL_USE_TLS'] = os.environ.get('MAIL_USE_TLS', 'True') == 'True'

# Get email and password from environment or private_config.py ---Author: SAMANT
app.config['MAIL_USERNAME'] = MAIL_EMAIL
app.config['MAIL_PASSWORD'] = MAIL_PASSWORD
app.config['MAIL_DEFAULT_SENDER'] = MAIL_EMAIL

mail = Mail(app)

# --- LOGIN MANAGER SETUP ---
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login' # Redirect here if user isn't logged in

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))


# -----------------------------------------------------------------------------
# Database Model
# -----------------------------------------------------------------------------

# 1. USER TABLE (New)
class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(150), unique=True, nullable=False)
    email = db.Column(db.String(150), unique=True, nullable=False)
    password = db.Column(db.String(256), nullable=False)
    # Relationship to surveys
    surveys = db.relationship('SurveyMetadata', backref='owner', lazy=True)

# 2. SURVEY METADATA TABLE (New - Links File to User)
class SurveyMetadata(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    survey_uuid = db.Column(db.String(36), unique=True, nullable=False) # The ID in the URL
    filename = db.Column(db.String(200), nullable=False) # The Excel file name
    original_name = db.Column(db.String(200), nullable=False) # What the user called it
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False) # Who owns it

# 3. RESPONSE TABLE
class SurveyResponse(db.Model):

    id = db.Column(db.Integer, primary_key=True)
    survey_id = db.Column(db.String(36), index=True, nullable=False)  # UUID of the survey
    response_data = db.Column(db.Text, nullable=False)  # Store the form data as a JSON string
    submission_time = db.Column(db.DateTime, default=datetime.utcnow)

    # Create tables if they don't exist (Run this once on startup)
with app.app_context():
    db.create_all()
# -----------------------------------------------------------------------------
# Auth Routes (Login / Register)
# -----------------------------------------------------------------------------

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form.get('username')
        email = request.form.get('email')
        password = request.form.get('password')

        user_exists = User.query.filter_by(email=email).first()
        if user_exists:
            flash('Email already exists.', 'error')
            return redirect(url_for('register'))

        # Create new user with hashed password
        new_user = User(
            username=username, 
            email=email, 
            password=generate_password_hash(password, method='pbkdf2:sha256')
        )
        db.session.add(new_user)
        db.session.commit()
        
        login_user(new_user)
        return redirect(url_for('dashboard'))
        
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        
        user = User.query.filter_by(email=email).first()
        
        if user and check_password_hash(user.password, password):
            login_user(user)
            return redirect(url_for('dashboard'))
        else:
            flash('Incorrect email or password.', 'error')
            
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('index'))



# -----------------------------------------------------------------------------
# Main Routes
# -----------------------------------------------------------------------------

# --- GOOGLE LOGIN ROUTES ---

@app.route('/login/google')
def google_login():
    google = oauth.create_client('google')
    # This automatically uses the https://webproject... URL on Render
    redirect_uri = url_for('google_callback', _external=True)
    return google.authorize_redirect(redirect_uri)

@app.route('/auth/callback')
def google_callback():
    google = oauth.create_client('google')
    try:
        token = google.authorize_access_token()
        resp = google.get('userinfo')
        user_info = resp.json()
    except Exception as e:
        # If user cancels or something fails
        flash("Login failed. Please try again.", "error")
        return redirect(url_for('login'))

    google_email = user_info['email']
    google_name = user_info.get('name', google_email.split('@')[0])

    # Check if user exists
    user = User.query.filter_by(email=google_email).first()

    if not user:
        # Create new user. 
        # Since they are using Google, we generate a random dummy password
        # to satisfy the database 'NOT NULL' requirement.
        dummy_password = secrets.token_hex(16)
        new_user = User(
            username=google_name, 
            email=google_email, 
            password=generate_password_hash(dummy_password)
        )
        db.session.add(new_user)
        db.session.commit()
        login_user(new_user)
    else:
        # User exists, just log them in
        login_user(user)

    return redirect(url_for('dashboard'))

@app.route('/')
def index():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    return render_template('index.html')

@app.route('/dashboard')
@login_required
def dashboard():
    # Show only the surveys belonging to the logged-in user
    user_surveys = SurveyMetadata.query.filter_by(user_id=current_user.id).order_by(SurveyMetadata.created_at.desc()).all()
    return render_template('dashboard.html', surveys=user_surveys)

@app.route('/upload', methods=['POST'])
@login_required # <--- Only logged in users can upload
def upload_file():
    """
    Handle upload of a survey definition file (CSV or Excel).

    Flow:
        1. Verify that a file was actually submitted.
        2. Validate the extension (.csv, .xlsx, .xls).
        3. Generate a new UUID-based survey_id.
        4. Save the file to the uploads folder.
        5. Return a JSON payload containing:
           - message
           - survey_id
           - survey_url (a link to fill the survey)
    """
    if 'surveyFile' not in request.files:
        return jsonify({"error": "No file part"}), 400

    the_file = request.files['surveyFile']

    if the_file and the_file.filename != '' and the_file.filename.lower().endswith(('.csv', '.xlsx', '.xls')):
        original_extension = os.path.splitext(the_file.filename)[1]
        survey_uuid = str(uuid.uuid4())
        new_filename = survey_uuid + original_extension
        # Save file to disk
        save_path = os.path.join(UPLOAD_FOLDER, new_filename)
        the_file.save(save_path)

        # ★★★ SAVE METADATA TO DB (Link to User) ★★★
        new_survey_meta = SurveyMetadata(
            survey_uuid=survey_uuid,
            filename=new_filename,
            original_name=the_file.filename,
            user_id=current_user.id
        )
        db.session.add(new_survey_meta)
        db.session.commit()

        survey_url = url_for('show_survey', survey_id=survey_uuid, _external=True)
        
        # If request came from dashboard (form submit), redirect. If AJAX, return JSON.
        # Assuming simple form submit for now based on 'index.html' usually used
        return redirect(url_for('dashboard'))

    return jsonify({"error": "Invalid file format."}), 400

# -----------------------------------------------------------------------------
# Survey Logic (Viewing & Submitting - Public Access)
# -----------------------------------------------------------------------------

@app.route('/survey/<survey_id>')
def show_survey(survey_id):
    # Check DB first to verify it exists
    meta = SurveyMetadata.query.filter_by(survey_uuid=survey_id).first()
    if not meta:
        abort(404, description="Survey not found in database.")

    file_path = os.path.join(UPLOAD_FOLDER, meta.filename)
    
    if not os.path.exists(file_path):
        abort(404, description="Survey file missing from server.")

    try:
        if meta.filename.lower().endswith('.csv'):
            full_df = pd.read_csv(file_path, header=None)
        else:
            full_df = pd.read_excel(file_path, header=None)

        form_fields = []
        for col_index in full_df.columns:
            column_data = full_df[col_index].dropna().reset_index(drop=True)
            if len(column_data) < 2: continue

            field_label = str(column_data[0]).strip()
            field_type_codeword = str(column_data[1]).lower().strip()
            field_name = field_label.lower().replace(' ', '_').replace('.', '')
            
            field_info = {'name': field_name, 'label': field_label, 'type': field_type_codeword}

            if field_type_codeword == 'select':
                field_info['options'] = column_data.iloc[2:].unique().tolist()
            elif field_type_codeword not in ['date', 'checkbox', 'select', 'text']:
                field_info['type'] = 'text'

            form_fields.append(field_info)

        return render_template('survey.html', fields=form_fields, survey_id=survey_id)

    except Exception as e:
        print(f"Error: {e}")
        abort(500)


@app.route('/submit/<survey_id>', methods=['POST'])
def submit_survey(survey_id):
    """
    Save a single survey submission to the database.

    Author: Saksham (PostgreSQL integration)

    Expected Input:
        - JSON payload sent from the front-end.

    Behaviour:
        - Validate JSON content-type.
        - Normalize checkbox values ('on' -> 'Yes').
        - Serialize the result to JSON and store in the SurveyResponse table.
        - Roll back and log on failure; commit on success.
    """
    if not request.is_json:
        return jsonify({"error": "Expected JSON payload"}), 400

    data_from_form = request.get_json()

    # Basic normalization: convert checkbox 'on' to 'Yes'
    for key, value in list(data_from_form.items()):
        if value == 'on':
            data_from_form[key] = 'Yes'

    # Save response to DB
    response_json = json.dumps(data_from_form)
    new_response = SurveyResponse(survey_id=survey_id, response_data=response_json)

    try:
        db.session.add(new_response)
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        app.logger.exception("Failed to save survey response")
        return jsonify({"error": "Failed to save response"}), 500

    return jsonify({"message": "Data successfully saved to database!"}), 201


@app.route('/share_email', methods=['POST'])
@login_required
def share_by_email():
    data = request.get_json()
    # Check ownership (Optional but good practice)
    # meta = SurveyMetadata.query.filter_by(survey_uuid=data['survey_id'], user_id=current_user.id).first()
    # if not meta: return jsonify({"error": "Unauthorized"}), 403

    try:
        msg = Message("Survey Invitation", recipients=[data['email']])
        msg.body = f"Please complete this survey:\n{data['link']}\n\nThanks!"
        mail.send(msg)
        return jsonify({"message": "Email Sent"}), 200
    except:
        return jsonify({"error": "Email Failed"}), 500

# ----- DOWNLOAD FUNCTION FOR EXCEL EXPORT ----- AUTHOR SAMANT
# MODIFIED BY SAMANT TO PRESERVE THE OLD DATA IN THE NEWLY CREATED EXCELSHEET

@app.route('/download/<survey_id>')
def download_responses(survey_id):
  # 1. Verify Ownership
    meta = SurveyMetadata.query.filter_by(survey_uuid=survey_id, user_id=current_user.id).first()
    if not meta:
        return "You do not have permission to view this survey.", 403

    file_path = os.path.join(UPLOAD_FOLDER, meta.filename)
    if not os.path.exists(file_path): return "Template file lost.", 404

    # 2. Read Template
    try:
        if meta.filename.lower().endswith('.csv'):
            original_df = pd.read_csv(file_path, header=None)
        else:
            original_df = pd.read_excel(file_path, header=None, engine='openpyxl')
    except:
        return "Error reading template.", 500

    # 3. Analyze Structure (Find which columns are NOT dropdowns)
    # Anchors are columns that users MUST fill (Name, Date) or the App fills (Timestamp).
    # Dropdowns are NOT anchors because template option rows have text there.
    col_mapping = {}
    anchor_indices = []

    # Get Type Row (Row 1)
    if len(original_df) > 1:
        type_row = original_df.iloc[1]
    else:
        type_row = pd.Series([])

    for col_index in original_df.columns:
        # Build Mapping
        cell_value = original_df.iloc[0, col_index]
        if pd.isna(cell_value):
            continue
        
        field_label = str(cell_value).strip()
        internal_key = field_label.lower().replace(' ', '_').replace('.', '')
        col_mapping[internal_key] = col_index

        # LOGIC: Check if this column is an "Anchor"
        # Case A: It's a standard column defined in the template
        if col_index < len(type_row):
            type_val = str(type_row[col_index]).lower().strip()
            # If it's NOT a select box, it's a valid anchor (e.g. text, date)
            if type_val != 'select':
                anchor_indices.append(col_index)
        
        # Case B: It's an extra column (like "Submission Time")
        # This protects rows that have timestamps even if other fields are empty
        else:
            anchor_indices.append(col_index)

    # 4. Filter the Template
    # We want to keep Header (Row 0) and any Old Data.
    # We want to delete Row 1 (Type) and Option Rows (where non-select cols are empty).
    
    header_row = original_df.iloc[[0]]
    potential_data = original_df.iloc[2:]  # Skip Header and Type

    # Force empty strings to be None so dropna works
    potential_data = potential_data.replace(r'^\s*$', None, regex=True)

    if anchor_indices:
        # If a row has NO data in the text/date columns, assume it's just an Option row -> Delete it.
        valid_old_data = potential_data.dropna(subset=anchor_indices, how='all')
    else:
        # If the WHOLE survey is dropdowns, just keep rows with at least 2 values
        valid_old_data = potential_data.dropna(thresh=2)

    # Create the clean base sheet
    clean_base_df = pd.concat([header_row, valid_old_data], ignore_index=True)

    # 5. Fetch and Merge New Data
    responses = SurveyResponse.query.filter_by(survey_id=survey_id).all()
    new_rows = []
    
    if responses:
        for response in responses:
            try:
                data = json.loads(response.response_data)
                current_row = [None] * len(original_df.columns)
                
                for key, value in data.items():
                    if key in col_mapping:
                        target_col_index = col_mapping[key]
                        current_row[target_col_index] = value
                    else:
                        normalized_key = str(key).lower().replace(' ', '_').replace('.', '')
                        if normalized_key in col_mapping:
                            target_col_index = col_mapping[normalized_key]
                            current_row[target_col_index] = value

                # --- TIMEZONE FIX (UTC -> IST) ---
                # Add 5 hours 30 minutes to the stored UTC time
                utc_time = response.submission_time
                ist_time = utc_time + timedelta(hours=5, minutes=30)
                formatted_time = ist_time.strftime('%Y-%m-%d %I:%M %p')  # e.g. 2025-11-30 02:30 PM
                
                # Append to row (This aligns with the 'Response At' header we added)
                current_row.append(formatted_time)
                new_rows.append(current_row)
            except Exception as e:
                print(f"Skipping corrupt record: {e}")

    # Merge!
    if new_rows:
        new_df = pd.DataFrame(new_rows)
        combined_df = pd.concat([clean_base_df, new_df], ignore_index=True)
    else:
        combined_df = clean_base_df

    # 6. Save and Send
    excel_filename = f"responses_{survey_id}.xlsx"
    excel_file_path = os.path.join(RESPONSES_FOLDER, excel_filename)

    try:
        combined_df.to_excel(excel_file_path, index=False, header=False, engine='openpyxl')
        return send_from_directory(directory=RESPONSES_FOLDER, path=excel_filename, as_attachment=True)
    except Exception as e:
        return f"Error creating download: {e}", 500

# -----------------------------------------------------------------------------
# Delete Logic
# -----------------------------------------------------------------------------
@app.route('/delete/<survey_id>', methods=['POST'])
@login_required
def delete_survey(survey_id):
    # 1. Find the survey in the DB
    survey = SurveyMetadata.query.filter_by(survey_uuid=survey_id).first()

    # 2. Security Check: Does it exist? Does it belong to the current user?
    if not survey:
        flash("Survey not found.", "error")
        return redirect(url_for('dashboard'))
    
    if survey.user_id != current_user.id:
        flash("You do not have permission to delete this survey.", "error")
        return redirect(url_for('dashboard'))

    try:
        # 3. Delete the actual file from the 'uploads' folder
        file_path = os.path.join(UPLOAD_FOLDER, survey.filename)
        if os.path.exists(file_path):
            os.remove(file_path)

        # 4. Delete the generated response file (if it exists)
        response_file = os.path.join(RESPONSES_FOLDER, f"responses_{survey_id}.xlsx")
        if os.path.exists(response_file):
            os.remove(response_file)

        # 5. Delete all associated responses from the Database
        # (Cascade delete isn't set up in the model, so we do it manually)
        SurveyResponse.query.filter_by(survey_id=survey_id).delete()

        # 6. Delete the Metadata record
        db.session.delete(survey)
        db.session.commit()

        flash("Survey deleted successfully!", "success")
    
    except Exception as e:
        db.session.rollback()
        print(f"Error deleting survey: {e}")
        flash("An error occurred while deleting the survey.", "error")

    return redirect(url_for('dashboard'))


# -----------------------------------------------------------------------------
# App Entry Point (development only)
# -----------------------------------------------------------------------------

if __name__ == '__main__':
    
    # Ensure all database tables exist before the server starts.
    # For production, prefer Flask-Migrate/Alembic migrations instead.
    with app.app_context():
        db.create_all()

    # In production, run this app with a WSGI server (e.g., Gunicorn) and
    # set debug=False. Debug=True is convenient only during development.
    app.run(debug=True)

# Usage hint (added by Saksham):
# After activating the virtual environment, set the DATABASE_URL in your shell:
#   $env:DATABASE_URL = "postgresql+psycopg2://flask_user:password@localhost:5432/survey_db"
