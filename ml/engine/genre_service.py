"""
Service for genre analysis and classification
"""
import re
import numpy as np
from typing import List, Dict, Any, Tuple, Optional
from collections import Counter
import sqlite3
import logging
from sentence_transformers import SentenceTransformer

logger = logging.getLogger(__name__)

class GenreService:
    def __init__(self):
        """Initialize genre service"""
        # Common genre mappings
        self.genre_categories = {
            'fiction': ['fiction', 'novel', 'story', 'literature', 'prose'],
            'non_fiction': ['non-fiction', 'biography', 'memoir', 'autobiography', 'history', 'science'],
            'fantasy': ['fantasy', 'magic', 'dragon', 'wizard', 'mythical', 'epic', 'quest'],
            'science_fiction': ['science fiction', 'sci-fi', 'space', 'future', 'alien', 'cyberpunk', 'dystopian'],
            'mystery': ['mystery', 'crime', 'detective', 'thriller', 'suspense', 'noir', 'whodunit'],
            'romance': ['romance', 'love', 'relationship', 'dating', 'wedding', 'passion'],
            'horror': ['horror', 'terror', 'ghost', 'haunted', 'supernatural', 'paranormal'],
            'young_adult': ['young adult', 'ya', 'teen', 'adolescent', 'coming of age'],
            'classic': ['classic', 'literature', 'canonical', 'masterpiece'],
            'poetry': ['poetry', 'poem', 'verse', 'rhyme', 'sonnet'],
            'drama': ['drama', 'play', 'theater', 'tragedy', 'comedy', 'stage'],
            'comedy': ['comedy', 'humor', 'funny', 'satire', 'parody', 'wit'],
            'adventure': ['adventure', 'action', 'journey', 'expedition', 'quest', 'exploration'],
            'historical': ['historical', 'history', 'period', 'era', 'ancient', 'medieval'],
            'self_help': ['self-help', 'self improvement', 'motivational', 'inspirational', 'personal growth'],
            'biography': ['biography', 'memoir', 'autobiography', 'life story', 'diary'],
            'cooking': ['cooking', 'recipe', 'culinary', 'food', 'gastronomy'],
            'travel': ['travel', 'guide', 'journey', 'exploration', 'destination'],
            'business': ['business', 'economics', 'finance', 'management', 'entrepreneurship']
        }
        
        # Genre model for embeddings
        self.genre_model = None
        self.genre_embeddings_cache = {}
    
    def load_genre_model(self):
        """Load genre embedding model"""
        if self.genre_model is None:
            # Use a smaller model for genre embeddings
            self.genre_model = SentenceTransformer('all-MiniLM-L6-v2')
    
    def get_genre_embedding(self, genre: str) -> Optional[np.ndarray]:
        """Get embedding for a genre"""
        self.load_genre_model()
        
        if genre in self.genre_embeddings_cache:
            return self.genre_embeddings_cache[genre]
        
        try:
            embedding = self.genre_model.encode(genre)
            self.genre_embeddings_cache[genre] = embedding
            return embedding
        except Exception as e:
            logger.error(f"Error generating embedding for genre '{genre}': {e}")
            return None
    
    def extract_genres_from_text(self, text: str, max_genres: int = 3) -> List[str]:
        """
        Extract genres from text
        
        Args:
            text: Text to analyze
            max_genres: Maximum number of genres to return
            
        Returns:
            List of detected genres
        """
        if not text:
            return []
        
        text_lower = text.lower()
        genre_scores = {}
        
        # Score each genre category based on keyword matches
        for category, keywords in self.genre_categories.items():
            score = 0
            for keyword in keywords:
                # Count exact word matches
                pattern = r'\b' + re.escape(keyword) + r'\b'
                matches = re.findall(pattern, text_lower)
                score += len(matches)
            
            if score > 0:
                genre_scores[category] = score
        
        # Sort genres by score
        sorted_genres = sorted(genre_scores.items(), key=lambda x: x[1], reverse=True)
        return [genre for genre, _ in sorted_genres[:max_genres]]
    
    def classify_book(self, book_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Classify a book into genres
        
        Args:
            book_data: Book information from your database
            
        Returns:
            Dictionary with classification results
        """
        # Combine text from different fields
        text_parts = []
        
        title = book_data.get('title', '')
        if title:
            text_parts.append(title)
        
        synopsis = book_data.get('synopsis', '')
        if synopsis:
            text_parts.append(synopsis)
        
        existing_genre = book_data.get('genre', '')
        if existing_genre:
            text_parts.append(existing_genre)
        
        combined_text = " ".join(text_parts)
        
        # Extract genres
        detected_genres = self.extract_genres_from_text(combined_text)
        
        # Get confidence scores
        confidence_scores = {}
        text_lower = combined_text.lower()
        
        for genre in detected_genres:
            keywords = self.genre_categories.get(genre, [])
            matches = 0
            
            for keyword in keywords:
                if re.search(r'\b' + re.escape(keyword) + r'\b', text_lower):
                    matches += 1
            
            if keywords:
                confidence_scores[genre] = matches / len(keywords)
            else:
                confidence_scores[genre] = 0.0
        
        # Format results
        primary_genre = detected_genres[0] if detected_genres else 'unknown'
        
        return {
            'primary_genre': primary_genre,
            'all_genres': detected_genres,
            'confidence_scores': confidence_scores,
            'suggested_genre': self.format_genre_name(primary_genre)
        }
    
    def format_genre_name(self, genre: str) -> str:
        """Format genre string for display"""
        return genre.replace('_', ' ').title()
    
    def analyze_library_genres(self, db_path: str = "library.db") -> Dict[str, Any]:
        """
        Analyze genre distribution in the library
        
        Args:
            db_path: Path to SQLite database
            
        Returns:
            Dictionary with analysis results
        """
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        # Get all books with their data
        cursor.execute("""
            SELECT id, title, author, synopsis, genre, rating
            FROM books
            WHERE synopsis IS NOT NULL AND synopsis != ''
        """)
        
        books = [dict(row) for row in cursor.fetchall()]
        conn.close()
        
        if not books:
            return {'total_books': 0, 'genre_distribution': {}}
        
        # Classify each book
        genre_counter = Counter()
        genre_ratings = {}
        
        for book in books:
            classification = self.classify_book(book)
            genres = classification.get('all_genres', [])
            
            for genre in genres:
                genre_counter[genre] += 1
                
                # Track average rating per genre
                rating = book.get('rating', 0)
                if genre not in genre_ratings:
                    genre_ratings[genre] = {'total': 0, 'count': 0}
                
                if rating > 0:
                    genre_ratings[genre]['total'] += rating
                    genre_ratings[genre]['count'] += 1
        
        # Calculate average rating per genre
        avg_rating_by_genre = {}
        for genre, data in genre_ratings.items():
            if data['count'] > 0:
                avg_rating_by_genre[genre] = data['total'] / data['count']
        
        # Get top genres
        total_books = len(books)
        top_genres = genre_counter.most_common(10)
        
        return {
            'total_books': total_books,
            'total_with_synopsis': len([b for b in books if b.get('synopsis')]),
            'genre_distribution': dict(genre_counter),
            'top_genres': top_genres,
            'avg_rating_by_genre': avg_rating_by_genre,
            'unique_genres': len(genre_counter)
        }
    
    def suggest_genre_for_book(self, book_id: int, db_path: str = "library.db") -> Dict[str, Any]:
        """
        Suggest genre for a specific book
        
        Args:
            book_id: Book ID
            db_path: Path to SQLite database
            
        Returns:
            Genre suggestion with confidence
        """
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT title, synopsis, genre
            FROM books WHERE id = ?
        """, (book_id,))
        
        book = cursor.fetchone()
        conn.close()
        
        if not book:
            return {'error': 'Book not found'}
        
        book_data = dict(book)
        classification = self.classify_book(book_data)
        
        # If book already has a genre, compare with our suggestion
        existing_genre = book_data.get('genre', '')
        suggested_genre = classification['suggested_genre']
        
        result = {
            'book_id': book_id,
            'title': book_data.get('title'),
            'existing_genre': existing_genre,
            'suggested_genre': suggested_genre,
            'all_suggestions': [self.format_genre_name(g) for g in classification['all_genres']],
            'confidence_scores': classification['confidence_scores']
        }
        
        # Check if suggestion matches existing
        if existing_genre and suggested_genre.lower() in existing_genre.lower():
            result['match'] = True
        else:
            result['match'] = False
        
        return result
    
    def find_similar_genres(self, target_genre: str, top_n: int = 5) -> List[Tuple[str, float]]:
        """
        Find genres similar to target genre
        
        Args:
            target_genre: Target genre to find similarities for
            top_n: Number of similar genres to return
            
        Returns:
            List of (genre, similarity_score) tuples
        """
        self.load_genre_model()
        
        target_embedding = self.get_genre_embedding(target_genre)
        if target_embedding is None:
            return []
        
        similarities = []
        
        for genre in self.genre_categories.keys():
            if genre == target_genre:
                continue
            
            genre_embedding = self.get_genre_embedding(genre)
            if genre_embedding is not None:
                # Calculate cosine similarity
                target_2d = target_embedding.reshape(1, -1)
                genre_2d = genre_embedding.reshape(1, -1)
                
                similarity = float(np.dot(target_embedding, genre_embedding) / 
                                 (np.linalg.norm(target_embedding) * np.linalg.norm(genre_embedding)))
                
                similarities.append((self.format_genre_name(genre), similarity))
        
        # Sort by similarity and return top N
        similarities.sort(key=lambda x: x[1], reverse=True)
        return similarities[:top_n]
    
    def update_book_genres_in_db(self, db_path: str = "library.db"):
        """
        Update book genres in database based on ML classification
        
        Args:
            db_path: Path to SQLite database
        """
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Get all books
        cursor.execute("SELECT id, title, synopsis FROM books")
        books = cursor.fetchall()
        
        updated_count = 0
        for book_id, title, synopsis in books:
            if not synopsis:
                continue
            
            book_data = {'title': title, 'synopsis': synopsis}
            classification = self.classify_book(book_data)
            
            # Get suggested genre
            suggested_genre = classification.get('suggested_genre', '')
            
            if suggested_genre:
                # Update the book's genre in database
                cursor.execute("""
                    UPDATE books SET genre = COALESCE(?, genre)
                    WHERE id = ?
                """, (suggested_genre, book_id))
                
                updated_count += 1
        
        conn.commit()
        conn.close()
        
        logger.info(f"Updated genres for {updated_count} books")
        return updated_count