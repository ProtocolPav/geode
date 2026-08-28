/**
 * Debug script to test API responses
 */

// Make a test request to the tasks endpoint
fetch('/info/tasks')
    .then(response => response.json())
    .then(data => {
        console.log('Tasks API Response:', data);
        // Check structure
        console.log('Has root property:', data.hasOwnProperty('root'));
        if (data.root) {
            console.log('Root is array:', Array.isArray(data.root));
            console.log('First task item:', data.root[0]);
        }
    })
    .catch(error => console.error('Error fetching tasks:', error));

// Make a test request to the backups endpoint
fetch('/backups/')
    .then(response => response.json())
    .then(data => {
        console.log('Backups API Response:', data);
        // Check structure
        console.log('Has backups property:', data.hasOwnProperty('backups'));
        if (data.backups) {
            console.log('Backups is array:', Array.isArray(data.backups));
            console.log('First backup item:', data.backups[0]);
        }
    })
    .catch(error => console.error('Error fetching backups:', error));

// Make a test request to the info endpoint
fetch('/info/')
    .then(response => response.json())
    .then(data => {
        console.log('Info API Response:', data);
        // Check server_start and status
        console.log('Server status:', data.status);
        console.log('Server start time:', data.server_start);
        console.log('Geode version:', data.geode_version);
        console.log('Minecraft version:', data.minecraft_version);
        
        // Try parsing the date
        if (data.server_start) {
            try {
                const date = new Date(data.server_start);
                console.log('Parsed date:', date, 'Valid:', !isNaN(date));
            } catch (e) {
                console.error('Date parsing error:', e);
            }
        }
    })
    .catch(error => console.error('Error fetching info:', error));