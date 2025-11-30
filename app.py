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
#     
# Requirements (install in your virtual environment):
#   pip install psycopg2-binary flask flask-mail flask-sqlalchemy pandas openpyxl

import os
import uuid
import pandas as pd
from datetime import datetime, timedelta
import json
from flask import Flask, request, render_template, jsonify, send_from_directory, abort, url_for
from flask_mail import Mail, Message
from flask_sqlalchemy import SQLAlchemy
# ---- SECURE DATABASE CONFIGURATION ----Author: SAMANT
from urllib.parse import quote_plus


# -----------------------------------------------------------------------------
# Flask App Setup
# -----------------------------------------------------------------------------

app = Flask(__name__)

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

app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get(
    'DATABASE_URL',
    f'postgresql+psycopg2://flask_user:{encoded_password}@127.0.0.1/survey_db'
)
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

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

# Ensure all database tables exist on startup.
# For larger projects, Flask-Migrate/Alembic is preferred, but this is
# sufficient for this survey app in both local and Render deployments.
with app.app_context():
    db.create_all()

# -----------------------------------------------------------------------------
# Database Model
# -----------------------------------------------------------------------------

class SurveyResponse(db.Model):
    """
    Database model representing a single survey submission.

    Author: Saksham

    Fields:
        id (int):
            Primary key.
        survey_id (str):
            UUID string that identifies which uploaded survey template
            this response belongs to.
        response_data (str):
            JSON string containing key/value pairs of the submitted form.
        submission_time (datetime):
            UTC timestamp automatically set when the record is inserted.
    """
    id = db.Column(db.Integer, primary_key=True)
    survey_id = db.Column(db.String(36), index=True, nullable=False)  # UUID of the survey
    response_data = db.Column(db.Text, nullable=False)  # Store the form data as a JSON string
    submission_time = db.Column(db.DateTime, default=datetime.utcnow)

# -----------------------------------------------------------------------------
# Routes
# -----------------------------------------------------------------------------

@app.route('/')
def index():
    """
    Render the home page.

    The home page typically contains:
      - A form for uploading survey definition files.
      - Links or instructions for using the survey system.
    """
    return render_template('index.html')


@app.route('/upload', methods=['POST'])
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
        survey_id = str(uuid.uuid4())
        new_filename = survey_id + original_extension
        save_path = os.path.join(UPLOAD_FOLDER, new_filename)
        the_file.save(save_path)

        # Build an absolute URL for sharing with respondents.
        survey_url = url_for('show_survey', survey_id=survey_id, _external=True)

        return jsonify({"message": "File uploaded!", "survey_id": survey_id, "survey_url": survey_url})

    return jsonify({"error": "Upload failed. Please select a valid .csv or .xlsx file."}), 400


@app.route('/survey/<survey_id>')  # AUTHOR SAMANT
def show_survey(survey_id):
    """
    Display the dynamic survey form for a given survey_id.

    Behaviour:
        - Locate the uploaded file whose name starts with the survey_id.
        - Load it into a pandas DataFrame.
        - For each column:
            Row 0 -> field label (question text).
            Row 1 -> field type codeword ('text', 'date', 'checkbox', 'select', etc.).
            Remaining rows -> options (for 'select' fields).
        - Construct a list of field descriptors and send them to the template.
    """
    found_file = None

    # Find the file whose name is prefixed with the survey_id.
    for filename in os.listdir(UPLOAD_FOLDER):
        if filename.startswith(survey_id):
            found_file = filename
            break

    if not found_file:
        abort(404, description="Survey file not found.")

    file_path = os.path.join(UPLOAD_FOLDER, found_file)

    try:
        # Decide how to load the file based on extension.
        if found_file.lower().endswith('.csv'):
            full_df = pd.read_csv(file_path, header=None)
        elif found_file.lower().endswith(('.xlsx', '.xls')):
            full_df = pd.read_excel(file_path, header=None)
        else:
            abort(400, description="Unsupported file format.")

        form_fields = []

        # Each column represents a single form field.
        for col_index in full_df.columns:
            column_data = full_df[col_index].dropna().reset_index(drop=True)

            # Need at least two rows: label + type.
            if len(column_data) < 2:
                # Missing label/type rows -> skip this column.
                print(f"Skipping column {col_index}: missing Label (Row 1) or Type (Row 2).")
                continue

            field_label = str(column_data[0]).strip()
            field_type_codeword = str(column_data[1]).lower().strip()

            # Field name used in HTML form and JSON payload.
            field_name = field_label.lower().replace(' ', '_').replace('.', '')
            field_info = {'name': field_name, 'label': field_label}

            codeword = field_type_codeword
            field_info['type'] = codeword

            # For select fields, all remaining rows are options.
            if codeword == 'select':
                field_options = column_data.iloc[2:].unique().tolist()
                field_info['options'] = field_options
            # For unknown types, fallback to simple text input.
            elif codeword not in ['date', 'checkbox', 'select', 'text']:
                field_info['type'] = 'text'

            form_fields.append(field_info)

        return render_template('survey.html', fields=form_fields, survey_id=survey_id)

    except Exception as e:
        # Log the error server-side so that bad template files can be debugged.
        print(f"!! ERROR reading file for survey {survey_id} !! {e}")
        abort(500, description="Could not process file. Ensure structure is correct.")


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
def share_by_email():
    """
    Send a survey link to a respondent via email.

    Expected JSON payload:
        {
            "email": "<recipient email address>",
            "link": "<full survey URL>"
        }
    """
    if not request.is_json:
        return jsonify({"error": "Expected JSON payload"}), 400

    data = request.get_json()
    recipient_email = data.get('email')
    survey_link = data.get('link')

    if not recipient_email or not survey_link:
        return jsonify({"error": "Email and link are required."}), 400

    try:
        msg = Message(
            subject="You're Invited to Take a Survey!",
            recipients=[recipient_email]
        )
        msg.body = (
            "Hello,\n\n"
            "Please complete this survey by clicking the following link:\n"
            f"{survey_link}\n\n"
            "Thank you!"
        )
        mail.send(msg)

        return jsonify({"message": f"Survey successfully sent to {recipient_email}"}), 200

    except Exception:
        app.logger.exception("EMAIL SENDING ERROR")
        return jsonify({"error": "Failed to send email. Check your credentials."}), 500

# ----- DOWNLOAD FUNCTION FOR EXCEL EXPORT ----- AUTHOR SAMANT
# MODIFIED BY SAMANT TO PRESERVE THE OLD DATA IN THE NEWLY CREATED EXCELSHEET

@app.route('/download/<survey_id>')
def download_responses(survey_id):
    # 1. Find Original File
    found_file = None
    if not os.path.exists(UPLOAD_FOLDER):
        return "Uploads folder missing.", 404

    for filename in os.listdir(UPLOAD_FOLDER):
        if filename.startswith(survey_id):
            found_file = filename
            break     

    if not found_file:
        return "CRITICAL ERROR: Original template not found.", 404

    file_path = os.path.join(UPLOAD_FOLDER, found_file)

    # 2. Read File
    try:
        if found_file.lower().endswith(('.xlsx', '.xls')):
            original_df = pd.read_excel(file_path, header=None, engine='openpyxl')
        else:
            original_df = pd.read_csv(file_path, header=None)
    except Exception as e:
        return f"Error reading file: {e}", 500

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
