/**
 * Geode Minecraft Control Panel
 * JavaScript for API interactions and UI functionality
 */

// Constants
const API_BASE_URL = '/'; // Base URL for API endpoints
const REFRESH_INTERVAL = 3000; // Refresh interval in milliseconds for frequent updates
const BACKUP_REFRESH_INTERVAL = 30000; // Refresh interval for backups (30 seconds)

// UI Elements
const elements = {
    // Status elements
    statusDot: document.querySelector('.status-dot'),
    statusText: document.querySelector('.status-text'),
    uptime: document.querySelector('.uptime'),
    version: document.querySelector('.version'),
    geodeVersion: document.querySelector('.geode-version'),
    
    // Control buttons
    startBtn: document.getElementById('start-btn'),
    stopBtn: document.getElementById('stop-btn'),
    restartBtn: document.getElementById('restart-btn'),
    killBtn: document.getElementById('kill-btn'),
    
    // Command input
    commandInput: document.getElementById('command-input'),
    sendCommandBtn: document.getElementById('send-command-btn'),
    
    // Logs
    logContainer: document.getElementById('log-container'),
    clearLogsBtn: document.getElementById('clear-logs-btn'),
    
    // Tasks
    tasksContainer: document.getElementById('tasks-container'),
    refreshTasksBtn: document.getElementById('refresh-tasks-btn'),
    
    // Backups
    backupsContainer: document.getElementById('backups-container'),
    createBackupBtn: document.getElementById('create-backup-btn'),
    
    // Modal
    modal: document.getElementById('modal'),
    modalTitle: document.getElementById('modal-title'),
    modalMessage: document.getElementById('modal-message'),
    modalConfirm: document.getElementById('modal-confirm'),
    modalCancel: document.getElementById('modal-cancel'),
    closeBtn: document.querySelector('.close-btn'),
    
    // Toast
    toastContainer: document.getElementById('toast-container')
};

// State
let serverStatus = 'unknown';
let logEventSource = null;
let updateInterval = null;

// Initialize the application
function init() {
    // Add event listeners
    setupEventListeners();
    
    // Initial data fetches - immediately and with slight delays to prevent overwhelming the server
    fetchServerInfo();
    
    // Stagger the initial fetches
    setTimeout(() => {
        fetchTasks();
    }, 500);
    
    setTimeout(() => {
        fetchBackups();
    }, 1000);
    
    // Setup log streaming
    setupLogStream();
    
    // Setup regular updates for server info and tasks (high frequency)
    updateInterval = setInterval(() => {
        fetchServerInfo();
        fetchTasks();
    }, REFRESH_INTERVAL);
    
    // Setup less frequent updates for backups
    setInterval(() => {
        fetchBackups();
    }, BACKUP_REFRESH_INTERVAL);
}

// Setup event listeners for UI interactions
function setupEventListeners() {
    // Control buttons
    elements.startBtn.addEventListener('click', () => handleControlAction('start', 'Start the server'));
    elements.stopBtn.addEventListener('click', () => handleControlAction('stop', 'Stop the server'));
    elements.restartBtn.addEventListener('click', () => handleControlAction('restart', 'Restart the server'));
    elements.killBtn.addEventListener('click', () => handleControlAction('kill', 'Force kill the server'));
    
    // Command input
    elements.sendCommandBtn.addEventListener('click', sendCommand);
    elements.commandInput.addEventListener('keypress', (e) => {
        if (e.key === 'Enter') sendCommand();
    });
    
    // Logs
    elements.clearLogsBtn.addEventListener('click', clearLogs);
    
    // Tasks
    elements.refreshTasksBtn.addEventListener('click', fetchTasks);
    
    // Backups
    elements.createBackupBtn.addEventListener('click', createBackup);
    
    // Modal
    elements.closeBtn.addEventListener('click', closeModal);
    elements.modalCancel.addEventListener('click', closeModal);
    window.addEventListener('click', (e) => {
        if (e.target === elements.modal) closeModal();
    });
}

// API Interactions

// Helper function to fetch with retry
async function fetchWithRetry(url, maxRetries = 3, retryDelay = 1000) {
    let lastError = null;
    
    for (let attempt = 0; attempt < maxRetries; attempt++) {
        try {
            const response = await fetch(url);
            if (!response.ok) throw new Error(`HTTP error ${response.status}`);
            
            const data = await response.json();
            return { success: true, data };
        } catch (error) {
            console.warn(`Attempt ${attempt + 1}/${maxRetries} failed for ${url}:`, error);
            lastError = error;
            
            if (attempt < maxRetries - 1) {
                // Wait before next retry
                await new Promise(resolve => setTimeout(resolve, retryDelay));
            }
        }
    }
    
    return { success: false, error: lastError };
}

// Fetch server information (status, uptime, version)
async function fetchServerInfo() {
    const result = await fetchWithRetry(`${API_BASE_URL}info/`);
    
    if (result.success) {
        updateServerInfo(result.data);
    } else {
        console.error('Error fetching server info:', result.error);
        // Only show toast for persistent errors
        showToast('Error fetching server info', 'error');
    }
}

// Fetch active tasks
async function fetchTasks() {
    const result = await fetchWithRetry(`${API_BASE_URL}info/tasks`);
    
    if (result.success) {
        updateTasksUI(result.data);
    } else {
        console.error('Error fetching tasks:', result.error);
        // Avoid spam toasts for background fetches
    }
}

// Fetch backups list
async function fetchBackups() {
    const result = await fetchWithRetry(`${API_BASE_URL}backups/`);
    
    if (result.success) {
        updateBackupsUI(result.data);
    } else {
        console.error('Error fetching backups:', result.error);
        // Avoid spam toasts for background fetches
    }
}

// Send server control commands (start, stop, restart, kill)
async function sendControlCommand(action) {
    try {
        const response = await fetch(`${API_BASE_URL}controls/${action}`, {
            method: 'POST'
        });
        
        if (!response.ok) throw new Error(`Failed to ${action} server`);
        
        showToast(`Server ${action} command sent successfully`, 'success');
        
        // Refresh server info after a short delay
        setTimeout(fetchServerInfo, 1000);
    } catch (error) {
        showToast(`Error: ${error.message}`, 'error');
        console.error(`Error sending ${action} command:`, error);
    }
}

// Send a Minecraft command to the server
async function sendCommand() {
    const command = elements.commandInput.value.trim();
    if (!command) return;
    
    try {
        const response = await fetch(`${API_BASE_URL}controls/command`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ command })
        });
        
        if (!response.ok) throw new Error('Failed to send command');
        
        showToast(`Command sent: ${command}`, 'success');
        elements.commandInput.value = ''; // Clear input field
    } catch (error) {
        showToast('Error sending command', 'error');
        console.error('Error sending command:', error);
    }
}

// Create a new backup
async function createBackup() {
    try {
        const response = await fetch(`${API_BASE_URL}backups/`, {
            method: 'POST'
        });
        
        if (!response.ok) throw new Error('Failed to create backup');
        
        showToast('Backup initiated', 'success');
        
        // Refresh backups list after a short delay
        setTimeout(fetchBackups, 5000);
    } catch (error) {
        showToast('Error creating backup', 'error');
        console.error('Error creating backup:', error);
    }
}

// Restore a backup
async function restoreBackup(fullPath) {
    try {
        const response = await fetch(`${API_BASE_URL}backups/restore`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ full_path: fullPath })
        });
        
        if (!response.ok) throw new Error('Failed to restore backup');
        
        showToast('Backup restoration initiated', 'success');
    } catch (error) {
        showToast('Error restoring backup', 'error');
        console.error('Error restoring backup:', error);
    }
}

// Set up event source for log streaming
function setupLogStream() {
    // Close any existing connection
    if (logEventSource) {
        logEventSource.close();
    }
    
    // Create a new event source connection
    logEventSource = new EventSource(`${API_BASE_URL}controls/logs`);
    
    // Listen for log events
    logEventSource.onmessage = (event) => {
        appendLogLine(event.data);
    };
    
    logEventSource.onerror = () => {
        // If the connection is closed, try to reconnect after a delay
        logEventSource.close();
        setTimeout(setupLogStream, 5000);
    };
}

// UI Updates

// Update server information in the UI
function updateServerInfo(data) {
    // Update server status
    serverStatus = data.status;
    elements.statusText.textContent = capitalizeFirstLetter(serverStatus);
    
// Update status indicator
    elements.statusDot.className = 'status-dot';
    if (serverStatus === 'started' || serverStatus === 'running') {
        elements.statusDot.classList.add('online');
    } else if (serverStatus === 'stopped') {
        elements.statusDot.classList.add('offline');
    }
    
    // Update version info
    if (data.minecraft_version) {
        elements.version.textContent = `MC Version: ${data.minecraft_version}`;
    }
    
    // Update Geode version
    if (data.geode_version) {
        elements.geodeVersion.textContent = `Geode: ${data.geode_version}`;
    }
    
    // Store the start time globally so we can update uptime continuously
    const serverStart = data.server_start;
    
    // Debug uptime calculation
    console.log('Server status:', serverStatus, 'Server start:', serverStart);
    
    // Check if server is in running-like state (match both 'running' and 'started')
    const isRunning = serverStatus === 'started' || serverStatus === 'running';
    console.log('Is server running?', isRunning);
    
    if (serverStart && isRunning) {
        try {
            const startTime = new Date(serverStart);
            console.log('Parsed server start time:', startTime, 'Valid:', !isNaN(startTime.getTime()));
            
            if (!isNaN(startTime.getTime())) {
                // Store as a timestamp number for more reliable comparison
                window.serverStartTimestamp = startTime.getTime();
                
                // Update immediately
                updateUptime();
                
                // Start a timer to update the uptime every second if it's not already running
                if (!window.uptimeInterval) {
                    console.log('Starting uptime interval');
                    window.uptimeInterval = setInterval(updateUptime, 1000);
                }
            } else {
                console.error('Invalid server start time:', serverStart);
                elements.uptime.textContent = 'Uptime: Invalid date';
            }
        } catch (e) {
            console.error('Error parsing server start time:', e);
            elements.uptime.textContent = 'Uptime: Parse error';
        }
    } else {
        elements.uptime.textContent = 'Uptime: --:--:--';
        // Clear the interval if the server is not running
        if (window.uptimeInterval) {
            console.log('Clearing uptime interval');
            clearInterval(window.uptimeInterval);
            window.uptimeInterval = null;
        }
    }
    
    // Update button states based on server status
    updateButtonStates();
}

// Update tasks list in the UI
function updateTasksUI(data) {
    console.log('Tasks data:', data); // Debug log
    
    // Handle direct array response OR object with root property
    let tasks = data;
    if (!Array.isArray(data) && data && data.root) {
        tasks = data.root;
    }
    
    // Defensive check - if data is null/undefined or doesn't have the expected structure
    if (!tasks || !Array.isArray(tasks) || tasks.length === 0) {
        elements.tasksContainer.innerHTML = '<p>No active tasks.</p>';
        return;
    }
    
    // For debugging:
    console.log(`Found ${tasks.length} tasks`);
    
    const tasksList = document.createElement('div');
    tasksList.className = 'tasks-list';
    
    // Show only a limited number of tasks
    const tasksToShow = tasks.slice(0, 10); // Show max 10 tasks
    
    tasksToShow.forEach(task => {
        const taskItem = document.createElement('div');
        taskItem.className = 'task-item';
        
        const taskName = document.createElement('div');
        taskName.className = 'task-name';
        taskName.textContent = task.name || 'Unnamed Task';
        
        const taskDetails = document.createElement('div');
        taskDetails.className = 'task-details';
        taskDetails.textContent = task.coro ? `Function: ${task.coro}` : '';
        
        taskItem.appendChild(taskName);
        if (task.coro) {
            taskItem.appendChild(taskDetails);
        }
        
        tasksList.appendChild(taskItem);
    });
    
    // Clear and update the container
    elements.tasksContainer.innerHTML = '';
    elements.tasksContainer.appendChild(tasksList);
    
    // Add task count if there are more tasks
    if (tasks.length > 10) {
        const moreInfo = document.createElement('p');
        moreInfo.className = 'more-info';
        moreInfo.textContent = `... and ${tasks.length - 10} more tasks`;
        elements.tasksContainer.appendChild(moreInfo);
    }
}

// Update backups list in the UI
function updateBackupsUI(data) {
    console.log('Backups data:', data); // Debug log
    
    // Defensive check with more logging
    if (!data) {
        console.error('Backups data is null or undefined');
        elements.backupsContainer.innerHTML = '<p>No backups available.</p>';
        return;
    }
    
    // Check if data is a direct array or has a nested structure
    let backups = [];
    if (Array.isArray(data)) {
        console.log('Backups is direct array');
        backups = data;
    } else if (data.root && Array.isArray(data.root)) {
        console.log('Backups using root structure');
        backups = data.root;
    } else if (data.backups && Array.isArray(data.backups)) {
        console.log('Backups using backups property');
        backups = data.backups;
    } else {
        console.error('Could not find backups array in', data);
        elements.backupsContainer.innerHTML = '<p>No backups available.</p>';
        return;
    }
    
    const backupsList = document.createElement('div');
    backupsList.className = 'backups-list';
    
    // Sort backups by date (newest first) - with null checking
    let sortedBackups = [];
    try {
        if (backups && Array.isArray(backups) && backups.length > 0) {
            sortedBackups = backups.slice().sort((a, b) => {
                // Use timestamp instead of created_at
                return new Date(b.timestamp || 0) - new Date(a.timestamp || 0);
            });
        } else {
            console.warn('No valid backups array to sort');
        }
    } catch (error) {
        console.error('Error sorting backups:', error);
    }
    
    sortedBackups.forEach(backup => {
        const backupItem = document.createElement('div');
        backupItem.className = 'backup-item';
        
        const backupName = document.createElement('div');
        backupName.className = 'backup-name';
        backupName.textContent = getBackupDisplayName(backup.full_path);
        
        const backupDate = document.createElement('div');
        backupDate.className = 'backup-date';
        backupDate.textContent = formatDate(backup.timestamp);
        
        backupItem.appendChild(backupName);
        backupItem.appendChild(backupDate);
        
        // Add click handler for backup restoration
        backupItem.addEventListener('click', () => {
            showModal(
                'Restore Backup',
                `Are you sure you want to restore backup: ${getBackupDisplayName(backup.full_path)}?`,
                () => restoreBackup(backup.full_path)
            );
        });
        
        backupsList.appendChild(backupItem);
    });
    
    // Clear and update the container with proper error checking
    if (backupsList.childNodes.length > 0) {
        console.log(`Displaying ${backupsList.childNodes.length} backups`);
        requestAnimationFrame(() => {
            elements.backupsContainer.innerHTML = '';
            elements.backupsContainer.appendChild(backupsList);
        });
    } else {
        console.warn('No backup items were created');
        elements.backupsContainer.innerHTML = '<p>No valid backups available.</p>';
    }
}

// Update button states based on server status
function updateButtonStates() {
    // Account for both 'running' and 'started' status
    const isRunning = serverStatus === 'running' || serverStatus === 'started';
    const isStopped = serverStatus === 'stopped';
    
    console.log('Button state update - Status:', serverStatus, 'Running:', isRunning, 'Stopped:', isStopped);
    
    // Enable/disable buttons based on server status
    elements.startBtn.disabled = isRunning;
    elements.stopBtn.disabled = isStopped;
    elements.restartBtn.disabled = isStopped;
    elements.killBtn.disabled = isStopped;
    elements.sendCommandBtn.disabled = isStopped;
    elements.commandInput.disabled = isStopped;
    
    // Apply visual disabled state
    [elements.startBtn, elements.stopBtn, elements.restartBtn, elements.killBtn, elements.sendCommandBtn]
        .forEach(button => {
            if (button.disabled) {
                button.classList.add('disabled');
            } else {
                button.classList.remove('disabled');
            }
        });
}

// ANSI color code mappings to CSS
const ANSI_COLORS = {
    // Standard foreground colors
    30: 'color:#4e4e4e',  // Black (dark gray for visibility)
    31: 'color:#cc0000',  // Red
    32: 'color:#4e9a06',  // Green
    33: 'color:#c4a000',  // Yellow
    34: 'color:#3465a4',  // Blue
    35: 'color:#75507b',  // Magenta
    36: 'color:#06989a',  // Cyan
    37: 'color:#d3d7cf',  // White
    // Bright foreground colors
    90: 'color:#555753',  // Bright Black
    91: 'color:#ef2929',  // Bright Red
    92: 'color:#8ae234',  // Bright Green
    93: 'color:#fce94f',  // Bright Yellow
    94: 'color:#729fcf',  // Bright Blue
    95: 'color:#ad7fa8',  // Bright Magenta
    96: 'color:#34e2e2',  // Bright Cyan
    97: 'color:#eeeeec',  // Bright White
};

const ANSI_BG_COLORS = {
    40: 'background:#4e4e4e',
    41: 'background:#cc0000',
    42: 'background:#4e9a06',
    43: 'background:#c4a000',
    44: 'background:#3465a4',
    45: 'background:#75507b',
    46: 'background:#06989a',
    47: 'background:#d3d7cf',
    100: 'background:#555753',
    101: 'background:#ef2929',
    102: 'background:#8ae234',
    103: 'background:#fce94f',
    104: 'background:#729fcf',
    105: 'background:#ad7fa8',
    106: 'background:#34e2e2',
    107: 'background:#eeeeec',
};

/**
 * Parses an ANSI-escaped string and returns a DocumentFragment
 * with <span> elements styled per escape sequence.
 */
function ansiToHtml(text) {
    const fragment = document.createDocumentFragment();
    // Regex matches ESC[ ... m sequences
    const ansiRegex = /\x1b\[([0-9;]*)m/g;

    let lastIndex = 0;
    let currentStyles = [];   // active CSS style strings
    let bold = false;
    let dim = false;
    let italic = false;
    let underline = false;

    function flushText(rawText) {
        if (!rawText) return;
        const span = document.createElement('span');
        const allStyles = [...currentStyles];
        if (bold)      allStyles.push('font-weight:bold');
        if (dim)       allStyles.push('opacity:0.6');
        if (italic)    allStyles.push('font-style:italic');
        if (underline) allStyles.push('text-decoration:underline');
        if (allStyles.length) span.style.cssText = allStyles.join(';');
        span.textContent = rawText;
        fragment.appendChild(span);
    }

    let match;
    while ((match = ansiRegex.exec(text)) !== null) {
        // Flush any text before this escape sequence
        flushText(text.slice(lastIndex, match.index));
        lastIndex = match.index + match[0].length;

        // Parse the codes (e.g. "1;32" → [1, 32])
        const codes = match[1] === '' ? [0] : match[1].split(';').map(Number);

        for (const code of codes) {
            if (code === 0) {
                // Reset all
                currentStyles = [];
                bold = dim = italic = underline = false;
            } else if (code === 1) {
                bold = true;
            } else if (code === 2) {
                dim = true;
            } else if (code === 3) {
                italic = true;
            } else if (code === 4) {
                underline = true;
            } else if (code === 22) {
                bold = false; dim = false;
            } else if (code === 23) {
                italic = false;
            } else if (code === 24) {
                underline = false;
            } else if (ANSI_COLORS[code]) {
                // Remove any existing foreground color
                currentStyles = currentStyles.filter(s => !s.startsWith('color'));
                currentStyles.push(ANSI_COLORS[code]);
            } else if (ANSI_BG_COLORS[code]) {
                currentStyles = currentStyles.filter(s => !s.startsWith('background'));
                currentStyles.push(ANSI_BG_COLORS[code]);
            }
            // 256-color and truecolor (38;5;n / 38;2;r;g;b) are handled below
        }

        // Handle 256-color: ESC[38;5;<n>m and ESC[48;5;<n>m
        if (codes[0] === 38 && codes[1] === 5 && codes[2] !== undefined) {
            currentStyles = currentStyles.filter(s => !s.startsWith('color'));
            currentStyles.push(`color:${ansi256ToHex(codes[2])}`);
        } else if (codes[0] === 48 && codes[1] === 5 && codes[2] !== undefined) {
            currentStyles = currentStyles.filter(s => !s.startsWith('background'));
            currentStyles.push(`background:${ansi256ToHex(codes[2])}`);
        }
        // Handle truecolor: ESC[38;2;<r>;<g>;<b>m
        else if (codes[0] === 38 && codes[1] === 2 && codes.length >= 5) {
            currentStyles = currentStyles.filter(s => !s.startsWith('color'));
            currentStyles.push(`color:rgb(${codes[2]},${codes[3]},${codes[4]})`);
        } else if (codes[0] === 48 && codes[1] === 2 && codes.length >= 5) {
            currentStyles = currentStyles.filter(s => !s.startsWith('background'));
            currentStyles.push(`background:rgb(${codes[2]},${codes[3]},${codes[4]})`);
        }
    }

    // Flush any remaining text after the last escape sequence
    flushText(text.slice(lastIndex));
    return fragment;
}

/**
 * Converts a 256-color ANSI index to a hex color string.
 */
function ansi256ToHex(n) {
    // Standard 16 colors
    const base16 = [
        '#000000','#800000','#008000','#808000','#000080','#800080','#008080','#c0c0c0',
        '#808080','#ff0000','#00ff00','#ffff00','#0000ff','#ff00ff','#00ffff','#ffffff'
    ];
    if (n < 16) return base16[n];
    // 6×6×6 color cube
    if (n < 232) {
        n -= 16;
        const b = n % 6, g = Math.floor(n / 6) % 6, r = Math.floor(n / 36);
        const c = v => v === 0 ? 0 : 55 + v * 40;
        return `rgb(${c(r)},${c(g)},${c(b)})`;
    }
    // Grayscale ramp
    const gray = 8 + (n - 232) * 10;
    return `rgb(${gray},${gray},${gray})`;
}

// Append a log line to the log container (with ANSI support)
function appendLogLine(text) {
    const logLine = document.createElement('div');
    logLine.className = 'log-line';

//    // Add semantic color classes based on log level keywords
//    if (text.includes('[ERROR]') || text.includes('Exception') || text.includes('Error:')) {
//        logLine.classList.add('error');
//    } else if (text.includes('[WARN]') || text.includes('[WARNING]')) {
//        logLine.classList.add('warning');
//    } else if (text.includes('[INFO]')) {
//        logLine.classList.add('info');
//    }

    // Render ANSI codes as styled spans
    logLine.appendChild(ansiToHtml(text));
    elements.logContainer.appendChild(logLine);

    // Auto-scroll to bottom
    elements.logContainer.scrollTop = elements.logContainer.scrollHeight;

    // Limit log lines to last 1000
    const maxLogLines = 1000;
    while (elements.logContainer.childElementCount > maxLogLines) {
        elements.logContainer.removeChild(elements.logContainer.firstChild);
    }
}

// Clear all logs
function clearLogs() {
    elements.logContainer.innerHTML = '';
}

// Helper Functions

// Show a modal dialog
function showModal(title, message, confirmCallback) {
    elements.modalTitle.textContent = title;
    elements.modalMessage.textContent = message;
    
    // Set up confirm callback
    elements.modalConfirm.onclick = () => {
        confirmCallback();
        closeModal();
    };
    
    // Show the modal
    elements.modal.classList.add('active');
}

// Close the modal dialog
function closeModal() {
    elements.modal.classList.remove('active');
}

// Show a toast notification
function showToast(message, type = 'info') {
    const toast = document.createElement('div');
    toast.className = `toast ${type}`;
    
    const toastContent = document.createElement('div');
    toastContent.className = 'toast-content';
    toastContent.textContent = message;
    
    const toastClose = document.createElement('div');
    toastClose.className = 'toast-close';
    toastClose.innerHTML = '&times;';
    toastClose.addEventListener('click', () => removeToast(toast));
    
    toast.appendChild(toastContent);
    toast.appendChild(toastClose);
    elements.toastContainer.appendChild(toast);
    
    // Auto-remove toast after 5 seconds
    setTimeout(() => removeToast(toast), 5000);
}

// Remove a toast notification
function removeToast(toast) {
    toast.classList.add('closing');
    setTimeout(() => {
        if (toast.parentNode) {
            toast.parentNode.removeChild(toast);
        }
    }, 300); // Match animation duration
}

// Handle control action with confirmation
function handleControlAction(action, actionTitle) {
    let message;
    
    switch (action) {
        case 'start':
            message = 'Are you sure you want to start the server?';
            break;
        case 'stop':
            message = 'Are you sure you want to stop the server? This will safely shut down the server.';
            break;
        case 'restart':
            message = 'Are you sure you want to restart the server?';
            break;
        case 'kill':
            message = 'Are you sure you want to force kill the server? This may cause data loss!';
            break;
        default:
            message = 'Are you sure you want to perform this action?';
    }
    
    showModal(actionTitle, message, () => sendControlCommand(action));
}

// Helper function to capitalize first letter
function capitalizeFirstLetter(string) {
    if (!string) return '';
    return string.charAt(0).toUpperCase() + string.slice(1);
}

// Helper function to pad numbers with leading zero
function padZero(num) {
    return num.toString().padStart(2, '0');
}

// Update uptime display
function updateUptime() {
    try {
        // Check if we have a valid server start timestamp
        if (window.serverStartTimestamp) {
            const now = Date.now(); // More efficient than new Date()
            const uptimeMs = now - window.serverStartTimestamp;
            
            // Log occasionally for debugging
            if (Math.floor(uptimeMs / 1000) % 30 === 0) { // Log every 30 seconds
                console.log('Updating uptime:', uptimeMs, 'ms');
            }
            
            const hours = Math.floor(uptimeMs / (1000 * 60 * 60));
            const minutes = Math.floor((uptimeMs % (1000 * 60 * 60)) / (1000 * 60));
            const seconds = Math.floor((uptimeMs % (1000 * 60)) / 1000);
            
            // Force DOM update
            elements.uptime.textContent = `Uptime: ${padZero(hours)}:${padZero(minutes)}:${padZero(seconds)}`;
        } else if (window.serverStartTime) {
            // Backward compatibility with old code
            const now = new Date();
            const uptimeMs = now - window.serverStartTime;
            
            const hours = Math.floor(uptimeMs / (1000 * 60 * 60));
            const minutes = Math.floor((uptimeMs % (1000 * 60 * 60)) / (1000 * 60));
            const seconds = Math.floor((uptimeMs % (1000 * 60)) / 1000);
            
            elements.uptime.textContent = `Uptime: ${padZero(hours)}:${padZero(minutes)}:${padZero(seconds)}`;
        }
    } catch (error) {
        console.error('Error updating uptime:', error);
    }
}

// Helper function to format dates
function formatDate(dateString) {
    const date = new Date(dateString);
    return `${date.toLocaleDateString()} ${date.toLocaleTimeString()}`;
}

// Extract backup name from full path
function getBackupDisplayName(fullPath) {
    if (!fullPath) return 'Unknown';
    
    // Extract the filename from the path
    const pathParts = fullPath.split('/');
    return pathParts[pathParts.length - 1];
}

// Initialize on DOM loaded
document.addEventListener('DOMContentLoaded', init);