/**
 * Custom Notification System
 * Auto-dismisses all notifications after 3 seconds
 */

// Custom notification function to replace alert()
function showNotification(message, type = 'info', duration = 1000) {
    // Create notification element
    const notification = document.createElement('div');
    notification.className = `fixed top-4 right-4 max-w-sm p-4 rounded-lg shadow-lg z-[9999] transform transition-all duration-300 translate-x-full opacity-0`;
    
    // Set notification style based on type
    switch(type) {
        case 'success':
            notification.classList.add('bg-green-50', 'border', 'border-green-200', 'text-green-800');
            break;
        case 'error':
            notification.classList.add('bg-red-50', 'border', 'border-red-200', 'text-red-800');
            break;
        case 'warning':
            notification.classList.add('bg-yellow-50', 'border', 'border-yellow-200', 'text-yellow-800');
            break;
        default:
            notification.classList.add('bg-blue-50', 'border', 'border-blue-200', 'text-blue-800');
    }
    
    // Add notification content with close button
    notification.innerHTML = `
        <div class="flex items-start">
            <div class="flex-1">
                <p class="text-sm font-medium">${message}</p>
            </div>
            <button onclick="this.parentElement.parentElement.remove()" class="ml-2 text-gray-400 hover:text-gray-600">
                <svg class="w-4 h-4" fill="currentColor" viewBox="0 0 20 20">
                    <path fill-rule="evenodd" d="M4.293 4.293a1 1 0 011.414 0L10 8.586l4.293-4.293a1 1 0 111.414 1.414L11.414 10l4.293 4.293a1 1 0 01-1.414 1.414L10 11.414l-4.293 4.293a1 1 0 01-1.414-1.414L8.586 10 4.293 5.707a1 1 0 010-1.414z" clip-rule="evenodd"></path>
                </svg>
            </button>
        </div>
    `;
    
    // Add to page
    document.body.appendChild(notification);
    
    // Animate in
    setTimeout(() => {
        notification.classList.remove('translate-x-full', 'opacity-0');
        notification.classList.add('translate-x-0', 'opacity-100');
    }, 100);
    
    // Auto dismiss after duration
    setTimeout(() => {
        notification.classList.add('translate-x-full', 'opacity-0');
        setTimeout(() => {
            if (notification.parentElement) {
                notification.remove();
            }
        }, 300);
    }, duration);
    
    return notification;
}

// Replace the native alert function
window.originalAlert = window.alert;
window.alert = function(message) {
    showNotification(message, 'info', 1000);
};

// Function to auto-hide Django messages
function autoDismissDjangoMessages() {
    // Find all Django message elements
    const messageContainers = document.querySelectorAll('[data-django-messages] > div, .messages > div, .django-messages > div');
    
    messageContainers.forEach(message => {
        // Add close button if not present
        if (!message.querySelector('.close-message')) {
            const closeButton = document.createElement('button');
            closeButton.className = 'close-message ml-2 text-gray-400 hover:text-gray-600 float-right';
            closeButton.innerHTML = `
                <svg class="w-4 h-4" fill="currentColor" viewBox="0 0 20 20">
                    <path fill-rule="evenodd" d="M4.293 4.293a1 1 0 011.414 0L10 8.586l4.293-4.293a1 1 0 111.414 1.414L11.414 10l4.293 4.293a1 1 0 01-1.414 1.414L10 11.414l-4.293 4.293a1 1 0 01-1.414-1.414L8.586 10 4.293 5.707a1 1 0 010-1.414z" clip-rule="evenodd"></path>
                </svg>
            `;
            closeButton.onclick = () => {
                message.style.transition = 'all 0.3s ease-out';
                message.style.opacity = '0';
                message.style.transform = 'translateY(-20px)';
                setTimeout(() => message.remove(), 300);
            };
            message.appendChild(closeButton);
        }
        
        // Auto dismiss after 3 seconds
        setTimeout(() => {
            if (message.parentElement) {
                message.style.transition = 'all 0.3s ease-out';
                message.style.opacity = '0';
                message.style.transform = 'translateY(-20px)';
                setTimeout(() => {
                    if (message.parentElement) {
                        message.remove();
                    }
                }, 300);
            }
        }, 1000);
    });
}

// Function to show success notifications
window.showSuccess = function(message, duration = 1000) {
    return showNotification(message, 'success', duration);
};

// Function to show error notifications
window.showError = function(message, duration = 1000) {
    return showNotification(message, 'error', duration);
};

// Function to show warning notifications
window.showWarning = function(message, duration = 1000) {
    return showNotification(message, 'warning', duration);
};

// Function to show info notifications
window.showInfo = function(message, duration = 1000) {
    return showNotification(message, 'info', duration);
};

// Initialize when DOM is ready
document.addEventListener('DOMContentLoaded', function() {
    // Auto-dismiss existing Django messages
    autoDismissDjangoMessages();
});

// Also run when page is fully loaded (for dynamic content)
window.addEventListener('load', function() {
    // Auto-dismiss any messages that appeared after DOMContentLoaded
    setTimeout(autoDismissDjangoMessages, 100);
});
