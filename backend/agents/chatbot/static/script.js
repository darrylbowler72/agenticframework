// Session management
let sessionId = localStorage.getItem('chatSessionId') || generateSessionId();
localStorage.setItem('chatSessionId', sessionId);

function generateSessionId() {
    return 'session_' + Date.now() + '_' + Math.random().toString(36).substr(2, 9);
}

function newChat() {
    if (confirm('Start a new chat? This will clear your current conversation.')) {
        sessionId = generateSessionId();
        localStorage.setItem('chatSessionId', sessionId);
        document.getElementById('chatMessages').innerHTML = `
            <div class="welcome-message">
                <h2>👋 Welcome!</h2>
                <p>I'm your DevOps assistant. I can help you with:</p>
                <ul>
                    <li>📋 <strong>Create Workflows</strong> - Plan and organize your DevOps tasks</li>
                    <li>💻 <strong>Generate Code</strong> - Create microservices, infrastructure, and pipelines</li>
                    <li>🔧 <strong>Fix Issues</strong> - Remediate CI/CD pipeline failures</li>
                    <li>💡 <strong>Get Help</strong> - Ask questions about DevOps best practices</li>
                </ul>
                <p class="try-asking">Try asking: "Create a new Python microservice" or "Help me plan a deployment workflow"</p>
            </div>
        `;
    }
}

// Auto-resize textarea
const userInput = document.getElementById('userInput');
userInput.addEventListener('input', function() {
    this.style.height = 'auto';
    this.style.height = (this.scrollHeight) + 'px';
});

function handleKeyPress(event) {
    if (event.key === 'Enter' && !event.shiftKey) {
        event.preventDefault();
        sendMessage();
    }
}

async function sendMessage() {
    const input = document.getElementById('userInput');
    const sendBtn = document.getElementById('sendBtn');
    const message = input.value.trim();

    if (!message) return;

    // Disable input while sending
    input.disabled = true;
    sendBtn.disabled = true;

    // Clear input
    input.value = '';
    input.style.height = 'auto';

    // Remove welcome message if present
    const welcomeMsg = document.querySelector('.welcome-message');
    if (welcomeMsg) {
        welcomeMsg.remove();
    }

    // Add user message to chat
    addMessage('user', message);

    // Show typing indicator
    showTypingIndicator();

    try {
        // Determine the API endpoint based on current URL
        const apiBase = window.location.pathname.startsWith('/dev') ? '/dev' : '';
        const chatEndpoint = `${apiBase}/chat`;

        // Send message to backend
        const response = await fetch(chatEndpoint, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                session_id: sessionId,
                message: message
            })
        });

        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }

        const data = await response.json();

        // Hide typing indicator
        hideTypingIndicator();

        // Add assistant message
        addMessage('assistant', data.message, data.agent_action);

    } catch (error) {
        console.error('Error:', error);
        hideTypingIndicator();
        addMessage('assistant', 'I apologize, but I encountered an error processing your request. Please try again.');
    } finally {
        // Re-enable input
        input.disabled = false;
        sendBtn.disabled = false;
        input.focus();
    }
}

function addMessage(role, content, action = null) {
    const messagesContainer = document.getElementById('chatMessages');

    const messageDiv = document.createElement('div');
    messageDiv.className = `message ${role}`;

    const avatar = document.createElement('div');
    avatar.className = 'message-avatar';
    avatar.textContent = role === 'user' ? '👤' : '🤖';

    const contentDiv = document.createElement('div');
    contentDiv.className = 'message-content';

    // Format content with line breaks
    const formattedContent = content.replace(/\n/g, '<br>');
    contentDiv.innerHTML = formattedContent;

    // Add action badge if present
    if (action) {
        const actionBadge = document.createElement('div');
        actionBadge.className = 'action-badge';
        const actionLabels = {
            'workflow': '📋 Workflow',
            'codegen': '💻 Code Generation',
            'remediation': '🔧 Remediation',
            'help': '💡 Help'
        };
        actionBadge.textContent = actionLabels[action] || action;
        contentDiv.appendChild(actionBadge);
    }

    // Add timestamp
    const timeDiv = document.createElement('div');
    timeDiv.className = 'message-time';
    timeDiv.textContent = new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
    contentDiv.appendChild(timeDiv);

    messageDiv.appendChild(avatar);
    messageDiv.appendChild(contentDiv);

    messagesContainer.appendChild(messageDiv);

    // Scroll to bottom
    messagesContainer.scrollTop = messagesContainer.scrollHeight;
}

function showTypingIndicator() {
    const indicator = document.getElementById('typingIndicator');
    indicator.style.display = 'flex';
}

function hideTypingIndicator() {
    const indicator = document.getElementById('typingIndicator');
    indicator.style.display = 'none';
}

// Load session history on page load
window.addEventListener('DOMContentLoaded', async () => {
    try {
        const apiBase = window.location.pathname.startsWith('/dev') ? '/dev' : '';
        const response = await fetch(`${apiBase}/session/${sessionId}`);

        if (response.ok) {
            const session = await response.json();
            if (session.messages && session.messages.length > 0) {
                // Remove welcome message
                const welcomeMsg = document.querySelector('.welcome-message');
                if (welcomeMsg) {
                    welcomeMsg.remove();
                }

                // Add all messages
                session.messages.forEach(msg => {
                    addMessage(msg.role, msg.content);
                });
            }
        }
    } catch (error) {
        console.error('Error loading session:', error);
    }
});

// Focus input on load
document.getElementById('userInput').focus();

// Agent Health Status Functions
async function fetchAgentHealth() {
    try {
        const apiBase = window.location.pathname.startsWith('/dev') ? '/dev' : '';
        const response = await fetch(`${apiBase}/api/agents/health`);

        if (!response.ok) {
            throw new Error('Failed to fetch agent health');
        }

        const data = await response.json();
        return data;
    } catch (error) {
        console.error('Error fetching agent health:', error);
        return null;
    }
}

function updateAgentStatusUI(healthData) {
    const statusGrid = document.getElementById('agentStatusGrid');

    if (!healthData || !healthData.agents) {
        statusGrid.innerHTML = '<div class="status-loading">Failed to load agent status</div>';
        return;
    }

    // Calculate overall health
    const agents = healthData.agents;
    const healthyCount = Object.values(agents).filter(agent =>
        agent.status === 'healthy' && agent.http_status !== 'error'
    ).length;
    const totalCount = Object.keys(agents).length;

    // Update overall status indicator
    const overallStatus = document.getElementById('overallStatus');
    overallStatus.className = 'status-indicator';
    if (healthyCount === totalCount) {
        overallStatus.classList.add('healthy');
    } else if (healthyCount > 0) {
        overallStatus.classList.add('degraded');
    } else {
        overallStatus.classList.add('error');
    }

    // Build agent cards HTML
    let html = '';
    for (const [agentName, agentData] of Object.entries(agents)) {
        const status = agentData.http_status || agentData.status || 'error';
        const version = agentData.version || 'unknown';

        html += `
            <div class="agent-card">
                <div class="agent-info">
                    <div class="agent-name">${agentName}</div>
                    <div class="agent-version">v${version}</div>
                </div>
                <div class="agent-status ${status}">${status}</div>
            </div>
        `;
    }

    // Add last updated timestamp
    const lastUpdated = new Date(healthData.timestamp).toLocaleTimeString();
    html += `<div class="status-last-updated">Last updated: ${lastUpdated}</div>`;

    statusGrid.innerHTML = html;
}

function toggleAgentStatus() {
    const panel = document.getElementById('agentStatusPanel');

    if (panel.style.display === 'none' || !panel.style.display) {
        panel.style.display = 'block';
        // Fetch fresh data when opening
        fetchAgentHealth().then(data => {
            if (data) {
                updateAgentStatusUI(data);
            }
        });
    } else {
        panel.style.display = 'none';
    }
}

// Auto-refresh agent health every 30 seconds if panel is open
setInterval(() => {
    const panel = document.getElementById('agentStatusPanel');
    if (panel.style.display === 'block') {
        fetchAgentHealth().then(data => {
            if (data) {
                updateAgentStatusUI(data);
            }
        });
    }
}, 30000);

// Fetch initial agent health status after page load
window.addEventListener('DOMContentLoaded', () => {
    fetchAgentHealth().then(data => {
        if (data) {
            // Update overall status indicator
            const agents = data.agents;
            const healthyCount = Object.values(agents).filter(agent =>
                agent.status === 'healthy' && agent.http_status !== 'error'
            ).length;
            const totalCount = Object.keys(agents).length;

            const overallStatus = document.getElementById('overallStatus');
            overallStatus.className = 'status-indicator';
            if (healthyCount === totalCount) {
                overallStatus.classList.add('healthy');
            } else if (healthyCount > 0) {
                overallStatus.classList.add('degraded');
            } else {
                overallStatus.classList.add('error');
            }
        }
    });
});
