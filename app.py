# My first Flask survey app

# import all the stuff I need
import os
import uuid
import pandas as pd
from flask import Flask, request, render_template, jsonify, send_from_directory, abort
# ★★★★★ NEW IMPORT ★★★★★
from flask_mail import Mail, Message

# make a new flask app
app = Flask(__name__)

# --- App Setup ---
UPLOAD_FOLDER = 'uploads'
RESPONSES_FOLDER = 'responses'

if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)
if not os.path.exists(RESPONSES_FOLDER):
    os.makedirs(RESPONSES_FOLDER)

# ★★★★★ NEW EMAIL CONFIGURATION SECTION ★★★★★
# Replace with your own Gmail address and App Password
app.config['MAIL_SERVER'] = 'smtp.gmail.com'
app.config['MAIL_PORT'] = 587
app.config['MAIL_USE_TLS'] = True
app.config['MAIL_USERNAME'] = 'articlestore701@gmail.com'  # <-- IMPORTANT: Your email
app.config['MAIL_PASSWORD'] = 'ldtq dvpr kpft yvvz' # <-- IMPORTANT: Your App Password
app.config['MAIL_DEFAULT_SENDER'] = 'articlestore701@gmail.com' # <-- IMPORTANT: Your email

# Initialize the Mail object
mail = Mail(app)
# --- End Setup ---


@app.route('/')
def index():
    # just return the main html page
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
    # This function is unchanged
    found_file = None
    for filename in os.listdir(UPLOAD_FOLDER):
        if filename.startswith(survey_id):
            found_file = filename
            break
    if not found_file:
        abort(404, description="Survey file not found.")
    file_path = os.path.join(UPLOAD_FOLDER, found_file)
    try:
         # 1. Read the file with no headers (header=None) to get all cells as data.
        if found_file.endswith(('.csv', '.CSV')):
            full_df = pd.read_csv(file_path, header=None)
        elif found_file.endswith(('.xlsx', '.XLSX', '.xls', '.XLS')):
            full_df = pd.read_excel(file_path, header=None)
        else:
            abort(400, description="Unsupported file format.")
        
        form_fields = []

        # 2. Iterate through columns to process each field definition
        for col_index in full_df.columns:
            
            # Get data for the current column, drop NaNs, and reset index
            column_data = full_df[col_index].dropna().reset_index(drop=True)
            
            # Ensure there is enough data for at least a Label and a Type (2 rows)
            if len(column_data) < 2:
                print(f"Skipping column {col_index}: missing Label (Row 1) or Type (Row 2).")
                continue

            # 3. Extract the definition from the top of the column
            field_label = str(column_data[0]).strip()  # Row 1 (index 0) is the Label
            field_type_codeword = str(column_data[1]).lower().strip() # Row 2 (index 1) is the Type
            
            # 4. Create the field dictionary
            # Create a clean name for internal form use (e.g., 'Full Name' -> 'full_name')
            field_name = field_label.lower().replace(' ', '_').replace('.', '')
            field_info = {'name': field_name, 'label': field_label}
            
            codeword = field_type_codeword
            field_info['type'] = codeword

            # 5. Logic for 'select' (dropdown) fields
            if codeword == 'select':
                # Data for options starts from Row 3 (index 2)
                # Use unique values in the rest of the column for options
                field_options = column_data.iloc[2:].unique().tolist()
                field_info['options'] = field_options
            
            # Optional: Fallback for unknown types
            elif codeword not in ['date', 'checkbox', 'select', 'text']:
                 field_info['type'] = 'text'

            form_fields.append(field_info)
        
        return render_template('survey.html', fields=form_fields, survey_id=survey_id)
        
    except Exception as e:
        print(f"!! ERROR reading file for survey {survey_id} !! {e}")
        abort(500, description="Could not process file. Ensure each column has the Field Label in Row 1 and the Type Codeword in Row 2.")
        
       


@app.route('/submit/<survey_id>', methods=['POST'])
def submit_survey(survey_id):
    # This function is unchanged
    data_from_form = request.json
    csv_filename = survey_id + ".csv"
    csv_file_path = os.path.join(RESPONSES_FOLDER, csv_filename)
    for key, value in data_from_form.items():
        if value == 'on':
            data_from_form[key] = 'Yes'
    new_row_df = pd.DataFrame([data_from_form])
    if os.path.exists(csv_file_path):
        new_row_df.to_csv(csv_file_path, mode='a', header=False, index=False)
    else:
        new_row_df.to_csv(csv_file_path, mode='w', header=True, index=False)
    return jsonify({"message": "Data saved!"})

# ★★★★★ THIS IS THE UPDATED EMAIL FUNCTION ★★★★★
@app.route('/share_email', methods=['POST'])
def share_by_email():
    # get the data the javascript sent
    data = request.json
    recipient_email = data.get('email')
    survey_link = data.get('link')

    # check if we got an email address and link
    if not recipient_email or not survey_link:
        return jsonify({"error": "Email and link are required."}), 400

    # try to send the email
    try:
        # create the email message
        msg = Message(
            subject="You're Invited to Take a Survey!",
            recipients=[recipient_email] # the person we are sending it to
        )
        
        # this is the body of the email
        msg.body = f"Hello,\n\nPlease complete this survey by clicking the following link:\n{survey_link}\n\nThank you!"
        
        # send the message!
        mail.send(msg)
        
        # tell the javascript it worked
        return jsonify({"message": f"Survey successfully sent to {recipient_email}"})

    except Exception as e:
        # if something went wrong, print the error and tell the user
        print("!! EMAIL SENDING ERROR !!")
        print(e)
        return jsonify({"error": "Failed to send email. Check your credentials in app.py."}), 500


@app.route('/download/<survey_id>')
def download_responses(survey_id):
    # This function is unchanged
    csv_file = survey_id + ".csv"
    if not os.path.exists(os.path.join(RESPONSES_FOLDER, csv_file)):
        return "No responses found to download for this survey."
    return send_from_directory(
        directory=RESPONSES_FOLDER,
        path=csv_file,
        as_attachment=True
    )

# this line starts the web server
if __name__ == '__main__':
    app.run(debug=True)
