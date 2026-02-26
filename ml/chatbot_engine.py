"""
Main chatbot engine integrating NLP with book data
"""
import sqlite3
import random
from typing import Dict, Any, List, Optional
import logging
from datetime import datetime

from .engine.nlp_service import NLPService
from .recommendation_engine import RecommendationEngine

logger = logging.getLogger(__name__)

class ChatbotEngine:
    def __init__(self, db_path: str = "library.db"):
        self.db_path = db_path
        self.nlp_service = NLPService()
        self.recommender = RecommendationEngine(db_path)
        
    def process_message(self, user_input: str, user_id: str = "default") -> Dict[str, Any]:
        """
        Process user message and generate response
        
        Args:
            user_input: User's message
            user_id: Unique user identifier for context
            
        Returns:
            Dictionary with response and metadata
        """
        logger.info(f"Processing message from {user_id}: {user_input}")
        
        # Get intent and entities
        intent_data = self.nlp_service.get_intent(user_input)
        entities = self.nlp_service.extract_entities(user_input, intent_data["intent"])
        
        # Generate response based on intent
        response_data = self._generate_response(intent_data, entities, user_id, user_input)
        
        # Add metadata
        response_data.update({
            "intent": intent_data["intent"],
            "confidence": intent_data["confidence"],
            "entities": entities,
            "timestamp": datetime.now().isoformat()
        })
        
        return response_data
    
    def _generate_response(self, intent_data: Dict[str, Any], 
                          entities: Dict[str, Any], 
                          user_id: str,
                          original_input: str) -> Dict[str, Any]:
        """Generate appropriate response based on intent"""
        intent = intent_data["intent"]
        
        # Get a random base response
        base_response = random.choice(intent_data["responses"])
        
        response_data = {
            "text": base_response,
            "type": "text",
            "suggestions": [],
            "books": []
        }
        
        # Handle specific intents with database queries
        if intent == "greeting":
            # Add personalized greeting if we have user context
            name = self.nlp_service.get_context(user_id, "name")
            if name:
                response_data["text"] = f"Hello {name}! {base_response}"
        
        elif intent == "recommendation":
            genre = entities.get('genre')
            if genre:
                # Get recommendations for this genre
                books = self.recommender.get_genre_recommendations(genre, top_k=3)
                if books:
                    response_data["text"] = f"Here are some {genre} books you might enjoy:"
                    response_data["books"] = books
                    response_data["type"] = "book_list"
                    
                    # Add genre to context
                    self.nlp_service.set_context(user_id, "last_genre", genre)
                else:
                    response_data["text"] = f"I couldn't find any {genre} books in our library. Try another genre!"
            else:
                # Ask for genre preference
                response_data["suggestions"] = ["Fiction", "Fantasy", "Mystery", "Sci-Fi", "Romance"]
        
        elif intent == "search":
            title = entities.get('title')
            author = entities.get('author')
            
            if title or author:
                results = self._search_books(title, author)
                if results:
                    response_data["text"] = f"I found {len(results)} book(s):"
                    response_data["books"] = results[:5]  # Limit to 5
                    response_data["type"] = "book_list"
                else:
                    response_data["text"] = "I couldn't find any books matching your search."
            else:
                response_data["text"] = "What would you like to search for? Tell me a book title or author name."
        
        elif intent == "genres":
            # Get all unique genres from database
            genres = self._get_all_genres()
            if genres:
                response_data["text"] = f"We have books in these genres: {', '.join(genres[:10])}"
                response_data["suggestions"] = genres[:5]
        
        elif intent == "rating":
            # Extract book title from context or entities
            book_title = entities.get('title') or self.nlp_service.get_context(user_id, "last_book")
            if book_title:
                rating = self._get_book_rating(book_title)
                if rating:
                    response_data["text"] = f"'{book_title}' has a rating of {rating}/5 ⭐"
                else:
                    response_data["text"] = f"I couldn't find rating information for '{book_title}'."
            else:
                response_data["text"] = "Which book's rating would you like to know?"
        
        elif intent == "popular":
            popular_books = self.recommender.get_popular_books(top_k=5)
            if popular_books:
                response_data["text"] = "Here are our most popular books:"
                response_data["books"] = popular_books
                response_data["type"] = "book_list"
        
        elif intent == "library_info":
            stats = self._get_library_stats()
            response_data["text"] = f"Our library has {stats['total_books']} books across {stats['total_genres']} genres. The average rating is {stats['avg_rating']:.1f}/5."
        
        elif intent == "author":
            author = entities.get('author')
            if author:
                books = self._get_books_by_author(author)
                if books:
                    response_data["text"] = f"Books by {author}:"
                    response_data["books"] = books[:5]
                    response_data["type"] = "book_list"
                else:
                    response_data["text"] = f"I couldn't find any books by {author}."
            else:
                response_data["text"] = "Which author are you looking for?"
        
        elif intent == "summary":
            book_title = entities.get('title')
            if book_title:
                summary = self._get_book_summary(book_title)
                if summary:
                    response_data["text"] = f"Summary of '{book_title}':\n\n{summary[:300]}..."
                    if len(summary) > 300:
                        response_data["text"] += "\n\n[Ask for more details if you want!]"
                else:
                    response_data["text"] = f"I don't have a summary for '{book_title}' yet."
            else:
                response_data["text"] = "Which book would you like a summary of?"
        
        return response_data
    
    def _search_books(self, title: Optional[str] = None, author: Optional[str] = None) -> List[Dict[str, Any]]:
        """Search books in database"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        query = "SELECT id, title, author, genre, synopsis, rating FROM books WHERE 1=1"
        params = []
        
        if title:
            query += " AND title LIKE ?"
            params.append(f"%{title}%")
        
        if author:
            query += " AND author LIKE ?"
            params.append(f"%{author}%")
        
        query += " LIMIT 10"
        
        cursor.execute(query, params)
        results = [dict(row) for row in cursor.fetchall()]
        conn.close()
        
        return results
    
    def _get_all_genres(self) -> List[str]:
        """Get all unique genres from database"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("SELECT DISTINCT genre FROM books WHERE genre IS NOT NULL AND genre != ''")
        genres = [row[0] for row in cursor.fetchall() if row[0]]
        conn.close()
        
        return sorted(genres)
    
    def _get_book_rating(self, book_title: str) -> Optional[float]:
        """Get book rating by title"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("SELECT rating FROM books WHERE title LIKE ?", (f"%{book_title}%",))
        result = cursor.fetchone()
        conn.close()
        
        return result[0] if result else None
    
    def _get_library_stats(self) -> Dict[str, Any]:
        """Get library statistics"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("SELECT COUNT(*) FROM books")
        total_books = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(DISTINCT genre) FROM books WHERE genre IS NOT NULL")
        total_genres = cursor.fetchone()[0]
        
        cursor.execute("SELECT AVG(rating) FROM books WHERE rating IS NOT NULL")
        avg_rating = cursor.fetchone()[0] or 0
        
        conn.close()
        
        return {
            "total_books": total_books,
            "total_genres": total_genres,
            "avg_rating": avg_rating
        }
    
    def _get_books_by_author(self, author: str) -> List[Dict[str, Any]]:
        """Get books by author"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT id, title, author, genre, rating 
            FROM books 
            WHERE author LIKE ? 
            ORDER BY rating DESC 
            LIMIT 10
        """, (f"%{author}%",))
        
        results = [dict(row) for row in cursor.fetchall()]
        conn.close()
        
        return results
    
    def _get_book_summary(self, book_title: str) -> Optional[str]:
        """Get book summary/synopsis"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("SELECT synopsis FROM books WHERE title LIKE ?", (f"%{book_title}%",))
        result = cursor.fetchone()
        conn.close()
        
        return result[0] if result else None
    
    def get_suggestions(self) -> List[str]:
        """Get suggested questions for the user"""
        return [
            "Recommend a fantasy book",
            "Search for books by Stephen King",
            "What are the top rated books?",
            "Tell me about mystery books",
            "How many books are in the library?",
            "Get a book summary"
        ]