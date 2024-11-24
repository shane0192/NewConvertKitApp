function calculateRevenue() {
    const data = {
        list_size: document.getElementById('list_size').value,
        open_rate: document.getElementById('open_rate').value,
        click_rate: document.getElementById('click_rate').value,
        avg_purchase: document.getElementById('avg_purchase').value,
        conversion_rate: document.getElementById('conversion_rate').value,
        emails_per_month: document.getElementById('emails_per_month').value
    };

    fetch('/calculate', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify(data)
    })
    .then(response => response.json())
    .then(data => {
        const resultsText = `Monthly Metrics:
• Email Opens: ${data.monthly_opens.toLocaleString()}
• Clicks: ${data.monthly_clicks.toLocaleString()}
• Purchases: ${data.monthly_purchases.toLocaleString()}
• Revenue: $${data.monthly_revenue.toLocaleString()}

Annual Revenue: $${data.annual_revenue.toLocaleString()}`;
        
        document.getElementById('results').textContent = resultsText;
    })
    .catch(error => {
        console.error('Error:', error);
        document.getElementById('results').textContent = 'An error occurred. Please try again.';
    });
}

function validateApiKey() {
    const apiKey = document.getElementById('api_key').value;
    console.log('Validating API key...');  // Debug log
    
    fetch('/validate_api_key', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify({ api_key: apiKey })
    })
    .then(response => {
        console.log('Got response:', response);  // Debug log
        return response.json();
    })
    .then(data => {
        console.log('Parsed data:', data);  // Debug log
        if (data.valid) {
            console.log('Tags received:', data.tags);  // Debug log
            console.log('Custom fields received:', data.custom_fields);  // Debug log
            populateDropdowns(data.tags, data.custom_fields);
        } else {
            console.error('API key validation failed:', data.error);  // Debug log
            alert('Invalid API key: ' + data.error);
        }
    })
    .catch(error => {
        console.error('Fetch error:', error);  // Debug log
        alert('An error occurred while validating the API key');
    });
}

function populateDropdowns(tags, customFields) {
    console.log('Populating dropdowns with tags:', tags);
    const tagsSelect = document.getElementById('tags');
    const customFieldsSelect = document.getElementById('custom_fields');
    
    // Clear existing options
    tagsSelect.innerHTML = '';
    customFieldsSelect.innerHTML = '';
    
    // Define the exact tags we want to pre-select (matching exactly what's in your API)
    const tagsToSelect = ['Creator Network - Confirmed', 'Facebook Ads'];
    
    // Add tags
    tags.forEach(tag => {
        const option = new Option(tag, tag);
        if (tagsToSelect.includes(tag)) {
            option.selected = true;
            console.log('Pre-selecting tag:', tag);
        }
        tagsSelect.add(option);
    });
    
    // Add custom fields
    customFields.forEach(field => {
        const option = new Option(field, field);
        // Match the exact custom field name from your API
        if (field === 'rh_isref') {
            option.selected = true;
            console.log('Pre-selecting custom field:', field);
        }
        customFieldsSelect.add(option);
    });
} 