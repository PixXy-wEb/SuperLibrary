"""
Service for generating embeddings from book data
"""
import numpy as np
from typing import List, Dict, Any, Optional
import pickle
import os
import sqlite3
from sentence_transformers import SentenceTransformer
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

class EmbeddingService:
    def __init__(self, db_path: str = "library.db"):
        """
        Initialize the embedding service
        
        Args:
            db_path: Path to SQLite database
        """
        self.db_path = db_path
        self.model_name = "all-MiniLM-L6-v2"  # Lightweight model
        self.model = None
        self.embeddings_cache = {}
        self.cache_file = "book_embeddings_cache.pkl"
        
    def load_model(self):
        """Load the embedding model"""
        if self.model is None:
            logger.info(f"Loading embedding model: {self.model_name}")
            self.model = SentenceTransformer(self.model_name)
            logger.info("Embedding model loaded successfully")
    
    def load_cache(self):
        """Load embeddings cache from disk"""
        if os.path.exists(self.cache_file):
            try:
                with open(self.cache_file, 'rb') as f:
                    self.embeddings_cache = pickle.load(f)
                logger.info(f"Loaded embeddings cache with {len(self.embeddings_cache)} entries")
            except Exception as e:
                logger.warning(f"Failed to load cache: {e}")
    
    def save_cache(self):
        """Save embeddings cache to disk"""
        try:
            with open(self.cache_file, 'wb') as f:
                pickle.dump(self.embeddings_cache, f)
            logger.info(f"Saved embeddings cache with {len(self.embeddings_cache)} entries")
        except Exception as e:
            logger.error(f"Failed to save cache: {e}")
    
    def get_book_embedding_key(self, book_data: Dict[str, Any]) -> str:
        """Generate a unique key for book embedding cache"""
        title = book_data.get('title', '')
        author = book_data.get('author', '')
        description = book_data.get('synopsis', '')[:100]  # First 100 chars of synopsis
        return f"{title}_{author}_{hash(description)}"
    
    def generate_book_embedding(self, book_data: Dict[str, Any]) -> np.ndarray:
        """
        Generate embedding for a book based on its metadata
        
        Args:
            book_data: Dictionary containing book information from your database
            
        Returns:
            numpy array with embedding
        """
        self.load_model()
        
        # Check cache first
        cache_key = self.get_book_embedding_key(book_data)
        if cache_key in self.embeddings_cache:
            return self.embeddings_cache[cache_key]
        
        # Prepare text for embedding
        texts = []
        
        # Add title
        title = book_data.get('title', '')
        if title:
            texts.append(f"Title: {title}")
        
        # Add author
        author = book_data.get('author', '')
        if author:
            texts.append(f"Author: {author}")
        
        # Add synopsis (from your database)
        synopsis = book_data.get('synopsis', '')
        if synopsis:
            # Clean synopsis
            clean_synopsis = synopsis[:500]  # Limit length
            texts.append(f"Synopsis: {clean_synopsis}")
        
        # Add genre
        genre = book_data.get('genre', '')
        if genre:
            texts.append(f"Genre: {genre}")
        
        # Combine all texts
        combined_text = " ".join(texts)
        
        # Generate embedding
        if combined_text.strip():
            embedding = self.model.encode(combined_text)
        else:
            # Fallback: use zeros
            embedding = np.zeros(384)  # Default dimension for MiniLM
        
        # Cache the embedding
        self.embeddings_cache[cache_key] = embedding
        
        return embedding
    
    def get_all_books_from_db(self) -> List[Dict[str, Any]]:
        """Get all books from your SQLite database"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT id, title, author, synopsis, genre, rating, isbn, publisher, published_date
            FROM books
            WHERE synopsis IS NOT NULL AND synopsis != ''
        """)
        
        books = []
        for row in cursor.fetchall():
            book_data = dict(row)
            books.append(book_data)
        
        conn.close()
        return books
    
    def generate_all_book_embeddings(self) -> Dict[int, np.ndarray]:
        """
        Generate embeddings for all books in database
        
        Returns:
            Dictionary mapping book_id -> embedding
        """
        books = self.get_all_books_from_db()
        book_embeddings = {}
        
        logger.info(f"Generating embeddings for {len(books)} books...")
        
        for i, book in enumerate(books):
            try:
                embedding = self.generate_book_embedding(book)
                book_id = book['id']
                book_embeddings[book_id] = embedding
                
                if i % 10 == 0:
                    logger.info(f"Processed {i}/{len(books)} books")
                    
            except Exception as e:
                logger.error(f"Error generating embedding for book {book.get('id')}: {e}")
        
        # Save cache after generating all embeddings
        self.save_cache()
        
        return book_embeddings
    
    def get_embedding_dimension(self) -> int:
        """Get the dimension of embeddings"""
        self.load_model()
        return self.model.get_sentence_embedding_dimension()
    
    def update_embeddings_in_db(self):
        """Update database with embeddings for all books"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Check if embeddings table exists
        cursor.execute("""
            SELECT name FROM sqlite_master 
            WHERE type='table' AND name='book_embeddings'
        """)
        
        if not cursor.fetchone():
            # Create embeddings table
            cursor.execute("""
                CREATE TABLE book_embeddings (
                    book_id INTEGER PRIMARY KEY,
                    embedding BLOB,
                    last_updated TEXT,
                    FOREIGN KEY (book_id) REFERENCES books(id)
                )
            """)
            logger.info("Created book_embeddings table")
        
        # Generate embeddings for all books
        book_embeddings = self.generate_all_book_embeddings()
        
        # Insert/update embeddings in database
        for book_id, embedding in book_embeddings.items():
            # Convert numpy array to bytes
            embedding_bytes = pickle.dumps(embedding)
            last_updated = datetime.now().isoformat()
            
            cursor.execute("""
                INSERT OR REPLACE INTO book_embeddings (book_id, embedding, last_updated)
                VALUES (?, ?, ?)
            """, (book_id, embedding_bytes, last_updated))
        
        conn.commit()
        conn.close()
        
        logger.info(f"Updated embeddings for {len(book_embeddings)} books in database")

    
    def get_book_embedding_from_db(self, book_id: int) -> Optional[np.ndarray]:
        """Get book embedding from database"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT embedding FROM book_embeddings WHERE book_id = ?
        """, (book_id,))
        
        result = cursor.fetchone()
        conn.close()
        
        if result and result[0]:
            return pickle.loads(result[0])
        return None
    
    def cleanup(self):
        """Cleanup resources"""
        self.save_cache()