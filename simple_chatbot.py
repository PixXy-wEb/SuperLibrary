"""
Chatbot API endpoints for Flask
"""
from flask import Blueprint, request, jsonify, session
import uuid
import logging

logger = logging.getLogger(__name__)

# Create blueprint
chatbot_bp = Blueprint('simple_chatbot', __name__)

# TEMPORARY: Simple chatbot without ML dependencies
class SimpleChatbot:
    def process_message(self, user_input: str, user_id: str = "default"):
        """Simple echo bot for testing"""
        user_input_lower = user_input.lower()
        
        responses = {
            "hello": "Hi there! I'm your book assistant. How can I help you today?",
            "hi": "Hello! Looking for a good book to read?",
            "recommend": "I'd love to recommend books! What genre interests you?",
            "search": "I can help you search for books. What's the title or author?",
            "help": "I can help you: 📚 Find books, ⭐ Check ratings, 🔍 Search, 🏷️ Browse genres",
            "bye": "Goodbye! Happy reading! 📚"
        }
        
        for key, response in responses.items():
            if key in user_input_lower:
                return {
                    "text": response,
                    "type": "text",
                    "suggestions": ["Fantasy", "Mystery", "Sci-Fi", "Romance"]
                }
        
        # Default response
        return {
            "text": f"I heard you say: '{user_input}'. I'm still learning about books!",
            "type": "text",
            "suggestions": ["What can you do?", "Recommend a book", "Search for Stephen King"]
        }
    
    def get_suggestions(self):
        return [
            "Recommend a fantasy book",
            "Search for books by Stephen King",
            "What are the top rated books?",
            "Tell me about mystery books"
        ]

# Initialize simple chatbot
chatbot = SimpleChatbot()

@chatbot_bp.route('/api/chatbot/message', methods=['POST'])
def chatbot_message():
    """Process chatbot message"""
    try:
        print("Chatbot endpoint called!")  # Debug
        data = request.get_json()
        print(f"Received data: {data}")  # Debug
        
        if not data:
            return jsonify({'error': 'No data provided'}), 400
            
        user_input = data.get('message', '').strip()
        
        if not user_input:
            return jsonify({
                'error': 'Message is required'
            }), 400
        
        # Generate unique user ID if not exists
        user_id = session.get('user_id')
        if not user_id:
            user_id = str(uuid.uuid4())
            session['user_id'] = user_id
        
        print(f"Processing message for user {user_id}: {user_input}")  # Debug
        
        # Process message
        response = chatbot.process_message(user_input, user_id)
        print(f"Sending response: {response}")  # Debug
        
        return jsonify(response)
        
    except Exception as e:
        logger.error(f"Chatbot error: {e}", exc_info=True)
        return jsonify({
            'text': "Sorry, I encountered an error. Please try again!",
            'type': 'text',
            'error': str(e)
        }), 500

@chatbot_bp.route('/api/chatbot/suggestions', methods=['GET'])
def chatbot_suggestions():
    """Get suggested questions"""
    print("Suggestions endpoint called!")  # Debug
    suggestions = chatbot.get_suggestions()
    return jsonify({'suggestions': suggestions})

@chatbot_bp.route('/api/chatbot/test', methods=['GET'])
def chatbot_test():
    """Test endpoint to verify API is working"""
    return jsonify({
        'status': 'ok',
        'message': 'Chatbot API is working!',
        'routes': ['/api/chatbot/message', '/api/chatbot/suggestions']
    })

@chatbot_bp.route('/api/chatbot/clear', methods=['POST'])
def clear_chatbot_context():
    """Clear chatbot context for current user"""
    return jsonify({'status': 'context cleared'})