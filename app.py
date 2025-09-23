# app.py

import os
import uuid
import pandas as pd
import re
from flask import Flask, request, render_template, jsonify, send_from_directory, abort

# Initialize the Flask application
app = Flask(__name__)

# --- CONFIGURATION ---
UPLOAD_FOLDER = os.path.join(os.getcwd(), 'uploads')
RESPONSES_FOLDER = os.path.join(os.getcwd(), 'responses')
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(RESPONSES_FOLDER, exist_ok=True)

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['RESPONSES_FOLDER'] = RESPONSES_FOLDER
# --- END CONFIGURATION ---


# --- ROUTES ---

@app.route('/')
def index():
    """Serves the main admin page (index.html)."""
    return render_template('index.html')


@app.route('/upload', methods=['POST'])
def upload_file():
    """Handles the Excel file upload and generates a unique survey ID."""
    if 'surveyFile' not in request.files:
        return jsonify({"error": "No file part in the request"}), 400
    
    file = request.files['surveyFile']
    
    if file.filename == '':
        return jsonify({"error": "No file selected"}), 400
        
    if file and file.filename.endswith(('.xlsx', '.xls')):
        survey_id = str(uuid.uuid4())
        filename = f"{survey_id}.xlsx"
        file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(file_path)

        survey_url = request.host_url + f"survey/{survey_id}"

        return jsonify({
            "message": "File uploaded successfully!",
            "survey_id": survey_id,
            "survey_url": survey_url
        })
        
    return jsonify({"error": "Invalid file type. Please upload an Excel file."}), 400


@app.route('/survey/<survey_id>')
def show_survey(survey_id):
    """
    ★★★★★ THIS IS THE REDESIGNED DYNAMIC SECTION ★★★★★
    Generates a survey form from ANY Excel file's column headers.
    """
    survey_file_path = os.path.join(app.config['UPLOAD_FOLDER'], f"{survey_id}.xlsx")
    
    if not os.path.exists(survey_file_path):
        abort(404, description="Survey not found.")

    try:
        # Read the excel file
        df = pd.read_excel(survey_file_path)
        
        # Get the list of column headers from the file
        headers = df.columns.tolist()
        
        fields = []
        for header in headers:
            # The original header is the question label the user sees
            label = str(header)
            
            # Create a safe, programmatic name for the HTML input field.
            # Example: "Full Name" -> "full_name"
            # 1. Convert to lowercase
            # 2. Replace spaces and other non-alphanumeric chars with an underscore
            # 3. Remove any trailing underscores
            name = re.sub(r'[^a-z0-9]+', '_', label.lower()).strip('_')

            # We only need the name and label for our new dynamic form
            fields.append({'name': name, 'label': label})
            
        # Pass the list of fields to the survey template
        return render_template('survey.html', survey_id=survey_id, fields=fields)

    except Exception as e:
        # Catch any errors during file processing
        print(f"Error processing Excel file: {e}")
        abort(500, description="There was an error processing the survey file.")


@app.route('/submit/<survey_id>', methods=['POST'])
def submit_survey(survey_id):
    """Receives form submission data and saves it to a CSV file."""
    response_data = request.json
    response_file_path = os.path.join(app.config['RESPONSES_FOLDER'], f"{survey_id}.csv")
    new_response_df = pd.DataFrame([response_data])
    
    if os.path.exists(response_file_path):
        new_response_df.to_csv(response_file_path, mode='a', header=False, index=False)
    else:
        new_response_df.to_csv(response_file_path, mode='w', header=True, index=False)
        
    return jsonify({"message": "Survey submitted successfully!"})


@app.route('/download/<survey_id>')
def download_responses(survey_id):
    """Allows the admin to download the collected responses for a survey."""
    response_file_path = os.path.join(app.config['RESPONSES_FOLDER'], f"{survey_id}.csv")

    if not os.path.exists(response_file_path):
        abort(404, description="No responses found for this survey.")

    return send_from_directory(
        directory=app.config['RESPONSES_FOLDER'],
        path=f"{survey_id}.csv",
        as_attachment=True,
        download_name=f"survey_{survey_id}_responses.csv"
    )

# Other routes (like share_email) are unchanged...

if __name__ == '__main__':
    app.run(debug=True)
