let chatHistory = [];
        
        // Add welcome suggestions
        setTimeout(() => {
            addSuggestions([
                "Recommend a fantasy book",
                "Search for Stephen King",
                "Show top rated books",
                "What genres do you have?"
            ]);
        }, 500);
        
        function addMessage(text, isUser = false, type = 'text', books = [], suggestions = []) {
            const chatMessages = document.getElementById('chatMessages');
            
            // Create message element
            const messageDiv = document.createElement('div');
            messageDiv.className = `message ${isUser ? 'user-message' : 'bot-message'}`;
            
            if (type === 'text') {
                messageDiv.innerHTML = text.replace(/\n/g, '<br>');
            } else if (type === 'book_list') {
                messageDiv.innerHTML = `<strong>${text}</strong>`;
                
                books.forEach(book => {
                    const bookCard = document.createElement('div');
                    bookCard.className = 'book-card';
                    bookCard.innerHTML = `
                        <div class="book-title">${book.title}</div>
                        <div class="book-author">by ${book.author}</div>
                        ${book.genre ? `<div style="color: #667eea; font-size: 12px; margin: 5px 0;">${book.genre}</div>` : ''}
                        ${book.rating ? `<div class="book-rating">⭐ ${book.rating}/5</div>` : ''}
                    `;
                    messageDiv.appendChild(bookCard);
                });
            }
            
            chatMessages.appendChild(messageDiv);
            chatMessages.scrollTop = chatMessages.scrollHeight;
            
            // Add suggestions if any
            if (suggestions.length > 0) {
                addSuggestions(suggestions);
            }
            
            return messageDiv;
        }
        
        function addSuggestions(suggestions) {
            const chatMessages = document.getElementById('chatMessages');
            
            const suggestionsDiv = document.createElement('div');
            suggestionsDiv.className = 'suggestions';
            
            suggestions.forEach(suggestion => {
                const chip = document.createElement('div');
                chip.className = 'suggestion-chip';
                chip.textContent = suggestion;
                chip.onclick = () => {
                    document.getElementById('messageInput').value = suggestion;
                    sendMessage();
                };
                suggestionsDiv.appendChild(chip);
            });
            
            chatMessages.appendChild(suggestionsDiv);
            chatMessages.scrollTop = chatMessages.scrollHeight;
        }
        
        function showTypingIndicator() {
            const chatMessages = document.getElementById('chatMessages');
            const typingDiv = document.createElement('div');
            typingDiv.className = 'typing-indicator';
            typingDiv.id = 'typingIndicator';
            typingDiv.innerHTML = `
                <div class="typing-dot"></div>
                <div class="typing-dot"></div>
                <div class="typing-dot"></div>
            `;
            chatMessages.appendChild(typingDiv);
            chatMessages.scrollTop = chatMessages.scrollHeight;
        }
        
        function hideTypingIndicator() {
            const typingIndicator = document.getElementById('typingIndicator');
            if (typingIndicator) {
                typingIndicator.remove();
            }
        }
        
        async function sendMessage() {
            const input = document.getElementById('messageInput');
            const message = input.value.trim();
            
            if (!message) return;
            
            // Add user message
            addMessage(message, true);
            input.value = '';
            
            // Show typing indicator
            showTypingIndicator();
            
            try {
                const response = await fetch('/api/chatbot/message', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                    },
                    body: JSON.stringify({ message })
                });
                
                const data = await response.json();
                
                // Hide typing indicator
                hideTypingIndicator();
                
                // Add bot response
                addMessage(data.text, false, data.type || 'text', data.books || [], data.suggestions || []);
                
                // Store in history
                chatHistory.push({
                    user: message,
                    bot: data.text,
                    timestamp: new Date().toISOString()
                });
                
            } catch (error) {
                console.error('Error:', error);
                hideTypingIndicator();
                addMessage("Sorry, I'm having trouble connecting. Please try again.", false);
            }
        }
        
        function handleKeyPress(event) {
            if (event.key === 'Enter') {
                sendMessage();
            }
        }
        
        // Load suggestions on startup
        fetch('/api/chatbot/suggestions')
            .then(response => response.json())
            .then(data => {
                if (data.suggestions && data.suggestions.length > 0) {
                    setTimeout(() => {
                        addSuggestions(data.suggestions.slice(0, 4));
                    }, 1000);
                }
            })
            .catch(console.error);