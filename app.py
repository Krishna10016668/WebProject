# My first Flask survey app

# Import the things we need from Flask and other libraries
import os
import uuid
import pandas as pd
from flask import Flask, request, render_template, jsonify, send_from_directory, abort

# Create the Flask app
app = Flask(__name__)

# --- App Setup ---
# Define the folders where we will save files
UPLOAD_FOLDER = 'uploads'
RESPONSES_FOLDER = 'responses'

# Create the folders if they don't already exist
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)
if not os.path.exists(RESPONSES_FOLDER):
    os.makedirs(RESPONSES_FOLDER)
# --- End Setup ---


# This is the main page of our website
@app.route('/')
def index():
    # Just show the index.html file
    return render_template('index.html')

# This handles the file upload
@app.route('/upload', methods=['POST'])
def upload_file():
    # Check if a file was actually sent
    if 'surveyFile' in request.files:
        the_file = request.files['surveyFile']

        # Make sure the filename is not empty
        if the_file.filename != '':
            # Create a new unique ID for the survey
            survey_id = str(uuid.uuid4())
            new_filename = f"{survey_id}.xlsx"
            
            # Figure out where to save it
            save_path = os.path.join(UPLOAD_FOLDER, new_filename)
            the_file.save(save_path)

            # Create the full URL for the new survey
            survey_url = request.host_url + f"survey/{survey_id}"

            # Send a success message back to the javascript
            return jsonify({
                "message": "File uploaded!",
                "survey_id": survey_id,
                "survey_url": survey_url
            })
    
    # If something went wrong, send an error
    return jsonify({"error": "Something went wrong during upload"}), 400

# This function shows the survey form to a user
@app.route('/survey/<survey_id>')
def show_survey(survey_id):
    # Find the path to the excel file for this survey
    file_path = os.path.join(UPLOAD_FOLDER, f"{survey_id}.xlsx")

    # Try to read the file and create the form
    try:
        # Read the excel file into pandas
        df = pd.read_excel(file_path)
        
        # Get the column headers from the file
        column_headers = df.columns.tolist()
        
        # This will hold the list of fields for our form
        form_fields = []

        # Loop through each header we found in the file
        for header in column_headers:
            
            # The 'label' is the original header name
            field_label = header
            
            # The 'name' needs to be simple for HTML.
            # So we make it lowercase and replace spaces with underscores.
            field_name = header.lower().replace(' ', '_')
            
            # Create a dictionary for this field
            field_info = {
                'name': field_name, 
                'label': field_label
            }
            # Add the dictionary to our list of fields
            form_fields.append(field_info)
            
        # Now, render the survey.html template and give it the list of fields
        return render_template('survey.html', survey_id=survey_id, fields=form_fields)

    except Exception as e:
        # If anything goes wrong, print the error and show an error page
        print("There was an error reading the excel file:")
        print(e)
        abort(500, description="Could not process the survey file.")

# This function saves the data when a user submits the form
@app.route('/submit/<survey_id>', methods=['POST'])
def submit_survey(survey_id):
    # Get the data that the javascript sent to us
    data_from_form = request.json
    
    # Figure out the name of the CSV file for saving responses
    csv_filename = f"{survey_id}.csv"
    csv_file_path = os.path.join(RESPONSES_FOLDER, csv_filename)
    
    # Put the new data into a pandas DataFrame
    new_row_df = pd.DataFrame([data_from_form])
    
    # Check if the CSV file already exists
    if os.path.exists(csv_file_path):
        # If it exists, just add the new row to the end
        new_row_df.to_csv(csv_file_path, mode='a', header=False, index=False)
    else:
        # If it's a new file, create it and add the headers
        new_row_df.to_csv(csv_file_path, mode='w', header=True, index=False)
        
    return jsonify({"message": "Data saved!"})


# This function lets the admin download the responses
@app.route('/download/<survey_id>')
def download_responses(survey_id):
    # Find the path to the responses CSV file
    file_to_download_path = os.path.join(RESPONSES_FOLDER, f"{survey_id}.csv")

    # If the file doesn't exist, show an error
    if not os.path.exists(file_to_download_path):
        abort(404, description="No responses found to download.")

    # Send the file to the user's browser
    return send_from_directory(
        directory=RESPONSES_FOLDER,
        path=f"{survey_id}.csv",
        as_attachment=True
    )


# This makes the app run when you type "python app.py" in the terminal
if __name__ == '__main__':
    app.run(debug=True)
