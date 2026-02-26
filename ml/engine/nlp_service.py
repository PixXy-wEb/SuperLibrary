"""
NLP Service for chatbot text processing
"""
import re
import numpy as np
from typing import List, Dict, Any, Optional
from sentence_transformers import SentenceTransformer
from sklearn.metrics.pairwise import cosine_similarity
import logging

logger = logging.getLogger(__name__)

class NLPService:
    def __init__(self):
        self.model = None
        self.intents = self._load_intents()
        self.context_memory = {}  # Store conversation context
        
    def _load_intents(self) -> List[Dict[str, Any]]:
        """Define chatbot intents and responses"""
        return [
            {
                "patterns": ["hello", "hi", "hey", "greetings", "good morning"],
                "responses": ["Hello! How can I help you with books today?", "Hi there! Looking for a good book?"],
                "intent": "greeting"
            },
            {
                "patterns": ["recommend", "suggest", "what should i read", "find me a book"],
                "responses": ["I'd love to recommend some books! What genre are you interested in?", "Tell me what kind of books you like, and I'll suggest some!"],
                "intent": "recommendation"
            },
            {
                "patterns": ["search", "find", "look for", "where can i find"],
                "responses": ["I can help you search for books. What's the title or author you're looking for?"],
                "intent": "search"
            },
            {
                "patterns": ["genre", "type", "category", "what genres"],
                "responses": ["We have books in various genres: Fiction, Fantasy, Sci-Fi, Mystery, Romance, Non-fiction. Which interests you?"],
                "intent": "genres"
            },
            {
                "patterns": ["rate", "rating", "how good", "is it good"],
                "responses": ["I can tell you about book ratings. Which book are you curious about?"],
                "intent": "rating"
            },
            {
                "patterns": ["author", "who wrote", "writer"],
                "responses": ["I can help you find books by specific authors. Which author are you interested in?"],
                "intent": "author"
            },
            {
                "patterns": ["summary", "synopsis", "what is about", "plot"],
                "responses": ["I can give you a summary of any book in our library. Which book would you like to know about?"],
                "intent": "summary"
            },
            {
                "patterns": ["help", "what can you do", "capabilities"],
                "responses": ["I can help you: 🔍 Search for books, 📚 Get recommendations, ⭐ Check ratings, 👨‍💻 Find authors, 📖 Read summaries, 🏷️ Browse by genre"],
                "intent": "help"
            },
            {
                "patterns": ["thanks", "thank you", "appreciate", "bye", "goodbye"],
                "responses": ["You're welcome! Happy reading! 📚", "Glad I could help! Come back anytime!"],
                "intent": "thanks"
            },
            {
                "patterns": ["popular", "trending", "best sellers", "top books"],
                "responses": ["I can show you our most popular books. Would you like to see them?"],
                "intent": "popular"
            },
            {
                "patterns": ["how many books", "library size", "collection"],
                "responses": ["Let me check our library collection for you..."],
                "intent": "library_info"
            }
        ]
    
    def load_model(self):
        """Load the NLP model"""
        if self.model is None:
            logger.info("Loading NLP model...")
            # Using a lightweight model for embeddings
            self.model = SentenceTransformer('all-MiniLM-L6-v2')
            logger.info("NLP model loaded successfully")
    
    def preprocess_text(self, text: str) -> str:
        """Clean and preprocess input text"""
        text = text.lower().strip()
        # Remove special characters but keep spaces
        text = re.sub(r'[^\w\s\?\!\.]', '', text)
        return text
    
    def get_intent(self, user_input: str) -> Dict[str, Any]:
        """Detect user intent using semantic similarity"""
        self.load_model()
        processed_input = self.preprocess_text(user_input)
        
        # If input is too short, use keyword matching
        if len(processed_input.split()) < 2:
            for intent_data in self.intents:
                for pattern in intent_data["patterns"]:
                    if pattern in processed_input:
                        return {
                            "intent": intent_data["intent"],
                            "confidence": 0.9,
                            "patterns": intent_data["patterns"],
                            "responses": intent_data["responses"]
                        }
        
        # Use embedding similarity for longer inputs
        input_embedding = self.model.encode([processed_input])
        
        best_match = None
        highest_similarity = 0
        
        for intent_data in self.intents:
            # Encode all patterns for this intent
            pattern_embeddings = self.model.encode(intent_data["patterns"])
            
            # Calculate similarity with each pattern
            similarities = cosine_similarity(input_embedding, pattern_embeddings)
            max_similarity = np.max(similarities)
            
            if max_similarity > highest_similarity:
                highest_similarity = max_similarity
                best_match = intent_data
        
        if best_match and highest_similarity > 0.3:  # Threshold
            return {
                "intent": best_match["intent"],
                "confidence": float(highest_similarity),
                "patterns": best_match["patterns"],
                "responses": best_match["responses"]
            }
        
        # Default fallback
        return {
            "intent": "unknown",
            "confidence": 0.0,
            "patterns": [],
            "responses": ["I'm not sure I understand. Could you rephrase that?", 
                         "I'm here to help with books! Try asking about recommendations, genres, or searching for books."]
        }
    
    def extract_entities(self, user_input: str, intent: str) -> Dict[str, Any]:
        """Extract key information from user input"""
        entities = {}
        text = user_input.lower()
        
        # Extract genre
        genres = ['fiction', 'fantasy', 'sci-fi', 'science fiction', 'mystery', 
                 'romance', 'thriller', 'horror', 'non-fiction', 'biography', 
                 'history', 'science', 'technology']
        
        for genre in genres:
            if genre in text:
                entities['genre'] = genre
                break
        
        # Extract author names (simple pattern)
        author_keywords = ['by', 'author', 'written by']
        for keyword in author_keywords:
            if keyword in text:
                parts = text.split(keyword)
                if len(parts) > 1:
                    entities['author'] = parts[1].strip()
                    break
        
        # Extract book titles (simple approach)
        quote_matches = re.findall(r'"([^"]*)"', user_input)
        if quote_matches:
            entities['title'] = quote_matches[0]
        
        return entities
    
    def set_context(self, user_id: str, key: str, value: Any):
        """Store conversation context"""
        if user_id not in self.context_memory:
            self.context_memory[user_id] = {}
        self.context_memory[user_id][key] = value
    
    def get_context(self, user_id: str, key: str) -> Optional[Any]:
        """Retrieve conversation context"""
        return self.context_memory.get(user_id, {}).get(key)