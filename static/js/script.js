document.addEventListener('DOMContentLoaded', function() {
    // Set default dates
    const today = new Date();
    const thirtyDaysAgo = new Date(today);
    thirtyDaysAgo.setDate(today.getDate() - 30);
    
    document.querySelector('input[name="end_date"]').value = today.toISOString().split('T')[0];
    document.querySelector('input[name="start_date"]').value = thirtyDaysAgo.toISOString().split('T')[0];
    
    populateTags();
});

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

function populateTags() {
    console.log('populateTags function is running');
    
    fetch('/get_tags')
        .then(response => response.json())
        .then(data => {
            console.log('Raw data received:', data);
            
            // Get dropdown elements
            const facebookTag = document.getElementById('facebook_tag');
            const creatorTag = document.getElementById('creator_tag');
            const sparkloopTag = document.getElementById('sparkloop_tag');
            
            // Clear existing options
            [facebookTag, creatorTag, sparkloopTag].forEach(select => {
                select.innerHTML = '<option value="">Select a tag</option>';
            });

            // Add all available tags to each dropdown
            if (data.all_tags) {
                data.all_tags.forEach(tag => {
                    // Create options for each dropdown
                    const fbOption = new Option(tag.name, tag.id.toString());
                    const creatorOption = new Option(tag.name, tag.id.toString());
                    const sparkloopOption = new Option(tag.name, tag.id.toString());
                    
                    // Add options to dropdowns
                    facebookTag.add(fbOption);
                    creatorTag.add(creatorOption);
                    sparkloopTag.add(sparkloopOption);
                });
            }

            // Set suggested values if they exist
            if (data.suggested) {
                console.log('Setting suggested values:', data.suggested);
                
                if (data.suggested.facebook) {
                    facebookTag.value = data.suggested.facebook.toString();
                }
                
                if (data.suggested.creator) {
                    creatorTag.value = data.suggested.creator.toString();
                }
                
                if (data.suggested.sparkloop) {
                    sparkloopTag.value = data.suggested.sparkloop.toString();
                }
            }
        })
        .catch(error => {
            console.error('Error loading tags:', error);
        });
}