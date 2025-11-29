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
from datetime import datetime
import json
from flask import Flask, request, render_template, jsonify, send_from_directory, abort, url_for
from flask_mail import Mail, Message
from flask_sqlalchemy import SQLAlchemy

# -----------------------------------------------------------------------------
# Flask App Setup
# -----------------------------------------------------------------------------

app = Flask(__name__)

# Folder where uploaded survey templates will be stored.
UPLOAD_FOLDER = 'uploads'

# Folder where generated response Excel files will be stored.
RESPONSES_FOLDER = 'responses'  # Used for temporary Excel export files

# Ensure folders exist (development friendly).
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(RESPONSES_FOLDER, exist_ok=True)

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
    'postgresql+psycopg2://flask_user:your_secure_password@localhost/survey_db'
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
app.config['MAIL_USERNAME'] = os.environ.get('MAIL_USERNAME', 'articlestore701@gmail.com')
app.config['MAIL_PASSWORD'] = os.environ.get('MAIL_PASSWORD', 'ldtq dvpr kpft yvvz')
app.config['MAIL_DEFAULT_SENDER'] = os.environ.get('MAIL_DEFAULT_SENDER', app.config['MAIL_USERNAME'])

mail = Mail(app)

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


@app.route('/survey/<survey_id>')
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


@app.route('/download/<survey_id>')
def download_responses(survey_id):
    """
    Export all stored responses for a survey as an Excel file.

    Author: Saksham (rewrote CSV approach to DB + Excel)

    Steps:
        1. Query all SurveyResponse entries for the given survey_id.
        2. Convert JSON string data back to dicts.
        3. Add a formatted submission_time for each row.
        4. Build a pandas DataFrame from all responses.
        5. Write it to an .xlsx file using openpyxl.
        6. Send the file as a download to the client.
    """
    # Fetch responses for the survey
    responses = SurveyResponse.query.filter_by(survey_id=survey_id).all()
    if not responses:
        return "No responses found to download for this survey.", 404

    response_list = []
    for response in responses:
        data = json.loads(response.response_data)
        data['submission_time'] = response.submission_time.strftime('%Y-%m-%d %H:%M:%S')
        response_list.append(data)

    df = pd.DataFrame(response_list)
    excel_filename = f"responses_{survey_id}.xlsx"
    excel_file_path = os.path.join(RESPONSES_FOLDER, excel_filename)

    try:
        df.to_excel(excel_file_path, index=False, engine='openpyxl')
    except ImportError:
        # openpyxl is required to write Excel files from pandas.
        return (
            "Error: openpyxl library is required for Excel export. "
            "Please run 'pip install openpyxl'."
        ), 500
    except Exception:
        app.logger.exception("Failed to write Excel file")
        return "Error generating Excel file", 500

    return send_from_directory(
        directory=RESPONSES_FOLDER,
        path=excel_filename,
        as_attachment=True
    )


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

 
