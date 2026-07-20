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
});
