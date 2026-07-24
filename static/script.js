document.addEventListener('DOMContentLoaded', () => {
    const currentTheme = localStorage.getItem('theme');
    const themeToggle = document.getElementById('theme-toggle');

    if (currentTheme) {
        document.body.classList.add(currentTheme);
        if (themeToggle && currentTheme === 'dark-theme') {
            themeToggle.checked = true;
        }
    }

    if (themeToggle) {
        themeToggle.addEventListener('change', function() {
            if (this.checked) {
                document.body.classList.add('dark-theme');
                localStorage.setItem('theme', 'dark-theme');
            } else {
                document.body.classList.remove('dark-theme');
                localStorage.setItem('theme', '');
            }
        });
    }

    // --- Chatbot Logic ---
    const chatToggleBtn = document.getElementById('chatbot-toggle');
    const chatWindow = document.getElementById('chatbot-window');
    const chatCloseBtn = document.getElementById('chatbot-close');
    const chatInput = document.getElementById('chatbot-input-field');
    const chatSendBtn = document.getElementById('chatbot-send-btn');
    const chatMessages = document.getElementById('chatbot-messages');

    if (chatToggleBtn && chatWindow) {
        // Toggle chat window
        chatToggleBtn.addEventListener('click', () => {
            chatWindow.style.display = chatWindow.style.display === 'none' ? 'flex' : 'none';
            if (chatWindow.style.display === 'flex') {
                chatInput.focus();
            }
        });

        // Close chat window
        chatCloseBtn.addEventListener('click', () => {
            chatWindow.style.display = 'none';
        });

        // Send message function
        const sendMessage = async () => {
            const message = chatInput.value.trim();
            if (!message) return;

            // Add user message to UI
            appendMessage(message, 'user-message');
            chatInput.value = '';

            // Add typing indicator
            const typingId = addTypingIndicator();

            try {
                // Send to backend
                const response = await fetch('/api/chat', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                    },
                    body: JSON.stringify({ message: message })
                });

                const data = await response.json();
                
                // Remove typing indicator
                document.getElementById(typingId)?.remove();

                if (response.ok) {
                    appendMessage(data.response, 'ai-message', true);
                } else {
                    appendMessage('Sorry, I encountered an error. Please check configuration.', 'ai-message', false);
                }
            } catch (error) {
                console.error('Error:', error);
                document.getElementById(typingId)?.remove();
                appendMessage('Failed to connect to the server.', 'ai-message', false);
            }
        };

        // Event listeners for sending
        chatSendBtn.addEventListener('click', sendMessage);
        chatInput.addEventListener('keypress', (e) => {
            if (e.key === 'Enter') {
                sendMessage();
            }
        });

        // Helper to append messages
        function appendMessage(text, className, parseMarkdown = false) {
            const msgDiv = document.createElement('div');
            msgDiv.className = `message ${className}`;
            
            if (parseMarkdown && typeof marked !== 'undefined') {
                msgDiv.innerHTML = marked.parse(text);
            } else {
                msgDiv.textContent = text;
            }
            
            chatMessages.appendChild(msgDiv);
            scrollToBottom();
        }

        // Helper for typing indicator
        function addTypingIndicator() {
            const id = 'typing-' + Date.now();
            const typingDiv = document.createElement('div');
            typingDiv.className = 'typing-indicator';
            typingDiv.id = id;
            typingDiv.innerHTML = `
                <div class="typing-dot"></div>
                <div class="typing-dot"></div>
                <div class="typing-dot"></div>
            `;
            chatMessages.appendChild(typingDiv);
            scrollToBottom();
            return id;
        }

        function scrollToBottom() {
            chatMessages.scrollTop = chatMessages.scrollHeight;
        }
    }

    // --- Floating AI Predictions Widget Logic (Left Side) ---
    const aiWidgetToggle = document.getElementById('ai-widget-toggle');
    const aiWidgetWindow = document.getElementById('ai-widget-window');
    const aiWidgetClose = document.getElementById('ai-widget-close');
    const aiWidgetRefresh = document.getElementById('ai-widget-refresh');
    const aiWidgetBody = document.getElementById('ai-widget-body');

    async function loadAiWidgetInsights() {
        if (!aiWidgetBody) return;
        const refreshIcon = document.getElementById('ai-widget-refresh-icon');
        if (refreshIcon) refreshIcon.classList.add('fa-spin');
        
        try {
            const res = await fetch('/api/ai-predictions');
            const data = await res.json();
            
            let html = '';
            if (data.stockout_predictions && data.stockout_predictions.length > 0) {
                html += `
                    <div style="font-weight: 600; font-size: 13px; color: var(--text-main); margin-bottom: 6px; display: flex; align-items: center; gap: 6px;">
                        <i class="fa-solid fa-crystal-ball" style="color: #8b5cf6;"></i> Stockout Risk Forecast
                    </div>`;
                html += data.stockout_predictions.slice(0, 3).map(p => {
                    const borderColor = p.risk_level === 'High' ? '#ef4444' : (p.risk_level === 'Medium' ? '#f59e0b' : '#10b981');
                    const badgeClass = p.risk_level === 'High' ? 'badge-danger' : (p.risk_level === 'Medium' ? 'badge-warning' : 'badge-success');
                    return `
                    <div style="padding: 8px 12px; background: rgba(0,0,0,0.03); border-radius: 8px; border-left: 3px solid ${borderColor}; margin-bottom: 6px;">
                        <div style="display: flex; justify-content: space-between; align-items: center;">
                            <strong style="font-size: 13px;">${p.product_name}</strong>
                            <span class="badge ${badgeClass}" style="font-size: 10px;">${p.risk_level} Risk</span>
                        </div>
                        <div style="font-size: 11px; color: var(--text-muted); margin-top: 2px;">
                            Stock: ${p.current_qty} | Est. ${p.predicted_days_left} days left
                        </div>
                    </div>`;
                }).join('');
            }
            
            if (data.smart_suggestions && data.smart_suggestions.length > 0) {
                html += `
                    <div style="font-weight: 600; font-size: 13px; color: var(--text-main); margin-top: 10px; margin-bottom: 6px; display: flex; align-items: center; gap: 6px;">
                        <i class="fa-solid fa-lightbulb" style="color: #f59e0b;"></i> Smart Recommendations
                    </div>`;
                html += data.smart_suggestions.slice(0, 3).map(s => {
                    const color = s.badge_color === 'danger' ? '#ef4444' : (s.badge_color === 'warning' ? '#f59e0b' : (s.badge_color === 'info' ? '#3b82f6' : '#10b981'));
                    const bgColor = s.badge_color === 'danger' ? 'rgba(239,68,68,0.15)' : (s.badge_color === 'warning' ? 'rgba(245,158,11,0.15)' : (s.badge_color === 'info' ? 'rgba(59,130,246,0.15)' : 'rgba(16,185,129,0.15)'));
                    const icon = s.icon || 'fa-lightbulb';
                    return `
                    <div style="display: flex; gap: 10px; align-items: flex-start; padding: 8px 12px; background: rgba(0,0,0,0.03); border-radius: 8px; margin-bottom: 6px;">
                        <div style="background: ${bgColor}; color: ${color}; width: 26px; height: 26px; border-radius: 6px; display: flex; align-items: center; justify-content: center; flex-shrink: 0; font-size: 12px;">
                            <i class="fa-solid ${icon}"></i>
                        </div>
                        <div>
                            <strong style="font-size: 12px; display: block;">${s.title}</strong>
                            <span style="font-size: 11px; color: var(--text-muted); line-height: 1.3; display: block;">${s.description}</span>
                        </div>
                    </div>`;
                }).join('');
            }
            
            aiWidgetBody.innerHTML = html || '<p style="font-size: 12px; color: var(--text-muted);">No insights available.</p>';
        } catch(e) {
            console.error(e);
            aiWidgetBody.innerHTML = '<p style="font-size: 12px; color: var(--danger);">Failed to load AI insights.</p>';
        } finally {
            if (refreshIcon) refreshIcon.classList.remove('fa-spin');
        }
    }

    if (aiWidgetToggle && aiWidgetWindow) {
        aiWidgetToggle.addEventListener('click', () => {
            const isHidden = aiWidgetWindow.style.display === 'none';
            aiWidgetWindow.style.display = isHidden ? 'flex' : 'none';
            if (isHidden) {
                loadAiWidgetInsights();
            }
        });
        if (aiWidgetClose) {
            aiWidgetClose.addEventListener('click', () => {
                aiWidgetWindow.style.display = 'none';
            });
        }
        if (aiWidgetRefresh) {
            aiWidgetRefresh.addEventListener('click', loadAiWidgetInsights);
        }
    }
});
