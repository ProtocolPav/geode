/**
 * Geode Minecraft Control Panel
 * JavaScript for API interactions and UI functionality
 */

// Constants
const API_BASE_URL = '/'; // Base URL for API endpoints
const REFRESH_INTERVAL = 5000; // Refresh interval in milliseconds

// UI Elements
const elements = {
    // Status elements
    statusDot: document.querySelector('.status-dot'),
    statusText: document.querySelector('.status-text'),
    uptime: document.querySelector('.uptime'),
    version: document.querySelector('.version'),
    
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
    
    // Initial data fetches
    fetchServerInfo();
    fetchTasks();
    fetchBackups();
    
    // Setup log streaming
    setupLogStream();
    
    // Setup regular updates
    updateInterval = setInterval(() => {
        fetchServerInfo();
        fetchTasks();
    }, REFRESH_INTERVAL);
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

// Fetch server information (status, uptime, version)
async function fetchServerInfo() {
    try {
        const response = await fetch(`${API_BASE_URL}info/`);
        if (!response.ok) throw new Error('Failed to fetch server info');
        
        const data = await response.json();
        updateServerInfo(data);
    } catch (error) {
        showToast('Error fetching server info', 'error');
        console.error('Error fetching server info:', error);
    }
}

// Fetch active tasks
async function fetchTasks() {
    try {
        const response = await fetch(`${API_BASE_URL}info/tasks`);
        if (!response.ok) throw new Error('Failed to fetch tasks');
        
        const data = await response.json();
        updateTasksUI(data);
    } catch (error) {
        showToast('Error fetching tasks', 'error');
        console.error('Error fetching tasks:', error);
    }
}

// Fetch backups list
async function fetchBackups() {
    try {
        const response = await fetch(`${API_BASE_URL}backups/`);
        if (!response.ok) throw new Error('Failed to fetch backups');
        
        const data = await response.json();
        updateBackupsUI(data);
    } catch (error) {
        showToast('Error fetching backups', 'error');
        console.error('Error fetching backups:', error);
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
    if (serverStatus === 'running') {
        elements.statusDot.classList.add('online');
    } else if (serverStatus === 'stopped') {
        elements.statusDot.classList.add('offline');
    }
    
    // Update version info
    if (data.minecraft_version) {
        elements.version.textContent = `Version: ${data.minecraft_version}`;
    }
    
    // Update uptime
    const serverStart = data.server_start;
    if (serverStart && serverStatus === 'running') {
        const startTime = new Date(serverStart);
        const now = new Date();
        const uptimeMs = now - startTime;
        
        const hours = Math.floor(uptimeMs / (1000 * 60 * 60));
        const minutes = Math.floor((uptimeMs % (1000 * 60 * 60)) / (1000 * 60));
        const seconds = Math.floor((uptimeMs % (1000 * 60)) / 1000);
        
        elements.uptime.textContent = `Uptime: ${padZero(hours)}:${padZero(minutes)}:${padZero(seconds)}`;
    } else {
        elements.uptime.textContent = 'Uptime: --:--:--';
    }
    
    // Update button states based on server status
    updateButtonStates();
}

// Update tasks list in the UI
function updateTasksUI(data) {
    if (!data.root || data.root.length === 0) {
        elements.tasksContainer.innerHTML = '<p>No active tasks.</p>';
        return;
    }
    
    const tasksList = document.createElement('div');
    tasksList.className = 'tasks-list';
    
    // Show only a limited number of tasks
    const tasksToShow = data.root.slice(0, 10); // Show max 10 tasks
    
    tasksToShow.forEach(task => {
        const taskItem = document.createElement('div');
        taskItem.className = 'task-item';
        
        const taskName = document.createElement('div');
        taskName.className = 'task-name';
        taskName.textContent = task.name || 'Unnamed Task';
        
        const taskDetails = document.createElement('div');
        taskDetails.className = 'task-details';
        taskDetails.textContent = task.coro || '';
        
        taskItem.appendChild(taskName);
        
        tasksList.appendChild(taskItem);
    });
    
    // Clear and update the container
    elements.tasksContainer.innerHTML = '';
    elements.tasksContainer.appendChild(tasksList);
    
    // Add task count if there are more tasks
    if (data.root.length > 10) {
        const moreInfo = document.createElement('p');
        moreInfo.className = 'more-info';
        moreInfo.textContent = `... and ${data.root.length - 10} more tasks`;
        elements.tasksContainer.appendChild(moreInfo);
    }
}

// Update backups list in the UI
function updateBackupsUI(data) {
    if (!data.backups || data.backups.length === 0) {
        elements.backupsContainer.innerHTML = '<p>No backups available.</p>';
        return;
    }
    
    const backupsList = document.createElement('div');
    backupsList.className = 'backups-list';
    
    // Sort backups by date (newest first)
    const sortedBackups = [...data.backups].sort((a, b) => {
        return new Date(b.created_at) - new Date(a.created_at);
    });
    
    sortedBackups.forEach(backup => {
        const backupItem = document.createElement('div');
        backupItem.className = 'backup-item';
        
        const backupName = document.createElement('div');
        backupName.className = 'backup-name';
        backupName.textContent = getBackupDisplayName(backup.full_path);
        
        const backupDate = document.createElement('div');
        backupDate.className = 'backup-date';
        backupDate.textContent = formatDate(backup.created_at);
        
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
    
    // Clear and update the container
    elements.backupsContainer.innerHTML = '';
    elements.backupsContainer.appendChild(backupsList);
}

// Update button states based on server status
function updateButtonStates() {
    const isRunning = serverStatus === 'running';
    const isStopped = serverStatus === 'stopped';
    
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

// Append a log line to the log container
function appendLogLine(text) {
    const logLine = document.createElement('div');
    logLine.className = 'log-line';
    
    // Add color classes based on log content
    if (text.includes('[ERROR]') || text.includes('Exception') || text.includes('Error:')) {
        logLine.classList.add('error');
    } else if (text.includes('[WARN]') || text.includes('[WARNING]')) {
        logLine.classList.add('warning');
    } else if (text.includes('[INFO]')) {
        logLine.classList.add('info');
    }
    
    logLine.textContent = text;
    elements.logContainer.appendChild(logLine);
    
    // Auto-scroll to the bottom
    elements.logContainer.scrollTop = elements.logContainer.scrollHeight;
    
    // Limit the number of log lines (keep last 1000 lines)
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