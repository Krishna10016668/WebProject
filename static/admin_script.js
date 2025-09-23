// static/admin_script.js

document.addEventListener('DOMContentLoaded', () => {
    // --- ELEMENT SELECTORS ---
    const uploadScreen = document.getElementById('upload-screen');
    const publishedScreen = document.getElementById('published-screen');
    const uploadBox = document.getElementById('upload-box');
    const fileInput = document.getElementById('file-input');

    const copyButton = document.querySelector('.copy-button');
    const emailButton = document.querySelector('.email-button');
    const downloadButton = document.querySelector('.download-button');

    const shareLinkInput = document.getElementById('share-link-input');
    const shareEmailInput = document.getElementById('share-email-input');

    const successModal = document.getElementById('successModal');
    const modalTitle = document.getElementById('modal-title');
    const modalMessage = document.getElementById('modal-message');
    const closeModalButton = document.getElementById('closeModal');

    // --- STATE ---
    // We store the survey_id globally in this script once we get it from the backend
    let currentSurveyId = null;

    // --- MODAL FUNCTIONS ---
    const showModal = (title, message) => {
        modalTitle.textContent = title;
        modalMessage.textContent = message;
        successModal.classList.remove('translate-x-full', 'opacity-0');
    };

    const hideModal = () => {
        successModal.classList.add('translate-x-full', 'opacity-0');
    };

    closeModalButton.addEventListener('click', hideModal);

    // --- EVENT LISTENERS ---

    // 1. UPLOAD LOGIC
    // When the user clicks the "Upload Excel Sheet" box, we trigger the hidden file input
    uploadBox.addEventListener('click', () => {
        fileInput.click();
    });

    // When the user selects a file in the dialog, this event is fired
    fileInput.addEventListener('change', async (event) => {
        const file = event.target.files[0];
        if (!file) {
            return; // No file selected
        }

        // Use FormData to package the file for sending
        const formData = new FormData();
        formData.append('surveyFile', file);

        try {
            // Make a POST request to our Flask backend's /upload endpoint
            const response = await fetch('/upload', {
                method: 'POST',
                body: formData,
            });

            const result = await response.json();

            if (response.ok) {
                // If upload is successful, backend sends back survey_id and survey_url
                currentSurveyId = result.survey_id;
                shareLinkInput.value = result.survey_url; // Populate the share link input

                // Switch to the 'published' screen
                uploadScreen.classList.add('hidden');
                publishedScreen.classList.remove('hidden');
                showModal('Success!', 'Your form has been published.');
            } else {
                // If there's an error, show it in the modal
                showModal('Upload Failed', result.error || 'An unknown error occurred.');
            }
        } catch (error) {
            console.error('Error uploading file:', error);
            showModal('Error', 'Could not connect to the server.');
        }
    });

    // 2. COPY LINK LOGIC
    copyButton.addEventListener('click', () => {
        shareLinkInput.select();
        document.execCommand('copy');
        showModal('Link Copied', 'The survey link is now in your clipboard.');
    });

    // 3. SHARE VIA EMAIL LOGIC
    emailButton.addEventListener('click', async () => {
        const email = shareEmailInput.value;
        const link = shareLinkInput.value;

        if (!email || !email.includes('@')) {
            showModal('Error', 'Please enter a valid email address.');
            return;
        }

        try {
            // Send the email and link to the /share_email endpoint
            const response = await fetch('/share_email', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ email: email, link: link })
            });
            const result = await response.json();
            if (response.ok) {
                showModal('Email Sent', result.message);
            } else {
                showModal('Error', result.error || 'Failed to send email.');
            }
        } catch (error) {
            console.error('Error sending email:', error);
            showModal('Error', 'Could not connect to the server.');
        }
    });

    // 4. DOWNLOAD RESPONSES LOGIC
    downloadButton.addEventListener('click', () => {
        if (!currentSurveyId) {
            showModal('Error', 'Cannot download responses, survey ID is missing.');
            return;
        }
        // Redirect the browser to the download URL. The browser will handle the file download.
        window.location.href = `/download/${currentSurveyId}`;
    });
});