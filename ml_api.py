"""
API wrapper for the ML recommendation system
"""
import json
import logging
from typing import Dict, List, Any
from ml.recommendation_engine import RecommendationEngine
from ml.chatbot_engine import ChatbotEngine

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class MLBookRecommender:
    def __init__(self, db_path: str = "library.db"):
        self.engine = RecommendationEngine(db_path)
        self.initialized = False
        self.engine.embedding_service

    
    def initialize(self):
        """Initialize the recommendation engine"""
        try:
            self.initialized = self.engine.initialize()
            if self.initialized:
                logger.info("ML Recommender initialized successfully")
            else:
                logger.error("Failed to initialize ML Recommender")
        except Exception as e:
            logger.error(f"Error initializing ML Recommender: {e}")
            self.initialized = False
    
    def get_book_recommendations(self, book_id: int, limit: int = 10) -> List[Dict[str, Any]]:
        """Get recommendations for a specific book"""
        if not self.initialized:
            self.initialize()
        
        try:
            recommendations = self.engine.get_book_recommendations(book_id, limit)
            return recommendations
        except Exception as e:
            logger.error(f"Error getting recommendations for book {book_id}: {e}")
            return []
        
    def get_chatbot(db_path):
        """Factory function to create a ChatbotEngine instance"""
        return ChatbotEngine(db_path)
    
    def get_personalized_recommendations(
        self, 
        user_ratings: Dict[int, float], 
        limit: int = 10
    ) -> Dict[str, Any]:
        """Get personalized recommendations based on user ratings"""
        if not self.initialized:
            self.initialize()
        
        try:
            # Analyze user preferences
            analysis = self.engine.analyze_user_preferences(user_ratings)
            preferred_genres = analysis.get('preferred_genres', [])
            
            # Get personalized recommendations
            recommendations = self.engine.get_personalized_recommendations(
                user_ratings, 
                limit,
                preferred_genres
            )
            
            return {
                'analysis': analysis,
                'recommendations': recommendations
            }
        except Exception as e:
            logger.error(f"Error getting personalized recommendations: {e}")
            return {'analysis': {}, 'recommendations': []}
    
    def search_similar_books(
        self, 
        title: str = "", 
        author: str = "", 
        genre: str = "", 
        synopsis: str = "",
        limit: int = 10
    ) -> List[Dict[str, Any]]:
        """Search for books similar to a description"""
        if not self.initialized:
            self.initialize()
        
        try:
            return self.engine.search_similar_books(
                title, author, genre, synopsis, limit
            )
        except Exception as e:
            logger.error(f"Error searching similar books: {e}")
            return []
    
    def get_genre_recommendations(self, genre: str, limit: int = 10) -> List[Dict[str, Any]]:
        """Get recommendations for a specific genre"""
        if not self.initialized:
            self.initialize()
        
        try:
            return self.engine.get_genre_recommendations(genre, limit)
        except Exception as e:
            logger.error(f"Error getting genre recommendations for {genre}: {e}")
            return []
    
    def get_popular_books(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Get popular books"""
        if not self.initialized:
            self.initialize()
        
        try:
            return self.engine.get_popular_books(limit)
        except Exception as e:
            logger.error(f"Error getting popular books: {e}")
            return []
    
    def analyze_genres(self) -> Dict[str, Any]:
        """Analyze genre distribution in the library"""
        try:
            return self.engine.genre_service.analyze_library_genres(self.engine.db_path)
        except Exception as e:
            logger.error(f"Error analyzing genres: {e}")
            return {}
    
    def update_genres(self) -> Dict[str, Any]:
        """Update book genres using ML classification"""
        try:
            updated = self.engine.genre_service.update_book_genres_in_db(self.engine.db_path)
            return {'updated_count': updated, 'success': True}
        except Exception as e:
            logger.error(f"Error updating genres: {e}")
            return {'updated_count': 0, 'success': False, 'error': str(e)}


# Singleton instance
_recommender_instance = None

def get_recommender(db_path: str = "library.db") -> MLBookRecommender:
    """Get or create the recommender instance"""
    global _recommender_instance
    if _recommender_instance is None:
        _recommender_instance = MLBookRecommender(db_path)
        _recommender_instance.initialize()
    return RecommendationEngine(db_path)