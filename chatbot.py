"""
Chatbot API endpoints for Flask
"""
from flask import Blueprint, request, jsonify, session
from ml.chatbot_engine import ChatbotEngine
import uuid
import logging

logger = logging.getLogger(__name__)

# Create blueprint
chatbot_bp = Blueprint('chatbot', __name__)

"""
Chatbot API endpoints for Flask
"""
from flask import Blueprint, request, jsonify, session
import uuid
import logging

logger = logging.getLogger(__name__)

# Create blueprint
chatbot_bp = Blueprint('chatbot', __name__)




# Initialize chatbot engine
chatbot = ChatbotEngine()

@chatbot_bp.route('/api/chatbot/message', methods=['POST'])
def chatbot_message():
    """Process chatbot message"""
    try:
        data = request.get_json()
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
        
        # Process message
        response = chatbot.process_message(user_input, user_id)
        
        return jsonify(response)
        
    except Exception as e:
        logger.error(f"Chatbot error: {e}")
        return jsonify({
            'text': "Sorry, I encountered an error. Please try again!",
            'type': 'text',
            'error': str(e)
        }), 500

@chatbot_bp.route('/api/chatbot/suggestions', methods=['GET'])
def chatbot_suggestions():
    """Get suggested questions"""
    suggestions = chatbot.get_suggestions()
    return jsonify({'suggestions': suggestions})

@chatbot_bp.route('/api/chatbot/clear', methods=['POST'])
def clear_chatbot_context():
    """Clear chatbot context for current user"""
    user_id = session.get('user_id')
    if user_id:
        # In a real implementation, you'd clear the context
        pass
    return jsonify({'status': 'context cleared'})