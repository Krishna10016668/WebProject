# app.py

import os
import uuid
import pandas as pd
from flask import Flask, request, render_template, jsonify, send_from_directory, abort

# Initialize the Flask application
app = Flask(__name__)

# --- CONFIGURATION ---
# Define paths for storing uploaded survey definitions and collected responses.
# It's good practice to use absolute paths to avoid issues.
UPLOAD_FOLDER = os.path.join(os.getcwd(), 'uploads')
RESPONSES_FOLDER = os.path.join(os.getcwd(), 'responses')
# Create these directories if they don't exist
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(RESPONSES_FOLDER, exist_ok=True)

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['RESPONSES_FOLDER'] = RESPONSES_FOLDER
# --- END CONFIGURATION ---


# --- ROUTES ---

@app.route('/')
def index():
    """
    Serves the main admin page (index.html).
    This is the entry point for creating a new survey.
    """
    return render_template('index.html')

@app.route('/upload', methods=['POST'])
def upload_file():
    """
    Handles the Excel file upload from the admin page.
    It saves the file and generates a unique ID for the new survey.
    """
    # Check if a file was sent in the request
    if 'surveyFile' not in request.files:
        return jsonify({"error": "No file part in the request"}), 400
    
    file = request.files['surveyFile']
    
    # Check if the user selected a file
    if file.filename == '':
        return jsonify({"error": "No file selected"}), 400
        
    if file and file.filename.endswith(('.xlsx', '.xls')):
        # Generate a unique ID for the survey to prevent filename conflicts
        survey_id = str(uuid.uuid4())
        # Save the uploaded Excel file (e.g., 'uploads/some-unique-id.xlsx')
        filename = f"{survey_id}.xlsx"
        file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(file_path)

        # For simplicity, we assume the survey is now 'published'.
        # We generate a unique URL for others to take the survey.
        survey_url = request.host_url + f"survey/{survey_id}"

        # Return the unique ID and the full URL to the frontend
        return jsonify({
            "message": "File uploaded successfully!",
            "survey_id": survey_id,
            "survey_url": survey_url
        })
        
    return jsonify({"error": "Invalid file type. Please upload an Excel file."}), 400

@app.route('/survey/<survey_id>')
def show_survey(survey_id):
    """
    Displays the survey form to a user.
    The <survey_id> in the URL tells us which survey to show.
    
    NOTE: In a real app, you would read the Excel file corresponding to survey_id 
    and dynamically generate the form questions here. For this example, we serve
    a static 'survey.html'.
    """
    # Check if the survey definition file exists before serving the page
    survey_file_path = os.path.join(app.config['UPLOAD_FOLDER'], f"{survey_id}.xlsx")
    if not os.path.exists(survey_file_path):
        abort(404, description="Survey not found.") # Show a 404 error if the ID is invalid
        
    return render_template('survey.html', survey_id=survey_id)


@app.route('/submit/<survey_id>', methods=['POST'])
def submit_survey(survey_id):
    """
    Receives form submission data from a user, saves it to a CSV file.
    Each survey ID will have its own CSV file for responses.
    """
    # Get the JSON data sent from the frontend
    response_data = request.json
    
    # Define the path for the response file (e.g., 'responses/some-unique-id.csv')
    response_file_path = os.path.join(app.config['RESPONSES_FOLDER'], f"{survey_id}.csv")
    
    # Create a pandas DataFrame from the incoming JSON data
    new_response_df = pd.DataFrame([response_data])
    
    # Check if the response file already exists
    if os.path.exists(response_file_path):
        # If it exists, append the new data without writing the header
        new_response_df.to_csv(response_file_path, mode='a', header=False, index=False)
    else:
        # If it's the first response, create the file and write the header
        new_response_df.to_csv(response_file_path, mode='w', header=True, index=False)
        
    return jsonify({"message": "Survey submitted successfully!"})


@app.route('/download/<survey_id>')
def download_responses(survey_id):
    """
    Allows the admin to download the collected responses for a specific survey.
    It sends the corresponding CSV file to the user's browser.
    """
    response_file_path = os.path.join(app.config['RESPONSES_FOLDER'], f"{survey_id}.csv")

    # Check if any responses have been recorded for this survey
    if not os.path.exists(response_file_path):
        abort(404, description="No responses found for this survey.")

    # Send the file for download
    return send_from_directory(
        directory=app.config['RESPONSES_FOLDER'],
        path=f"{survey_id}.csv",
        as_attachment=True,
        download_name=f"survey_{survey_id}_responses.csv" # The name the user will see
    )

# This is a placeholder for a real email sending function
@app.route('/share_email', methods=['POST'])
def share_by_email():
    """
    A placeholder endpoint for the "Share via email" feature.
    In a real application, you would integrate a service like SendGrid or Flask-Mail here.
    """
    data = request.json
    email = data.get('email')
    link = data.get('link')

    if not email or not link:
        return jsonify({"error": "Email and link are required."}), 400

    # --- REAL EMAIL LOGIC WOULD GO HERE ---
    # Example:
    # from flask_mail import Message, Mail
    # mail = Mail(app)
    # msg = Message("Please take our survey!", recipients=[email])
    # msg.body = f"You have been invited to take a survey. Please click here: {link}"
    # mail.send(msg)
    # ----------------------------------------

    print(f"--- SIMULATING EMAIL ---")
    print(f"TO: {email}")
    print(f"LINK: {link}")
    print(f"------------------------")
    
    return jsonify({"message": f"Survey link sent to {email}"})


# This allows you to run the app by executing "python app.py"
if __name__ == '__main__':
    app.run(debug=True) # debug=True allows for auto-reloading during development