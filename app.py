# My first Flask survey app

# import all the stuff I need
import os
import uuid
import pandas as pd
from datetime import datetime # Added by Saksham for timestamping DB records
import json # Added by Saksham for handling JSON data in the DB
from flask import Flask, request, render_template, jsonify, send_from_directory, abort
from flask_mail import Mail, Message
# ★★★★★ DATABASE IMPORTS ★★★★★
from flask_sqlalchemy import SQLAlchemy 
# Author: Saksham (Database Integration)

# make a new flask app
app = Flask(__name__)

# --- App Setup ---
UPLOAD_FOLDER = 'uploads'
RESPONSES_FOLDER = 'responses' # Used for temporary Excel export files

if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)
if not os.path.exists(RESPONSES_FOLDER):
    os.makedirs(RESPONSES_FOLDER)

# ★★★★★ NEW DATABASE CONFIGURATION SECTION ★★★★★
# Configure SQLite database (responses.db file will be created in the project root)
app.config['SQLALCHEMY_DATABASE_URI'] = 'mysql+pymysql://flask_user:your_secure_password@localhost/survey_db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

# ★★★★★ EMAIL CONFIGURATION SECTION (unchanged) ★★★★★
app.config['MAIL_SERVER'] = 'smtp.gmail.com'
app.config['MAIL_PORT'] = 587
app.config['MAIL_USE_TLS'] = True
app.config['MAIL_USERNAME'] = 'articlestore701@gmail.com' 
app.config['MAIL_PASSWORD'] = 'ldtq dvpr kpft yvvz'
app.config['MAIL_DEFAULT_SENDER'] = 'articlestore701@gmail.com'

# Initialize the Mail object
mail = Mail(app)
# --- End Setup ---


# ★★★★★ NEW DATABASE MODEL ★★★★★
class SurveyResponse(db.Model):
    """Stores each completed survey response."""
    # Model created by Saksham to store data persistently
    id = db.Column(db.Integer, primary_key=True)
    survey_id = db.Column(db.String(36), nullable=False) # UUID of the survey
    response_data = db.Column(db.Text, nullable=False) # Store the form data as a JSON string
    submission_time = db.Column(db.DateTime, default=datetime.utcnow)


@app.route('/')
def index():
    return render_template('index.html')


@app.route('/upload', methods=['POST'])
def upload_file():
    # This function is unchanged
    the_file = request.files['surveyFile']
    if the_file and the_file.filename != '' and the_file.filename.endswith(('.csv', '.xlsx', '.xls')):
        original_extension = os.path.splitext(the_file.filename)[1]
        survey_id = str(uuid.uuid4())
        new_filename = survey_id + original_extension
        save_path = os.path.join(UPLOAD_FOLDER, new_filename)
        the_file.save(save_path)
        survey_url = request.host_url + "survey/" + survey_id
        return jsonify({"message": "File uploaded!", "survey_id": survey_id, "survey_url": survey_url})
    return jsonify({"error": "Upload failed. Please select a valid .csv or .xlsx file."}), 400


@app.route('/survey/<survey_id>')
def show_survey(survey_id):
    # This function is unchanged (Reads Excel/CSV to build form fields)
    found_file = None
    for filename in os.listdir(UPLOAD_FOLDER):
        if filename.startswith(survey_id):
            found_file = filename
            break
    if not found_file:
        abort(404, description="Survey file not found.")
    file_path = os.path.join(UPLOAD_FOLDER, found_file)
    try:
        if found_file.endswith(('.csv', '.CSV')):
            full_df = pd.read_csv(file_path, header=None)
        elif found_file.endswith(('.xlsx', '.XLSX', '.xls', '.XLS')):
            full_df = pd.read_excel(file_path, header=None)
        else:
            abort(400, description="Unsupported file format.")
            
        form_fields = []
        for col_index in full_df.columns:
            column_data = full_df[col_index].dropna().reset_index(drop=True)
            if len(column_data) < 2:
                print(f"Skipping column {col_index}: missing Label (Row 1) or Type (Row 2).")
                continue

            field_label = str(column_data[0]).strip()
            field_type_codeword = str(column_data[1]).lower().strip()
            field_name = field_label.lower().replace(' ', '_').replace('.', '')
            field_info = {'name': field_name, 'label': field_label}
            
            codeword = field_type_codeword
            field_info['type'] = codeword

            if codeword == 'select':
                field_options = column_data.iloc[2:].unique().tolist()
                field_info['options'] = field_options
            
            elif codeword not in ['date', 'checkbox', 'select', 'text']:
                field_info['type'] = 'text'

            form_fields.append(field_info)
        
        return render_template('survey.html', fields=form_fields, survey_id=survey_id)
        
    except Exception as e:
        print(f"!! ERROR reading file for survey {survey_id} !! {e}")
        abort(500, description="Could not process file. Ensure structure is correct.")


@app.route('/submit/<survey_id>', methods=['POST'])
def submit_survey(survey_id):
    # Logic modified by Saksham to save data to database instead of CSV
    data_from_form = request.json
    
    # Pre-process checkbox values for storage consistency
    for key, value in data_from_form.items():
        if value == 'on':
            data_from_form[key] = 'Yes'
    
    # ★★★★★ DATABASE: Save Response ★★★★★
    # 1. Convert form data to a JSON string for storage
    response_json = json.dumps(data_from_form)
    
    # 2. Create and commit the new record to the SQLite database
    new_response = SurveyResponse(survey_id=survey_id, response_data=response_json)
    db.session.add(new_response)
    db.session.commit()
    
    return jsonify({"message": "Data successfully saved to database!"})


@app.route('/share_email', methods=['POST'])
def share_by_email():
    # This function is unchanged
    data = request.json
    recipient_email = data.get('email')
    survey_link = data.get('link')

    if not recipient_email or not survey_link:
        return jsonify({"error": "Email and link are required."}), 400

    try:
        msg = Message(
            subject="You're Invited to Take a Survey!",
            recipients=[recipient_email]
        )
        
        msg.body = f"Hello,\n\nPlease complete this survey by clicking the following link:\n{survey_link}\n\nThank you!"
        mail.send(msg)
        return jsonify({"message": f"Survey successfully sent to {recipient_email}"})

    except Exception as e:
        print("!! EMAIL SENDING ERROR !!")
        print(e)
        return jsonify({"error": "Failed to send email. Check your credentials in app.py."}), 500


# ★★★★★ NEW/MODIFIED DOWNLOAD FUNCTION FOR EXCEL EXPORT ★★★★★
@app.route('/download/<survey_id>')
def download_responses(survey_id):
    # Function rewritten by Saksham for database retrieval and Excel export via Pandas
    
    # 1. Fetch all responses for the specific survey_id from the database
    responses = SurveyResponse.query.filter_by(survey_id=survey_id).all()
    
    if not responses:
        return "No responses found to download for this survey.", 404

    # 2. Prepare data for Pandas DataFrame
    response_list = []
    for response in responses:
        # Load the JSON string back into a Python dictionary
        data = json.loads(response.response_data)
        # Add submission time from the DB for context
        data['submission_time'] = response.submission_time.strftime('%Y-%m-%d %H:%M:%S')
        response_list.append(data)

    # 3. Create a clean Pandas DataFrame from all responses
    # Pandas automatically aligns columns/headers from the dictionary keys
    df = pd.DataFrame(response_list)
    
    # 4. Define paths for the temporary Excel file
    excel_filename = f"responses_{survey_id}.xlsx"
    excel_file_path = os.path.join(RESPONSES_FOLDER, excel_filename)
    
    # 5. Use Pandas to write the full DataFrame to an Excel file
    # Requires 'openpyxl' installed: pip install openpyxl
    try:
        df.to_excel(excel_file_path, index=False, engine='openpyxl')
    except ImportError:
        return "Error: openpyxl library is required for Excel export. Please run 'pip install openpyxl'.", 500

    # 6. Send the dynamically created file to the user
    return send_from_directory(
        directory=RESPONSES_FOLDER,
        path=excel_filename,
        as_attachment=True
    )

# this line starts the web server
if __name__ == '__main__':
    # Logic added by Saksham for DB initialization
    with app.app_context():
        db.create_all()
    app.run(debug=True)
