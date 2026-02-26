"""
Service for calculating similarity between book embeddings
"""
import numpy as np
from typing import List, Tuple, Dict, Any, Optional
import sqlite3
import pickle
from sklearn.metrics.pairwise import cosine_similarity
from scipy.spatial.distance import euclidean
import logging
from .genre_service import GenreService

logger = logging.getLogger(__name__)

class SimilarityService:
    def __init__(self, db_path: str = "library.db"):
        """Initialize similarity service"""
        self.db_path = db_path
        
    def cosine_similarity(self, embedding1: np.ndarray, embedding2: np.ndarray) -> float:
        """
        Calculate cosine similarity between two embeddings
        
        Args:
            embedding1: First embedding vector
            embedding2: Second embedding vector
            
        Returns:
            Similarity score between -1 and 1
        """
        if embedding1.shape != embedding2.shape:
            raise ValueError(f"Embedding shapes don't match: {embedding1.shape} vs {embedding2.shape}")
        
        # Reshape for sklearn
        emb1_2d = embedding1.reshape(1, -1)
        emb2_2d = embedding2.reshape(1, -1)
        
        return cosine_similarity(emb1_2d, emb2_2d)[0][0]
    
    def get_all_book_embeddings(self) -> Tuple[List[int], List[np.ndarray]]:
        """Get all book embeddings from database"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT book_id, embedding FROM book_embeddings
        """)
        
        book_ids = []
        embeddings = []
        
        for book_id, embedding_bytes in cursor.fetchall():
            if embedding_bytes:
                try:
                    embedding = pickle.loads(embedding_bytes)
                    book_ids.append(book_id)
                    embeddings.append(embedding)
                except Exception as e:
                    logger.error(f"Error loading embedding for book {book_id}: {e}")
        
        conn.close()
        return book_ids, embeddings
    
    def find_similar_books(
        self,
        book_id: int,
        top_k: int = 10,
        min_similarity: float = 0.3
    ) -> List[Tuple[int, float]]:
        """
        Find books similar to a given book
        
        Args:
            book_id: ID of the reference book
            top_k: Number of similar books to return
            min_similarity: Minimum similarity threshold
            
        Returns:
            List of (book_id, similarity_score) tuples
        """
        # Get all embeddings
        all_book_ids, all_embeddings = self.get_all_book_embeddings()
        
        if not all_embeddings:
            return []
        
        # Find the reference book's index
        try:
            ref_index = all_book_ids.index(book_id)
            ref_embedding = all_embeddings[ref_index]
        except ValueError:
            logger.error(f"Book {book_id} not found in embeddings")
            return []
        
        # Calculate similarities
        similarities = []
        ref_2d = ref_embedding.reshape(1, -1)
        all_2d = np.array(all_embeddings)
        
        # Batch similarity calculation
        sim_scores = cosine_similarity(ref_2d, all_2d)[0]
        
        # Create list of (book_id, similarity) excluding the reference book
        for i, sim_score in enumerate(sim_scores):
            if i != ref_index and sim_score >= min_similarity:
                similarities.append((all_book_ids[i], float(sim_score)))
        
        # Sort by similarity (descending)
        similarities.sort(key=lambda x: x[1], reverse=True)
        
        # Return top K
        return similarities[:top_k]
    
    def find_similar_books_by_content(
        self,
        title: str = "",
        author: str = "",
        genre: str = "",
        synopsis: str = "",
        top_k: int = 10
    ) -> List[Tuple[int, float]]:
        """
        Find books similar to a text description
        
        Args:
            title: Book title
            author: Book author
            genre: Book genre
            synopsis: Book synopsis
            top_k: Number of similar books to return
            
        Returns:
            List of (book_id, similarity_score) tuples
        """
        from .embedding_service import EmbeddingService
        
        # Create text for embedding
        texts = []
        if title:
            texts.append(f"Title: {title}")
        if author:
            texts.append(f"Author: {author}")
        if genre:
            texts.append(f"Genre: {genre}")
        if synopsis:
            texts.append(f"Synopsis: {synopsis[:500]}")
        
        if not texts:
            return []
        
        combined_text = " ".join(texts)
        
        # Generate embedding for the query
        embedding_service = EmbeddingService()
        embedding_service.load_model()
        query_embedding = embedding_service.model.encode(combined_text)
        
        # Get all book embeddings
        all_book_ids, all_embeddings = self.get_all_book_embeddings()
        
        if not all_embeddings:
            return []
        
        # Calculate similarities
        similarities = []
        query_2d = query_embedding.reshape(1, -1)
        all_2d = np.array(all_embeddings)
        
        # Batch similarity calculation
        sim_scores = cosine_similarity(query_2d, all_2d)[0]
        
        # Create list of (book_id, similarity)
        for i, sim_score in enumerate(sim_scores):
            similarities.append((all_book_ids[i], float(sim_score)))
        
        # Sort by similarity (descending)
        similarities.sort(key=lambda x: x[1], reverse=True)
        
        # Return top K
        return similarities[:top_k]
    
    def get_similarity_matrix(self) -> Optional[Dict[str, Any]]:
        """
        Build similarity matrix for all books
        
        Returns:
            Dictionary with matrix and book IDs
        """
        book_ids, embeddings = self.get_all_book_embeddings()
        
        if not embeddings:
            return None
        
        # Convert to numpy array
        embeddings_array = np.array(embeddings)
        
        # Calculate similarity matrix
        similarity_matrix = cosine_similarity(embeddings_array)
        
        return {
            'book_ids': book_ids,
            'similarity_matrix': similarity_matrix,
            'num_books': len(book_ids)
        }
    
    def find_books_by_genre(self, genre: str, top_k: int = 10) -> List[Tuple[int, float]]:
        """
        Find books by genre using similarity
        
        Args:
            genre: Target genre
            top_k: Number of books to return
            
        Returns:
            List of (book_id, genre_similarity) tuples
        """
        
        
        genre_service = GenreService()
        all_book_ids, all_embeddings = self.get_all_book_embeddings()
        
        if not all_embeddings:
            return []
        
        # Get genre embedding
        genre_embedding = genre_service.get_genre_embedding(genre)
        if genre_embedding is None:
            return []
        
        # Calculate similarities
        similarities = []
        genre_2d = genre_embedding.reshape(1, -1)
        all_2d = np.array(all_embeddings)
        
        # Batch similarity calculation
        sim_scores = cosine_similarity(genre_2d, all_2d)[0]
        
        # Create list of (book_id, similarity)
        for i, sim_score in enumerate(sim_scores):
            similarities.append((all_book_ids[i], float(sim_score)))
        
        # Sort by similarity (descending)
        similarities.sort(key=lambda x: x[1], reverse=True)
        
        # Return top K
        return similarities[:top_k]