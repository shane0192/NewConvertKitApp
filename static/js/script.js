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