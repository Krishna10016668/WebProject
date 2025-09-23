// static/survey_script.js

document.getElementById('surveyForm').addEventListener('submit', async function (event) {
    event.preventDefault(); // Prevent the default browser form submission

    // Extract the survey_id from the current URL
    // e.g., from 'http://127.0.0.1:5000/survey/abc-123' it gets 'abc-123'
    const pathParts = window.location.pathname.split('/');
    const surveyId = pathParts[pathParts.length - 1];

    if (!surveyId) {
        console.error("Survey ID not found in URL!");
        alert("Error: Cannot submit form without a survey ID.");
        return;
    }

    const form = event.target;
    const formData = new FormData(form);

    // Convert FormData to a simple JavaScript object
    const data = {};
    formData.forEach((value, key) => {
        data[key] = value;
    });

    console.log('Submitting form data:', data);

    try {
        // Send the data as JSON to the backend's /submit/<survey_id> endpoint
        const response = await fetch(`/submit/${surveyId}`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify(data),
        });

        const result = await response.json();

        if (response.ok) {
            // On success, show the success modal and disable the form
            document.getElementById('successModal').classList.remove('hidden');
            form.reset(); // Clear the form
            // Disable all form elements after successful submission
            Array.from(form.elements).forEach(element => element.disabled = true);
        } else {
            alert(`Error: ${result.error || 'Could not submit survey.'}`);
        }
    } catch (error) {
        console.error('Submission error:', error);
        alert('An error occurred while submitting the form.');
    }
});