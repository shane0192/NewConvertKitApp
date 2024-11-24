document.addEventListener('DOMContentLoaded', function() {
    // Set default dates
    const today = new Date();
    const thirtyDaysAgo = new Date(today);
    thirtyDaysAgo.setDate(today.getDate() - 30);
    
    document.querySelector('input[name="end_date"]').value = today.toISOString().split('T')[0];
    document.querySelector('input[name="start_date"]').value = thirtyDaysAgo.toISOString().split('T')[0];
    
    // Form validation and submission
    const form = document.querySelector('form');
    if (form) {
        form.addEventListener('submit', handleFormSubmit);
    }
});

async function handleFormSubmit(e) {
    e.preventDefault();
    
    // Show loading state
    const submitButton = this.querySelector('button[type="submit"]');
    const originalButtonText = submitButton.textContent;
    submitButton.textContent = 'Validating...';
    submitButton.disabled = true;
    
    // Get both API credentials
    const apiKey = document.querySelector('#api_key').value;
    const oauthToken = document.querySelector('#oauth_token').value;
    
    // Validate both fields are present
    if (!apiKey || !oauthToken) {
        showAlert('Both API Key and OAuth Token are required', 'danger');
        resetButton(submitButton, originalButtonText);
        return;
    }
    
    try {
        const response = await validateCredentials(apiKey, oauthToken);
        handleValidationResponse(response, this, submitButton, originalButtonText);
    } catch (error) {
        console.error('Error:', error);
        showAlert('An error occurred while validating the API credentials. Please try again.', 'danger');
        resetButton(submitButton, originalButtonText);
    }
}

async function validateCredentials(apiKey, oauthToken) {
    const response = await fetch('/validate_api_key', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/x-www-form-urlencoded',
        },
        body: new URLSearchParams({
            'api_key': apiKey,
            'oauth_token': oauthToken
        })
    });
    return response.json();
}

function handleValidationResponse(data, form, submitButton, originalButtonText) {
    if (data.valid) {
        updateDropdowns(data.tags, data.custom_fields);
        enableFormFields();
        showAlert('API credentials validated successfully!', 'success');
        setTimeout(() => form.submit(), 1000);
    } else {
        showAlert(data.error || 'Invalid API credentials. Please check both API Key and OAuth Token.', 'danger');
        resetButton(submitButton, originalButtonText);
    }
}

function updateDropdowns(tags, customFields) {
    updateSelect('select[name="tags"]', tags);
    updateSelect('select[name="custom_fields"]', customFields);
}

function updateSelect(selector, options) {
    const select = document.querySelector(selector);
    if (select) {
        select.innerHTML = '';
        options.forEach(option => {
            const optionElement = document.createElement('option');
            optionElement.value = option;
            optionElement.textContent = option;
            select.appendChild(optionElement);
        });
    }
}

function enableFormFields() {
    document.querySelectorAll('select, input[type="date"]')
        .forEach(element => element.disabled = false);
}

function showAlert(message, type) {
    const alertDiv = document.createElement('div');
    alertDiv.className = `alert alert-${type}`;
    alertDiv.textContent = message;
    
    const form = document.querySelector('form');
    if (form) {
        form.insertBefore(alertDiv, form.firstChild);
        
        // Remove alert after 5 seconds
        setTimeout(() => alertDiv.remove(), 5000);
    }
}

function resetButton(button, originalText) {
    button.textContent = originalText;
    button.disabled = false;
} 