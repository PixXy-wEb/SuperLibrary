#!/usr/bin/env python3
"""
Test script for ML recommendation system
"""
import json
from ml_api import get_recommender
from ml.recommendation_engine import RecommendationEngine

def test_recommendations():
    """Test various recommendation features"""
    print("📚 Testing ML Book Recommendation System")
    print("="*50)
    
    # Get recommender instance
    recommender = get_recommender()
    
    # Test 1: Get popular books
    print("\n1️⃣ Popular Books:")
    popular = recommender.get_popular_books(5)
    for i, book in enumerate(popular, 1):
        print(f"   {i}. {book.get('title', 'Unknown')} by {book.get('author', 'Unknown')}")
    
    # Test 2: Analyze genres
    print("\n2️⃣ Genre Analysis:")
    genre_analysis = recommender.analyze_genres()
    if genre_analysis:
        print(f"   Total books: {genre_analysis.get('total_books', 0)}")
        print(f"   Unique genres: {genre_analysis.get('unique_genres', 0)}")
        print("   Top genres:")
        for genre, count in genre_analysis.get('top_genres', [])[:5]:
            print(f"     - {genre}: {count} books")
    
    # Test 3: Get recommendations for a book (if we have book ID 1)
    print("\n3️⃣ Similar Books (if available):")
    similar = recommender.get_book_recommendations(1, 5)
    if similar:
        for i, book in enumerate(similar, 1):
            title = book.get('title', 'Unknown')
            author = book.get('author', 'Unknown')
            score = book.get('similarity_score', 0)
            print(f"   {i}. {title} by {author} (Score: {score:.2f})")
    else:
        print("   No books found or database is empty")
    
    # Test 4: Personalized recommendations
    print("\n4️⃣ Personalized Recommendations (sample):")
    # Sample user ratings (book_id -> rating 1-5)
    sample_ratings = {
        1: 5.0,  # Liked book 1
        2: 4.5,  # Liked book 2
        3: 1.0,  # Disliked book 3
    }
    
    personalized = recommender.get_personalized_recommendations(sample_ratings, 5)
    if personalized and personalized.get('recommendations'):
        print("   Based on your ratings, you might like:")
        for i, book in enumerate(personalized['recommendations'], 1):
            title = book.get('title', 'Unknown')
            author = book.get('author', 'Unknown')
            score = book.get('recommendation_score', 0)
            print(f"   {i}. {title} by {author} (Score: {score:.2f})")
    
    print("\n✅ ML Recommendation System Test Complete!")
    print("="*50)

if __name__ == "__main__":
    test_recommendations()