from flask import Blueprint, request, jsonify
import logging

# FIX: Remove the relative import
# Instead, import the function directly or define it here

logger = logging.getLogger(__name__)

pdf_bp = Blueprint('pdf', __name__)

# You have two options:

# OPTION 1: Move the get_book_pdf function here directly
def get_book_pdf(title, author):
    """Your PDF search function - copy it here or import it differently"""
    import urllib.parse
    import requests
    from bs4 import BeautifulSoup
    
    # Build the link
    query = f"{title} {author}"
    encoded_query = urllib.parse.quote(query)
    search_url = f"https://www.google.com/search?q={encoded_query}"
    
    # Add headers
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
    }
    
    # Fetch search results page
    response = requests.get(search_url, headers=headers)
    if response.status_code != 200:
        return None
    
    # Parse HTML
    soup = BeautifulSoup(response.text, 'html.parser')
    
    # Look for PDF links
    for link in soup.find_all('a', href=True):
        href = link['href']
        if 'pdf' in href.lower() and 'google' not in href.lower():
            if 'url=' in href:
                # Extract URL from Google redirect
                start = href.find('url=') + 4
                end = href.find('&', start)
                pdf_url = href[start:end] if end != -1 else href[start:]
                import urllib.parse
                pdf_url = urllib.parse.unquote(pdf_url)
                return pdf_url
    
    return None

def get_book_pdf_api(title, author):
    """Flask-friendly wrapper"""
    try:
        pdf_url = get_book_pdf(title, author)
        
        if pdf_url:
            return {
                "status": "success",
                "pdf_url": pdf_url,
                "message": f"Found PDF for '{title}' by {author}"
            }
        else:
            return {
                "status": "not_found",
                "pdf_url": None,
                "message": f"No PDF found for '{title}' by {author}"
            }
    except Exception as e:
        return {
            "status": "error",
            "pdf_url": None,
            "message": f"Error: {str(e)}"
        }


# OPTION 2: If you have the function in a separate file, import it like this:
# from book_library import get_book_pdf  # If it's in book_library.py
# OR
# from pdf_finder import get_book_pdf   # If it's in pdf_finder.py

@pdf_bp.route('/api/books/search-pdf', methods=['GET', 'POST'])
def search_pdf():
    """
    Search for book PDF
    
    GET or POST with JSON: {"title": "Book Title", "author": "Author Name"}
    """
    try:
        if request.method == 'GET':
            title = request.args.get('title', '').strip()
            author = request.args.get('author', '').strip()
        else:  # POST
            data = request.get_json()
            if not data:
                return jsonify({
                    "status": "error",
                    "message": "No JSON data provided"
                }), 400
            title = data.get('title', '').strip()
            author = data.get('author', '').strip()
        
        if not title or not author:
            return jsonify({
                "status": "error",
                "message": "Both title and author are required"
            }), 400
        
        logger.info(f"Searching PDF for: '{title}' by {author}")
        
        result = get_book_pdf_api(title, author)
        
        return jsonify(result)
        
    except Exception as e:
        logger.error(f"PDF search endpoint error: {e}")
        return jsonify({
            "status": "error",
            "message": f"Server error: {str(e)}"
        }), 500


@pdf_bp.route('/api/books/<int:book_id>/pdf', methods=['GET'])
def get_book_pdf_by_id(book_id):
    """
    Get PDF for a specific book by ID
    Requires database lookup first
    """
    try:
        # Import your database function
        # Assuming you have a BookLibrary class in book_library.py
        from book_library import BookLibrary
        
        library = BookLibrary()
        book = library.view_book_details(book_id)
        
        if not book:
            return jsonify({
                "status": "error",
                "message": f"Book with ID {book_id} not found"
            }), 404
        
        # Search for PDF
        result = get_book_pdf_api(book.get('title'), book.get('author'))
        
        return jsonify(result)
        
    except Exception as e:
        logger.error(f"Error getting PDF for book {book_id}: {e}")
        return jsonify({
            "status": "error",
            "message": f"Server error: {str(e)}"
        }), 500