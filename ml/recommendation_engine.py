"""
Main recommendation engine combining all ML services
"""
import numpy as np
from typing import List, Dict, Any, Optional, Tuple
import sqlite3
import pickle
import logging
from datetime import datetime

from .engine.embedding_service import EmbeddingService
from .engine.similarity_service import SimilarityService
from .engine.genre_service import GenreService

logger = logging.getLogger(__name__)

class RecommendationEngine:
    def __init__(self, db_path: str = "library.db"):
        """
        Initialize the recommendation engine
        
        Args:
            db_path: Path to SQLite database
        """
        self.db_path = db_path
        self.embedding_service = EmbeddingService(db_path)
        self.similarity_service = SimilarityService(db_path)
        self.genre_service = GenreService()
        
        # User preferences cache
        self.user_preferences = {}
        
    def initialize(self):
        """Initialize the recommendation system"""
        logger.info("Initializing recommendation engine...")
        
        try:
            # Load embedding model
            self.embedding_service.load_model()
            self.embedding_service.load_cache()
            
            # Generate and store embeddings if not exists
            self.embedding_service.update_embeddings_in_db()
            
            logger.info("Recommendation engine initialized successfully")
            return True
            
        except Exception as e:
            logger.error(f"Failed to initialize recommendation engine: {e}")
            return False
    
    def get_book_recommendations(
        self,
        book_id: int,
        top_k: int = 10,
        include_similarity: bool = True
    ) -> List[Dict[str, Any]]:
        """
        Get recommendations for a specific book
        
        Args:
            book_id: ID of the reference book
            top_k: Number of recommendations to return
            include_similarity: Whether to include similarity scores
            
        Returns:
            List of recommended books with details
        """
        # Find similar books
        similar_books = self.similarity_service.find_similar_books(book_id, top_k * 2)
        
        if not similar_books:
            return []
        
        # Get book details from database
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        recommendations = []
        for similar_book_id, similarity in similar_books[:top_k]:
            cursor.execute("""
                SELECT 
                    id, title, author, genre, synopsis, 
                    cover_url, rating, publisher, published_date
                FROM books 
                WHERE id = ?
            """, (similar_book_id,))
            
            book_data = cursor.fetchone()
            if book_data:
                book_dict = dict(book_data)
                
                if include_similarity:
                    book_dict['similarity_score'] = float(similarity)
                    book_dict['match_percentage'] = int(similarity * 100)
                
                recommendations.append(book_dict)
        
        conn.close()
        return recommendations
    
    def get_personalized_recommendations(
        self,
        user_ratings: Dict[int, float],  # book_id -> rating
        top_k: int = 10,
        preferred_genres: Optional[List[str]] = None
    ) -> List[Dict[str, Any]]:
        """
        Get personalized recommendations based on user ratings
        
        Args:
            user_ratings: Dictionary of book IDs and ratings (1-5)
            top_k: Number of recommendations to return
            preferred_genres: User's preferred genres
            
        Returns:
            List of recommended books
        """
        if not user_ratings:
            return self.get_popular_books(top_k)
        
        # Calculate weighted average of liked books
        liked_books = [bid for bid, rating in user_ratings.items() if rating >= 4]
        disliked_books = [bid for bid, rating in user_ratings.items() if rating <= 2]
        
        if not liked_books:
            return self.get_popular_books(top_k)
        
        # Get recommendations based on liked books
        all_recommendations = {}
        
        for liked_book_id in liked_books[:5]:  # Limit to top 5 liked books
            similar_books = self.similarity_service.find_similar_books(
                liked_book_id, 
                top_k * 3,
                min_similarity=0.4
            )
            
            for book_id, similarity in similar_books:
                if book_id in user_ratings:  # Skip books user already rated
                    continue
                
                # Boost score if book is similar to multiple liked books
                current_score = all_recommendations.get(book_id, 0)
                all_recommendations[book_id] = current_score + similarity
        
        # Penalize books similar to disliked books
        for disliked_book_id in disliked_books[:3]:
            similar_books = self.similarity_service.find_similar_books(
                disliked_book_id,
                top_k * 2,
                min_similarity=0.5
            )
            
            for book_id, similarity in similar_books:
                if book_id in all_recommendations:
                    all_recommendations[book_id] -= similarity * 0.5
        
        # Sort by score
        sorted_books = sorted(all_recommendations.items(), key=lambda x: x[1], reverse=True)
        
        # Get book details
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        recommendations = []
        for book_id, score in sorted_books[:top_k]:
            cursor.execute("""
                SELECT 
                    id, title, author, genre, synopsis, 
                    cover_url, rating, publisher, published_date
                FROM books 
                WHERE id = ?
            """, (book_id,))
            
            book_data = cursor.fetchone()
            if book_data:
                book_dict = dict(book_data)
                book_dict['recommendation_score'] = float(score)
                
                # Apply genre preference boost
                if preferred_genres and book_dict.get('genre'):
                    book_genre = book_dict['genre'].lower()
                    for pref_genre in preferred_genres:
                        if pref_genre.lower() in book_genre:
                            book_dict['recommendation_score'] += 0.2
                            book_dict['genre_match'] = True
                            break
                
                recommendations.append(book_dict)
        
        conn.close()
        return recommendations
    
    def get_popular_books(self, top_k: int = 10) -> List[Dict[str, Any]]:
        """Get popular books based on ratings and number of reviews"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT 
                id, title, author, genre, synopsis, 
                cover_url, rating, publisher, published_date
            FROM books 
            WHERE rating >= 4.0
            ORDER BY rating DESC, date_added DESC
            LIMIT ?
        """, (top_k,))
        
        books = [dict(row) for row in cursor.fetchall()]
        conn.close()
        
        return books
    
    def search_similar_books(
        self,
        title: str = "",
        author: str = "",
        genre: str = "",
        synopsis: str = "",
        top_k: int = 10
    ) -> List[Dict[str, Any]]:
        """
        Search for books similar to a description
        
        Args:
            title: Book title
            author: Book author
            genre: Book genre
            synopsis: Book synopsis
            top_k: Number of results to return
            
        Returns:
            List of similar books
        """
        # Find similar books by content
        similar_books = self.similarity_service.find_similar_books_by_content(
            title, author, genre, synopsis, top_k * 2
        )
        
        if not similar_books:
            return []
        
        # Get book details
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        recommendations = []
        for book_id, similarity in similar_books[:top_k]:
            cursor.execute("""
                SELECT 
                    id, title, author, genre, synopsis, 
                    cover_url, rating, publisher, published_date
                FROM books 
                WHERE id = ?
            """, (book_id,))
            
            book_data = cursor.fetchone()
            if book_data:
                book_dict = dict(book_data)
                book_dict['similarity_score'] = float(similarity)
                book_dict['match_percentage'] = int(similarity * 100)
                recommendations.append(book_dict)
        
        conn.close()
        return recommendations
    
    def get_genre_recommendations(self, genre: str, top_k: int = 10) -> List[Dict[str, Any]]:
        """
        Get recommendations for a specific genre
        
        Args:
            genre: Target genre
            top_k: Number of recommendations
            
        Returns:
            List of books in the genre
        """
        # Find books by genre similarity
        genre_books = self.similarity_service.find_books_by_genre(genre, top_k * 2)
        
        if not genre_books:
            # Fallback to database query
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT 
                    id, title, author, genre, synopsis, 
                    cover_url, rating, publisher, published_date
                FROM books 
                WHERE genre LIKE ? OR genre LIKE ?
                ORDER BY rating DESC
                LIMIT ?
            """, (f"%{genre}%", f"%{genre.title()}%", top_k))
            
            books = [dict(row) for row in cursor.fetchall()]
            conn.close()
            return books
        
        # Get book details
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        recommendations = []
        for book_id, similarity in genre_books[:top_k]:
            cursor.execute("""
                SELECT 
                    id, title, author, genre, synopsis, 
                    cover_url, rating, publisher, published_date
                FROM books 
                WHERE id = ?
            """, (book_id,))
            
            book_data = cursor.fetchone()
            if book_data:
                book_dict = dict(book_data)
                book_dict['genre_similarity'] = float(similarity)
                recommendations.append(book_dict)
        
        conn.close()
        return recommendations
    
    def analyze_user_preferences(self, user_ratings: Dict[int, float]) -> Dict[str, Any]:
        """
        Analyze user preferences based on their ratings
        
        Args:
            user_ratings: Dictionary of book IDs and ratings
            
        Returns:
            User preference analysis
        """
        if not user_ratings:
            return {'error': 'No ratings provided'}
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Get book details for rated books
        liked_books = []
        disliked_books = []
        all_genres = []
        all_authors = []
        
        for book_id, rating in user_ratings.items():
            cursor.execute("""
                SELECT title, author, genre, rating
                FROM books WHERE id = ?
            """, (book_id,))
            
            book_data = cursor.fetchone()
            if book_data:
                title, author, genre, book_rating = book_data
                
                if rating >= 4:
                    liked_books.append({
                        'id': book_id,
                        'title': title,
                        'author': author,
                        'genre': genre,
                        'user_rating': rating,
                        'book_rating': book_rating
                    })
                elif rating <= 2:
                    disliked_books.append({
                        'id': book_id,
                        'title': title,
                        'author': author,
                        'genre': genre,
                        'user_rating': rating,
                        'book_rating': book_rating
                    })
                
                if genre:
                    all_genres.append(genre)
                if author:
                    all_authors.append(author)
        
        conn.close()
        
        # Analyze preferences
        from collections import Counter
        
        genre_counter = Counter(all_genres)
        author_counter = Counter(all_authors)
        
        favorite_genres = genre_counter.most_common(3)
        favorite_authors = author_counter.most_common(3)
        
        # Calculate average ratings
        avg_liked_rating = sum(b['book_rating'] for b in liked_books) / len(liked_books) if liked_books else 0
        avg_disliked_rating = sum(b['book_rating'] for b in disliked_books) / len(disliked_books) if disliked_books else 0
        
        return {
            'total_ratings': len(user_ratings),
            'liked_books': len(liked_books),
            'disliked_books': len(disliked_books),
            'favorite_genres': [{'genre': g, 'count': c} for g, c in favorite_genres],
            'favorite_authors': [{'author': a, 'count': c} for a, c in favorite_authors],
            'avg_liked_rating': round(avg_liked_rating, 2),
            'avg_disliked_rating': round(avg_disliked_rating, 2),
            'preferred_genres': [g for g, _ in favorite_genres],
            'preferred_authors': [a for a, _ in favorite_authors]
        }
    
    def cleanup(self):
        """Cleanup resources"""
        self.embedding_service.cleanup()