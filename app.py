from flask import Flask, flash, request, jsonify, render_template, redirect, url_for, send_file
from book_library import BookLibrary
from ml_api import get_recommender
from chatbot import chatbot_bp
import urllib.parse
import requests
from bs4 import BeautifulSoup
import os
import tempfile
import logging
import re
import json
import os
import tempfile
from datetime import datetime
from werkzeug.utils import secure_filename
from typing import Dict, Any, Optional
import time
import threading
from concurrent.futures import ThreadPoolExecutor

logger = logging.getLogger(__name__)

# Initialize
recommender = get_recommender("library.db")
app = Flask(__name__)
app.secret_key = "brrpatapintralalerotralala"
library = BookLibrary()

# EPUB converter Setup
app.config['EPUB_UPLOAD_FOLDER'] = 'uploads/epubs'
app.config['MAX_CONTENT_LENGTH'] = 100 * 1024 * 1024  # 100MB max file size
app.config['ALLOWED_EXTENSIONS'] = {'pdf', 'epub'}

os.makedirs(app.config['EPUB_UPLOAD_FOLDER'], exist_ok=True)
os.makedirs('static/epub_covers', exist_ok=True)

# Register blueprints
app.register_blueprint(chatbot_bp)

def allowed_file(filename):
    """Check if file extension is allowed"""
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in app.config['ALLOWED_EXTENSIONS']



def get_book_pdf_url(title, author):
    """Search for book PDF URL"""
    try:
        # Clean inputs
        title = title.strip() if title else ""
        author = author.strip() if author else ""
        
        if not title or not author:
            logger.warning("Title or author is empty")
            return None
        
        # Build search query
        query = f"{title} {author} pdf free download"
        encoded_query = urllib.parse.quote(query)
        search_url = f"https://www.google.com/search?q={encoded_query}"
        
        # Real browser headers
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Accept-Encoding': 'gzip, deflate, br',
            'DNT': '1',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
            'Sec-Fetch-Dest': 'document',
            'Sec-Fetch-Mode': 'navigate',
            'Sec-Fetch-Site': 'none',
            'Sec-Fetch-User': '?1',
            'Cache-Control': 'max-age=0'
        }
        
        logger.info(f"Searching for PDF: {query}")
        
        # Fetch search results
        response = requests.get(search_url, headers=headers, timeout=30)
        if response.status_code != 200:
            logger.error(f"Google search failed: {response.status_code}")
            return None
        
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Method 1: Look for PDF links in search results
        for link in soup.find_all('a', href=True):
            href = link['href']
            
            # Skip Google's own links
            if 'google.com' in href or href.startswith('/search?'):
                continue
            
            # Check for PDF indicator in URL or link text
            is_pdf_link = ('.pdf' in href.lower() or 
                          'pdf' in href.lower() or
                          (link.text and 'pdf' in link.text.lower()) or
                          (link.text and 'download' in link.text.lower()))
            
            if is_pdf_link:
                # Handle Google redirect URLs
                if href.startswith('/url?q='):
                    # Extract actual URL from Google redirect
                    pdf_url = href.split('q=')[1].split('&')[0]
                    pdf_url = urllib.parse.unquote(pdf_url)
                    if pdf_url.lower().endswith('.pdf') or 'pdf' in pdf_url.lower():
                        logger.info(f"Found PDF via redirect: {pdf_url[:100]}...")
                        return pdf_url
                elif href.startswith('http'):
                    # Direct link
                    if href.lower().endswith('.pdf') or 'pdf' in href.lower():
                        logger.info(f"Found direct PDF link: {href[:100]}...")
                        return href
        
        # Method 2: Look for text containing PDF references
        for element in soup.find_all(['span', 'div', 'p']):
            text = element.get_text().lower()
            if 'pdf' in text and 'download' in text:
                # Find the nearest link
                link = element.find_parent('a') or element.find_next('a')
                if link and link.get('href'):
                    href = link['href']
                    if href.startswith('/url?q='):
                        pdf_url = href.split('q=')[1].split('&')[0]
                        pdf_url = urllib.parse.unquote(pdf_url)
                        if pdf_url.lower().endswith('.pdf'):
                            return pdf_url
        
        # Method 3: Look for Archive.org or Project Gutenberg links
        for link in soup.find_all('a', href=True):
            href = link['href']
            if any(domain in href for domain in ['archive.org', 'gutenberg.org', 'libgen', 'pdfdrive']):
                if href.startswith('/url?q='):
                    pdf_url = href.split('q=')[1].split('&')[0]
                    pdf_url = urllib.parse.unquote(pdf_url)
                    return pdf_url
                elif href.startswith('http'):
                    return href
        
        logger.info("No PDF URL found")
        return None
        
    except Exception as e:
        logger.error(f"Error searching for PDF URL: {e}")
        return None

def download_pdf_file(pdf_url):
    """Download PDF from URL and return file path"""
    try:
        if not pdf_url:
            return None
        
        # Set up headers for download
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Accept': 'application/pdf,application/octet-stream,*/*',
            'Accept-Language': 'en-US,en;q=0.5',
            'Referer': 'https://www.google.com/',
            'Sec-Fetch-Dest': 'document',
            'Sec-Fetch-Mode': 'navigate'
        }
        
        # Send HEAD request first to check
        try:
            head_resp = requests.head(pdf_url, headers=headers, timeout=10, allow_redirects=True)
            content_type = head_resp.headers.get('content-type', '').lower()
            content_length = head_resp.headers.get('content-length', '0')
            
            if 'pdf' not in content_type and not pdf_url.lower().endswith('.pdf'):
                logger.warning(f"URL doesn't appear to be PDF. Content-Type: {content_type}")
        except:
            pass  # Continue anyway
        
        # Download the file
        response = requests.get(pdf_url, headers=headers, stream=True, timeout=30)
        response.raise_for_status()
        
        # Create temp file
        temp_dir = tempfile.gettempdir()
        
        # Generate safe filename
        filename = "book.pdf"
        if 'content-disposition' in response.headers:
            content_disp = response.headers['content-disposition']
            if 'filename=' in content_disp:
                filename = content_disp.split('filename=')[1].strip('"\'')
        elif pdf_url.lower().endswith('.pdf'):
            filename = pdf_url.split('/')[-1].split('?')[0]
        
        # Clean filename
        filename = re.sub(r'[^\w\-_. ]', '', filename)
        if not filename.lower().endswith('.pdf'):
            filename += '.pdf'
        
        filepath = os.path.join(temp_dir, filename)
        
        # Save file
        with open(filepath, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                if chunk:
                    f.write(chunk)
        
        # Verify file size
        file_size = os.path.getsize(filepath)
        if file_size < 1024:  # Less than 1KB probably not a valid PDF
            os.remove(filepath)
            logger.warning(f"Downloaded file too small: {file_size} bytes")
            return None
        
        logger.info(f"PDF downloaded: {filepath} ({file_size} bytes)")
        return filepath
        
    except Exception as e:
        logger.error(f"Error downloading PDF: {e}")
        return None

def search_and_download_pdf(title, author):
    """Combined function to search and download PDF"""
    pdf_url = get_book_pdf_url(title, author)
    if pdf_url:
        return download_pdf_file(pdf_url)
    return None

@app.before_request
def log_request():
    print(f"Request: {request.method} {request.path}")

# Web app routes
@app.route("/", methods=["GET"])
def home():
    return render_template("index.html")

@app.route("/add-book", methods=["GET", "POST"])
def add_book():
    if request.method == "POST":
        title = request.form.get("title")
        author = request.form.get("author")

        library.add_book(title, author)
        try:
            recommender.embedding_service.update_embeddings_in_db()
        except AttributeError as e:
            print(f"Warning: Could not update embeddings: {e}")
            print("Continuing without embedding update...")

        flash("📘 Book added successfully!", "success")
        return redirect(url_for("home"))

    return render_template("add_book.html")

@app.route("/books")
def books():
    return render_template("books.html", books=library.view_books())


    
@app.route('/api/books/pdf-stats', methods=['GET'])
def get_pdf_stats():
    """Get PDF statistics"""
    try:
        conn = library.get_connection()
        cursor = conn.cursor()
        
        # Total books
        cursor.execute("SELECT COUNT(*) FROM books")
        total_books_result = cursor.fetchone()
        total_books = total_books_result[0] if total_books_result else 0
        
        # Books with PDFs
        cursor.execute("SELECT COUNT(*) FROM books WHERE pdf_path IS NOT NULL AND pdf_path != ''")
        pdf_result = cursor.fetchone()
        books_with_pdf = pdf_result[0] if pdf_result else 0
        
        # Books with PDFs converted to EPUB
        cursor.execute("SELECT COUNT(*) FROM books WHERE has_epub = 1")
        epub_result = cursor.fetchone()
        books_converted = epub_result[0] if epub_result else 0
        
        # Recent PDF activity (last 5 books with PDFs)
        cursor.execute("""
            SELECT id, title, pdf_path, last_updated 
            FROM books 
            WHERE pdf_path IS NOT NULL AND pdf_path != ''
            ORDER BY COALESCE(last_updated, date_added) DESC 
            LIMIT 5
        """)
        recent_activity_rows = cursor.fetchall()
        
        conn.close()
        
        recent_activity = []
        for row in recent_activity_rows:
            recent_activity.append({
                "id": row[0],
                "title": row[1],
                "pdf_path": row[2],
                "last_updated": row[3]
            })
        
        return jsonify({
            "status": "success",
            "stats": {
                "total_books": total_books,
                "books_with_pdf": books_with_pdf,
                "books_converted": books_converted,
                "conversion_rate": f"{(books_converted/books_with_pdf*100):.1f}%" if books_with_pdf > 0 else "0%"
            },
            "recent_activity": recent_activity
        })
        
    except Exception as e:
        logger.error(f"PDF stats error: {e}")
        return jsonify({
            "status": "error",
            "message": f"Stats error: {str(e)}",
            "stats": {
                "total_books": 0,
                "books_with_pdf": 0,
                "books_converted": 0,
                "conversion_rate": "0%"
            },
            "recent_activity": []
        })

@app.route('/api/library-stats', methods=['GET'])
def get_library_stats_api():
    """Get all library statistics in one endpoint (simplified version)"""
    try:
        conn = library.get_connection()
        cursor = conn.cursor()
        
        # Get all stats in one query
        cursor.execute("""
            SELECT 
                COUNT(*) as total_books,
                COUNT(CASE WHEN pdf_path IS NOT NULL AND pdf_path != '' THEN 1 END) as books_with_pdf,
                COUNT(CASE WHEN has_epub = 1 THEN 1 END) as books_with_epub,
                COUNT(DISTINCT author) as unique_authors
            FROM books
        """)
        
        stats = cursor.fetchone()
        
        conn.close()
        
        if stats:
            return jsonify({
                "status": "success",
                "stats": {
                    "total_books": stats[0] or 0,
                    "books_with_pdf": stats[1] or 0,
                    "books_with_epub": stats[2] or 0,
                    "unique_authors": stats[3] or 0
                }
            })
        else:
            return jsonify({
                "status": "success",
                "stats": {
                    "total_books": 0,
                    "books_with_pdf": 0,
                    "books_with_epub": 0,
                    "unique_authors": 0
                }
            })
            
    except Exception as e:
        logger.error(f"Library stats error: {e}")
        return jsonify({
            "status": "error",
            "stats": {
                "total_books": 0,
                "books_with_pdf": 0,
                "books_with_epub": 0,
                "unique_authors": 0
            }
        })

@app.route("/book/<int:book_id>")
def book_details(book_id):
    book = library.view_book_details(book_id)
    return render_template("book_details.html", book=book)

@app.route("/search")
def search_books():
    query = request.args.get("q", "")
    results = library.search_books(query)
    return render_template("books.html", books=results)

@app.route("/delete/<int:book_id>", methods=["POST"])
def delete(book_id):
    library.delete_book(book_id)
    return redirect(url_for("books"))

@app.route("/add-saga", methods=["GET", "POST"])
def add_saga():
    if request.method == "POST":
        title = request.form["title"]
        author = request.form["author"]
        description = request.form.get("description", "")
        num_books = int(request.form["num_books"])

        library.add_saga(title, description)
        flash("Saga added successfully!", "success")
        return redirect(url_for("add_saga"))

    return render_template("add_saga.html")

@app.route("/sagas")
def view_sagas():
    sagas = library.get_all_sagas()
    return render_template("sagas.html", sagas=sagas)

@app.route("/saga/<int:saga_id>")
def saga_details(saga_id):
    saga = library.saga_details(saga_id)
    books = library.get_books_by_saga(saga_id)
    return render_template("saga_detail.html", saga=saga, books=books)

@app.route("/saga/<int:saga_id>/add-book", methods=["GET", "POST"])
def add_book_to_saga(saga_id):
    saga = library.saga_details(saga_id)

    if request.method == "POST":
        title = request.form["title"]
        author = request.form["author"]

        library.add_book(title, author, saga_id=saga_id)
        flash("Book added to saga!", "success")
        return redirect(url_for("saga_details", saga_id=saga_id))

    return render_template("add_book_to_saga.html", saga=saga)

@app.route("/delete/<int:saga_id>", methods=["POST"])
def delete_saga(saga_id):
    library.delete_saga(saga_id)
    return redirect(url_for("view_sagas"))

@app.route("/book/<int:book_id>/rate", methods=["POST"])
def rate_book(book_id):
    rating = float(request.form["rating"])
    library.rate_book(book_id, rating)
    return redirect(url_for("book_details", book_id=book_id))

@app.route("/book/<int:book_id>/recommendations")
def book_recommendations(book_id):
    recommendations = recommender.get_book_recommendations(
        book_id=book_id,
        top_k=6
    )
    return render_template(
        "recommendations.html",
        recommendations=recommendations
    )

@app.route("/chatbot")
def chatbot_page():
    return render_template("chatbot.html")

# PDF Routes
@app.route('/api/books/search-pdf', methods=['GET', 'POST'])
def search_pdf():
    """Search for book PDF and return URL"""
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
        
        pdf_url = get_book_pdf_url(title, author)
        
        if pdf_url:
            return jsonify({
                "status": "success",
                "pdf_url": pdf_url,
                "download_url": f"/api/books/download-pdf?url={urllib.parse.quote(pdf_url)}&title={urllib.parse.quote(title)}",
                "message": f"Found PDF for '{title}' by {author}"
            })
        else:
            return jsonify({
                "status": "not_found",
                "pdf_url": None,
                "message": f"No PDF found for '{title}' by {author}"
            })
        
    except Exception as e:
        logger.error(f"PDF search endpoint error: {e}")
        return jsonify({
            "status": "error",
            "message": f"Server error: {str(e)}"
        }), 500

@app.route('/api/books/download-pdf', methods=['GET'])
def download_pdf():
    """Download and serve PDF file"""
    try:
        pdf_url = request.args.get('url', '')
        title = request.args.get('title', 'Book')
        
        if not pdf_url:
            return jsonify({
                "status": "error",
                "message": "PDF URL is required"
            }), 400
        
        pdf_url = urllib.parse.unquote(pdf_url)
        title = urllib.parse.unquote(title)
        
        logger.info(f"Downloading PDF: {title} from {pdf_url[:100]}...")
        
        # Download the PDF
        filepath = download_pdf_file(pdf_url)
        
        if not filepath or not os.path.exists(filepath):
            return jsonify({
                "status": "error",
                "message": "Failed to download PDF file"
            }), 500
        
        # Clean title for filename
        safe_title = re.sub(r'[^\w\s-]', '', title)
        safe_title = re.sub(r'\s+', '_', safe_title)
        filename = f"{safe_title}.pdf"
        
        # Send the file
        return send_file(
            filepath,
            as_attachment=True,
            download_name=filename,
            mimetype='application/pdf'
        )
        
    except Exception as e:
        logger.error(f"PDF download error: {e}")
        return jsonify({
            "status": "error",
            "message": f"Download error: {str(e)}"
        }), 500

@app.route('/api/books/<int:book_id>/pdf-download', methods=['GET'])
def get_book_pdf_download(book_id):
    """Get and download PDF for a specific book by ID"""
    try:
        book = library.view_book_details(book_id)
        if not book:
            return jsonify({
                "status": "error",
                "message": f"Book with ID {book_id} not found"
            }), 404
        
        title = book.get('title', '')
        author = book.get('author', '')
        
        logger.info(f"Getting PDF for book {book_id}: '{title}' by {author}")
        
        # Search for PDF URL
        pdf_url = get_book_pdf_url(title, author)
        
        if not pdf_url:
            return jsonify({
                "status": "not_found",
                "message": f"No PDF found for '{title}' by {author}"
            }), 404
        
        # Download the PDF
        filepath = download_pdf_file(pdf_url)
        
        if not filepath or not os.path.exists(filepath):
            return jsonify({
                "status": "error",
                "message": "Failed to download PDF file"
            }), 500
        
        # Create filename
        safe_title = re.sub(r'[^\w\s-]', '', title)
        safe_title = re.sub(r'\s+', '_', safe_title)
        filename = f"{safe_title}_{book_id}.pdf"
        
        # Send the file
        return send_file(
            filepath,
            as_attachment=True,
            download_name=filename,
            mimetype='application/pdf'
        )
        
    except Exception as e:
        logger.error(f"Book PDF download error: {e}")
        return jsonify({
            "status": "error",
            "message": f"Error: {str(e)}"
        }), 500

@app.route('/api/books/<int:book_id>/pdf-view', methods=['GET'])
def view_book_pdf(book_id):
    """View PDF in browser (inline)"""
    try:
        book = library.view_book_details(book_id)
        if not book:
            return jsonify({
                "status": "error",
                "message": f"Book with ID {book_id} not found"
            }), 404
        
        title = book.get('title', '')
        author = book.get('author', '')
        
        logger.info(f"Viewing PDF for book {book_id}: '{title}' by {author}")
        
        # Search for PDF URL
        pdf_url = get_book_pdf_url(title, author)
        
        if not pdf_url:
            return jsonify({
                "status": "not_found",
                "message": f"No PDF found for '{title}' by {author}"
            }), 404
        
        # Download the PDF
        filepath = download_pdf_file(pdf_url)
        
        if not filepath or not os.path.exists(filepath):
            return jsonify({
                "status": "error",
                "message": "Failed to download PDF file"
            }), 500
        
        # Send file for inline viewing
        return send_file(
            filepath,
            as_attachment=False,  # False for inline viewing
            mimetype='application/pdf'
        )
        
    except Exception as e:
        logger.error(f"Book PDF view error: {e}")
        return jsonify({
            "status": "error",
            "message": f"Error: {str(e)}"
        }), 500

@app.route('/api/books/<int:book_id>/pdf', methods=['GET'])
def get_book_pdf_by_id(book_id):
    """Get PDF URL for a specific book (backward compatibility)"""
    try:
        book = library.view_book_details(book_id)
        if not book:
            return jsonify({
                "status": "error",
                "message": f"Book with ID {book_id} not found"
            }), 404
        
        title = book.get('title', '')
        author = book.get('author', '')
        
        pdf_url = get_book_pdf_url(title, author)
        
        if pdf_url:
            return jsonify({
                "status": "success",
                "pdf_url": pdf_url,
                "download_url": f"/api/books/{book_id}/pdf-download",
                "view_url": f"/api/books/{book_id}/pdf-view",
                "book": {
                    "id": book_id,
                    "title": title,
                    "author": author
                },
                "message": f"Found PDF for '{title}'"
            })
        else:
            return jsonify({
                "status": "not_found",
                "pdf_url": None,
                "message": f"No PDF found for '{title}' by {author}"
            })
        
    except Exception as e:
        logger.error(f"Error getting PDF for book {book_id}: {e}")
        return jsonify({
            "status": "error",
            "message": f"Server error: {str(e)}"
        }), 500

# New route for direct PDF search from web interface
@app.route("/search-pdf", methods=["GET"])
def search_pdf_page():
    """Web page for searching PDFs"""
    return render_template("search_pdf.html")

@app.route('/api/books/<int:book_id>/search-pdf', methods=['POST', 'GET'])
def search_book_pdf(book_id):
    """
    Search for PDF of a specific book
    POST: Start search
    GET: Check search status
    """
    try:
        # Get book details
        book = library.view_book_details(book_id)
        if not book:
            return jsonify({
                "status": "error",
                "message": f"Book with ID {book_id} not found"
            }), 404
        
        title = book.get('title', '')
        author = book.get('author', '')
        
        if request.method == 'POST':
            # Start PDF search
            print(f"🔍 Starting PDF search for book {book_id}: '{title}' by {author}")
            
            # Use the enhanced PDF search
            pdf_url = library.get_book_pdf_enhanced(title, author)
            
            if pdf_url:
                return jsonify({
                    "status": "success",
                    "message": "PDF found",
                    "book": {
                        "id": book_id,
                        "title": title,
                        "author": author
                    },
                    "pdf_url": pdf_url,
                    "download_action": {
                        "url": f"/api/books/{book_id}/download-found-pdf",
                        "method": "POST",
                        "body": {"pdf_url": pdf_url}
                    },
                    "direct_download": f"/api/books/{book_id}/download-pdf-direct?url={urllib.parse.quote(pdf_url)}"
                })
            else:
                return jsonify({
                    "status": "not_found",
                    "message": f"No PDF found for '{title}' by {author}",
                    "book": {
                        "id": book_id,
                        "title": title,
                        "author": author
                    }
                }), 404
        
        else:  # GET method
            # Check if book already has PDF
            if book.get('pdf_path') and os.path.exists(book.get('pdf_path')):
                return jsonify({
                    "status": "already_downloaded",
                    "message": "Book already has a PDF file",
                    "pdf_path": book.get('pdf_path'),
                    "file_size": book.get('file_size'),
                    "download_url": f"/api/books/{book_id}/download-existing-pdf"
                })
            
            return jsonify({
                "status": "ready",
                "message": "Ready to search for PDF",
                "book": {
                    "id": book_id,
                    "title": title,
                    "author": author
                },
                "search_url": f"/api/books/{book_id}/search-pdf",
                "method": "POST"
            })
        
    except Exception as e:
        logger.error(f"PDF search error for book {book_id}: {e}")
        return jsonify({
            "status": "error",
            "message": f"Search error: {str(e)}"
        }), 500
    
@app.route('/api/books/<int:book_id>/download-found-pdf', methods=['POST'])
def download_found_pdf(book_id):
    """
    Download a found PDF URL and save it to the book
    """
    try:
        data = request.get_json()
        if not data or 'pdf_url' not in data:
            return jsonify({
                "status": "error",
                "message": "PDF URL is required"
            }), 400
        
        pdf_url = data['pdf_url']
        
        # Get book details
        book = library.view_book_details(book_id)
        if not book:
            return jsonify({
                "status": "error",
                "message": f"Book with ID {book_id} not found"
            }), 404
        
        print(f"📥 Downloading PDF for book {book_id}: {pdf_url[:100]}...")
        
        # Download the PDF
        pdf_path = library.download_pdf_file(pdf_url, book_id)
        
        if not pdf_path or not os.path.exists(pdf_path):
            return jsonify({
                "status": "error",
                "message": "Failed to download PDF file"
            }), 500
        
        # Update database
        conn = library.get_connection()
        cursor = conn.cursor()
        
        file_size = os.path.getsize(pdf_path)
        cursor.execute("""
            UPDATE books SET 
                pdf_path = ?,
                file_size = ?,
                last_updated = ?
            WHERE id = ?
        """, (pdf_path, file_size, datetime.datetime.now().isoformat(), book_id))
        
        conn.commit()
        conn.close()
        
        return jsonify({
            "status": "success",
            "message": "PDF downloaded and saved successfully",
            "book": {
                "id": book_id,
                "title": book.get('title'),
                "author": book.get('author')
            },
            "pdf": {
                "path": pdf_path,
                "size": file_size,
                "size_mb": round(file_size / (1024 * 1024), 2)
            },
            "download_url": f"/api/books/{book_id}/download-existing-pdf",
            "convert_url": f"/api/books/{book_id}/convert-to-epub"
        })
        
    except Exception as e:
        logger.error(f"PDF download error for book {book_id}: {e}")
        return jsonify({
            "status": "error",
            "message": f"Download error: {str(e)}"
        }), 500
    
@app.route('/api/books/<int:book_id>/download-existing-pdf', methods=['GET'])
def download_existing_pdf(book_id):
    """
    Download an already saved PDF file for a book
    """
    try:
        book = library.view_book_details(book_id)
        if not book:
            return jsonify({
                "status": "error",
                "message": f"Book with ID {book_id} not found"
            }), 404
        
        pdf_path = book.get('pdf_path')
        if not pdf_path or not os.path.exists(pdf_path):
            return jsonify({
                "status": "not_found",
                "message": "No PDF file found for this book. Please search for one first."
            }), 404
        
        # Create safe filename
        title = book.get('title', f'book_{book_id}')
        safe_title = re.sub(r'[^\w\s-]', '', title)
        safe_title = re.sub(r'\s+', '_', safe_title)
        filename = f"{safe_title}.pdf"
        
        return send_file(
            pdf_path,
            as_attachment=True,
            download_name=filename,
            mimetype='application/pdf'
        )
        
    except Exception as e:
        logger.error(f"Error downloading existing PDF: {e}")
        return jsonify({
            "status": "error",
            "message": f"Download error: {str(e)}"
        }), 500
    
@app.route('/api/books/<int:book_id>/download-pdf-direct', methods=['GET'])
def download_pdf_direct(book_id):
    """
    Direct PDF download from URL (without saving to database)
    """
    try:
        pdf_url = request.args.get('url', '')
        if not pdf_url:
            return jsonify({
                "status": "error",
                "message": "PDF URL is required"
            }), 400
        
        pdf_url = urllib.parse.unquote(pdf_url)
        
        # Get book for filename
        book = library.view_book_details(book_id)
        title = book.get('title', f'book_{book_id}') if book else f'book_{book_id}'
        
        print(f"📥 Direct download: {pdf_url[:100]}...")
        
        # Download to temp file
        temp_dir = tempfile.gettempdir()
        temp_filename = f"book_{book_id}_{int(time.time())}.pdf"
        temp_path = os.path.join(temp_dir, temp_filename)
        
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Accept': 'application/pdf,*/*'
        }
        
        response = requests.get(pdf_url, headers=headers, stream=True, timeout=30)
        response.raise_for_status()
        
        with open(temp_path, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                if chunk:
                    f.write(chunk)
        
        # Create safe filename
        safe_title = re.sub(r'[^\w\s-]', '', title)
        safe_title = re.sub(r'\s+', '_', safe_title)
        filename = f"{safe_title}.pdf"
        
        return send_file(
            temp_path,
            as_attachment=True,
            download_name=filename,
            mimetype='application/pdf'
        )
        
    except Exception as e:
        logger.error(f"Direct PDF download error: {e}")
        return jsonify({
            "status": "error",
            "message": f"Download error: {str(e)}"
        }), 500
    
@app.route('/api/books/<int:book_id>/auto-find-pdf', methods=['POST'])
def auto_find_download_pdf(book_id):
    """
    Automatically find and download PDF for a book (all-in-one)
    """
    try:
        # Get book details
        book = library.view_book_details(book_id)
        if not book:
            return jsonify({
                "status": "error",
                "message": f"Book with ID {book_id} not found"
            }), 404
        
        title = book.get('title', '')
        author = book.get('author', '')
        
        print(f"🚀 Auto-find PDF for book {book_id}: '{title}' by {author}")
        
        # Check if already has PDF
        if book.get('pdf_path') and os.path.exists(book.get('pdf_path')):
            return jsonify({
                "status": "already_exists",
                "message": "Book already has a PDF file",
                "pdf_path": book.get('pdf_path'),
                "download_url": f"/api/books/{book_id}/download-existing-pdf"
            })
        
        # Search for PDF
        pdf_url = library.get_book_pdf_enhanced(title, author)
        
        if not pdf_url:
            return jsonify({
                "status": "not_found",
                "message": f"No PDF found for '{title}' by {author}"
            }), 404
        
        # Download PDF
        pdf_path = library.download_pdf_file(pdf_url, book_id)
        
        if not pdf_path or not os.path.exists(pdf_path):
            return jsonify({
                "status": "download_failed",
                "message": "Found PDF but download failed",
                "pdf_url": pdf_url,
                "direct_download": f"/api/books/{book_id}/download-pdf-direct?url={urllib.parse.quote(pdf_url)}"
            }), 500
        
        # Update database
        conn = library.get_connection()
        cursor = conn.cursor()
        
        file_size = os.path.getsize(pdf_path)
        cursor.execute("""
            UPDATE books SET 
                pdf_path = ?,
                file_size = ?,
                last_updated = ?
            WHERE id = ?
        """, (pdf_path, file_size, datetime.datetime.now().isoformat(), book_id))
        
        conn.commit()
        conn.close()
        
        return jsonify({
            "status": "success",
            "message": "PDF found, downloaded, and saved successfully",
            "book": {
                "id": book_id,
                "title": title,
                "author": author
            },
            "pdf": {
                "path": pdf_path,
                "size": file_size,
                "size_mb": round(file_size / (1024 * 1024), 2)
            },
            "download_url": f"/api/books/{book_id}/download-existing-pdf",
            "convert_url": f"/api/books/{book_id}/convert-to-epub"
        })
        
    except Exception as e:
        logger.error(f"Auto-find PDF error for book {book_id}: {e}")
        return jsonify({
            "status": "error",
            "message": f"Auto-find error: {str(e)}"
        }), 500
    
@app.route('/api/books/batch-find-pdfs', methods=['POST'])
def batch_find_pdfs():
    """
    Batch find PDFs for multiple books
    """
    try:
        data = request.get_json()
        book_ids = data.get('book_ids', [])
        
        if not book_ids:
            # Get all books without PDFs
            conn = library.get_connection()
            cursor = conn.cursor()
            cursor.execute("""
                SELECT id FROM books 
                WHERE pdf_path IS NULL OR pdf_path = '' OR NOT EXISTS (
                    SELECT 1 FROM books b2 WHERE b2.id = books.id AND b2.pdf_path IS NOT NULL
                )
            """)
            book_ids = [row[0] for row in cursor.fetchall()]
            conn.close()
        
        if not book_ids:
            return jsonify({
                "status": "info",
                "message": "All books already have PDFs"
            })
        
        results = []
        
        for book_id in book_ids:
            try:
                book = library.view_book_details(book_id)
                if not book:
                    results.append({
                        "book_id": book_id,
                        "status": "error",
                        "message": "Book not found"
                    })
                    continue
                
                # Skip if already has PDF
                if book.get('pdf_path') and os.path.exists(book.get('pdf_path')):
                    results.append({
                        "book_id": book_id,
                        "status": "skipped",
                        "message": "Already has PDF",
                        "title": book.get('title')
                    })
                    continue
                
                # Search for PDF
                pdf_url = library.get_book_pdf_enhanced(book.get('title'), book.get('author'))
                
                if pdf_url:
                    results.append({
                        "book_id": book_id,
                        "status": "found",
                        "title": book.get('title'),
                        "pdf_url": pdf_url,
                        "download_url": f"/api/books/{book_id}/download-found-pdf"
                    })
                else:
                    results.append({
                        "book_id": book_id,
                        "status": "not_found",
                        "title": book.get('title'),
                        "message": "No PDF found"
                    })
                    
            except Exception as e:
                results.append({
                    "book_id": book_id,
                    "status": "error",
                    "message": str(e)
                })
        
        found_count = sum(1 for r in results if r['status'] == 'found')
        
        return jsonify({
            "status": "success",
            "message": f"Batch search completed. Found {found_count}/{len(book_ids)} PDFs",
            "total": len(book_ids),
            "found": found_count,
            "not_found": len([r for r in results if r['status'] == 'not_found']),
            "results": results
        })
        
    except Exception as e:
        logger.error(f"Batch find PDFs error: {e}")
        return jsonify({
            "status": "error",
            "message": f"Batch search error: {str(e)}"
        }), 500
    
@app.route('/api/books/<int:book_id>/pdf-info', methods=['GET'])
def get_pdf_info(book_id):
    """
    Get PDF information for a book
    """
    try:
        book = library.view_book_details(book_id)
        if not book:
            return jsonify({
                "status": "error",
                "message": f"Book with ID {book_id} not found"
            }), 404
        
        pdf_info = {
            "book_id": book_id,
            "title": book.get('title'),
            "author": book.get('author'),
            "has_pdf": False,
            "pdf_exists": False,
            "file_size": 0,
            "file_size_mb": 0,
            "last_updated": book.get('last_updated')
        }
        
        pdf_path = book.get('pdf_path')
        if pdf_path:
            pdf_info['has_pdf'] = True
            pdf_info['pdf_path'] = pdf_path
            
            if os.path.exists(pdf_path):
                pdf_info['pdf_exists'] = True
                file_size = os.path.getsize(pdf_path)
                pdf_info['file_size'] = file_size
                pdf_info['file_size_mb'] = round(file_size / (1024 * 1024), 2)
                pdf_info['download_url'] = f"/api/books/{book_id}/download-existing-pdf"
        
        return jsonify({
            "status": "success",
            "pdf_info": pdf_info
        })
        
    except Exception as e:
        logger.error(f"PDF info error: {e}")
        return jsonify({
            "status": "error",
            "message": f"PDF info error: {str(e)}"
        }), 500

@app.route('/api/books/<int:book_id>/delete-pdf', methods=['DELETE'])
def delete_book_pdf(book_id):
    """
    Delete PDF file for a book
    """
    try:
        book = library.view_book_details(book_id)
        if not book:
            return jsonify({
                "status": "error",
                "message": f"Book with ID {book_id} not found"
            }), 404
        
        pdf_path = book.get('pdf_path')
        deleted_file = False
        
        if pdf_path and os.path.exists(pdf_path):
            try:
                os.remove(pdf_path)
                deleted_file = True
                print(f"🗑️ Deleted PDF file: {pdf_path}")
            except Exception as e:
                logger.warning(f"Could not delete PDF file: {e}")
        
        # Update database
        conn = library.get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE books SET 
                pdf_path = NULL,
                file_size = NULL,
                last_updated = ?
            WHERE id = ?
        """, (datetime.datetime.now().isoformat(), book_id))
        
        conn.commit()
        conn.close()
        
        return jsonify({
            "status": "success",
            "message": "PDF removed from database" + (" and file deleted" if deleted_file else ""),
            "file_deleted": deleted_file
        })
        
    except Exception as e:
        logger.error(f"Delete PDF error: {e}")
        return jsonify({
            "status": "error",
            "message": f"Delete error: {str(e)}"
        }), 500

@app.route('/find-pdfs', methods=['GET'])
def find_pdfs_page():
    """Web page for finding PDFs"""
    # Get books without PDFs
    conn = library.get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT id, title, author, pdf_path
        FROM books 
        ORDER BY title
    """)
    books = cursor.fetchall()
    conn.close()
    
    # Convert to list of dictionaries
    book_list = []
    for book in books:
        book_id, title, author, pdf_path = book
        book_list.append({
            'id': book_id,
            'title': title,
            'author': author,
            'has_pdf': bool(pdf_path and os.path.exists(pdf_path)) if pdf_path else False,
            'pdf_path': pdf_path
        })
    
    return render_template('find_pdfs.html', books=book_list)

@app.route('/upload-pdf', methods=['GET'])
def upload_pdf_page():
    """Web page for manually uploading PDFs"""
    # Get all books
    books = library.view_books()
    return render_template('upload_pdf.html', books=books)

@app.route('/api/books/<int:book_id>/upload-pdf-manual', methods=['POST'])
def upload_pdf_manual(book_id):
    """Manually upload PDF file for a book"""
    try:
        if 'pdf_file' not in request.files:
            return jsonify({
                "status": "error",
                "message": "No PDF file provided"
            }), 400
        
        pdf_file = request.files['pdf_file']
        if pdf_file.filename == '':
            return jsonify({
                "status": "error",
                "message": "No file selected"
            }), 400
        
        if not pdf_file.filename.lower().endswith('.pdf'):
            return jsonify({
                "status": "error",
                "message": "File must be a PDF"
            }), 400
        
        # Get book details
        book = library.view_book_details(book_id)
        if not book:
            return jsonify({
                "status": "error",
                "message": f"Book with ID {book_id} not found"
            }), 404
        
        # Save uploaded file
        filename = f"book_{book_id}_{int(time.time())}.pdf"
        upload_dir = library.epub_dir
        os.makedirs(upload_dir, exist_ok=True)
        
        filepath = os.path.join(upload_dir, filename)
        pdf_file.save(filepath)
        
        # Verify it's a PDF
        try:
            with open(filepath, 'rb') as f:
                header = f.read(4)
                if header != b'%PDF':
                    os.remove(filepath)
                    return jsonify({
                        "status": "error",
                        "message": "Uploaded file is not a valid PDF"
                    }), 400
        except:
            pass
        
        # Update database
        conn = library.get_connection()
        cursor = conn.cursor()
        
        file_size = os.path.getsize(filepath)
        cursor.execute("""
            UPDATE books SET 
                pdf_path = ?,
                file_size = ?,
                last_updated = ?
            WHERE id = ?
        """, (filepath, file_size, datetime.datetime.now().isoformat(), book_id))
        
        conn.commit()
        conn.close()
        
        return jsonify({
            "status": "success",
            "message": "PDF uploaded successfully",
            "pdf": {
                "path": filepath,
                "size_mb": round(file_size / (1024 * 1024), 2)
            },
            "download_url": f"/api/books/{book_id}/download-existing-pdf",
            "convert_url": f"/api/books/{book_id}/convert-to-epub"
        })
        
    except Exception as e:
        logger.error(f"Manual PDF upload error: {e}")
        return jsonify({
            "status": "error",
            "message": f"Upload error: {str(e)}"
        }), 500
    


@app.route('/api/books/<int:book_id>/convert-to-epub', methods=['POST'])
def convert_book_to_epub(book_id):
    """Convert a book's PDF to EPUB format"""
    try:
        # Get book details from database
        book = library.view_book_details(book_id)
        if not book:
            return jsonify({
                "status": "error",
                "message": f"Book with ID {book_id} not found"
            }), 404
        
        # Check if book already has EPUB
        conn = library.get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT has_epub, epub_path FROM books WHERE id = ?", (book_id,))
        result = cursor.fetchone()
        
        if result and result[0]:  # has_epub is True
            return jsonify({
                "status": "info",
                "message": "Book already has an EPUB version",
                "epub_path": result[1],
                "download_url": f"/api/books/{book_id}/download-epub"
            }), 200
        
        # Check if book has PDF
        cursor.execute("SELECT pdf_path FROM books WHERE id = ?", (book_id,))
        pdf_result = cursor.fetchone()
        pdf_path = pdf_result[0] if pdf_result else None
        
        # If no PDF in DB, check for uploaded file
        if not pdf_path or not os.path.exists(pdf_path):
            # Check if PDF was uploaded with the request
            if 'pdf_file' not in request.files:
                return jsonify({
                    "status": "error",
                    "message": "No PDF file found. Please upload a PDF or ensure book has PDF path in database."
                }), 400
            
            pdf_file = request.files['pdf_file']
            if pdf_file.filename == '':
                return jsonify({
                    "status": "error",
                    "message": "No selected file"
                }), 400
            
            if not allowed_file(pdf_file.filename):
                return jsonify({
                    "status": "error",
                    "message": "File type not allowed. Please upload a PDF file."
                }), 400
            
            # Save uploaded PDF
            filename = secure_filename(f"book_{book_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf")
            pdf_path = os.path.join(app.config['EPUB_UPLOAD_FOLDER'], filename)
            pdf_file.save(pdf_path)
            
            # Update database with PDF path
            cursor.execute("UPDATE books SET pdf_path = ? WHERE id = ?", (pdf_path, book_id))
            conn.commit()
        
        # Get book title and author
        title = book.get('title', f'Book_{book_id}')
        author = book.get('author', 'Unknown')
        cover_url = book.get('cover_url')
        
        # Download cover if exists
        cover_path = None
        if cover_url:
            try:
                # Create safe filename for cover
                cover_filename = secure_filename(f"cover_{book_id}.jpg")
                cover_path = os.path.join('static/epub_covers', cover_filename)
                
                response = requests.get(cover_url, timeout=10)
                if response.status_code == 200:
                    with open(cover_path, 'wb') as f:
                        f.write(response.content)
            except Exception as e:
                logger.warning(f"Could not download cover: {e}")
                cover_path = None
        
        # Convert PDF to EPUB
        print(f"🔄 Converting book {book_id} to EPUB...")
        
        # Use the converter from your BookLibrary class
        epub_path = library.convert_book_to_epub(book_id, pdf_path)
        
        if not epub_path or not os.path.exists(epub_path):
            # Clean up temporary cover
            if cover_path and os.path.exists(cover_path):
                os.remove(cover_path)
            
            return jsonify({
                "status": "error",
                "message": "Failed to convert PDF to EPUB. Please check if the PDF file is valid."
            }), 500
        
        # Clean up temporary cover
        if cover_path and os.path.exists(cover_path):
            try:
                os.remove(cover_path)
            except:
                pass
        
        # Update database with EPUB info
        epub_size = os.path.getsize(epub_path) if os.path.exists(epub_path) else 0
        conversion_date = datetime.now().isoformat()
        
        cursor.execute("""
            UPDATE books SET 
                epub_path = ?,
                has_epub = 1,
                file_size = ?,
                conversion_date = ?
            WHERE id = ?
        """, (epub_path, epub_size, conversion_date, book_id))
        conn.commit()
        conn.close()
        
        # Get relative path for web access
        epub_relative_path = os.path.relpath(epub_path, start='.')
        
        return jsonify({
            "status": "success",
            "message": f"Successfully converted '{title}' to EPUB",
            "book": {
                "id": book_id,
                "title": title,
                "author": author
            },
            "epub": {
                "path": epub_path,
                "relative_path": epub_relative_path,
                "size": epub_size,
                "size_mb": round(epub_size / (1024 * 1024), 2),
                "conversion_date": conversion_date
            },
            "download_url": f"/api/books/{book_id}/download-epub",
            "view_url": f"/api/books/{book_id}/view-epub-info"
        }), 201
        
    except Exception as e:
        logger.error(f"Error converting book to EPUB: {e}")
        return jsonify({
            "status": "error",
            "message": f"Conversion error: {str(e)}"
        }), 500
    
@app.route('/api/books/<int:book_id>/download-epub', methods=['GET'])
def download_book_epub(book_id):
    """Download EPUB file for a book"""
    try:
        # Get EPUB path from database
        conn = library.get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT epub_path, title, author FROM books WHERE id = ? AND has_epub = 1", (book_id,))
        result = cursor.fetchone()
        conn.close()
        
        if not result:
            return jsonify({
                "status": "error",
                "message": "EPUB not found. Please convert the book to EPUB first."
            }), 404
        
        epub_path, title, author = result
        
        if not os.path.exists(epub_path):
            return jsonify({
                "status": "error",
                "message": "EPUB file not found on server"
            }), 404
        
        # Create safe filename
        safe_title = re.sub(r'[^\w\s-]', '', title)
        safe_title = re.sub(r'\s+', '_', safe_title)
        filename = f"{safe_title}_{book_id}.epub"
        
        return send_file(
            epub_path,
            as_attachment=True,
            download_name=filename,
            mimetype='application/epub+zip'
        )
        
    except Exception as e:
        logger.error(f"Error downloading EPUB: {e}")
        return jsonify({
            "status": "error",
            "message": f"Download error: {str(e)}"
        }), 500
    
@app.route('/api/books/<int:book_id>/view-epub-info', methods=['GET'])
def view_epub_info(book_id):
    """Get EPUB information for a book"""
    try:
        conn = library.get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id, title, author, epub_path, has_epub, file_size, conversion_date
            FROM books WHERE id = ?
        """, (book_id,))
        result = cursor.fetchone()
        conn.close()
        
        if not result:
            return jsonify({
                "status": "error",
                "message": f"Book with ID {book_id} not found"
            }), 404
        
        book_id, title, author, epub_path, has_epub, file_size, conversion_date = result
        
        epub_info = {
            "book_id": book_id,
            "title": title,
            "author": author,
            "has_epub": bool(has_epub),
            "file_size": file_size,
            "file_size_mb": round(file_size / (1024 * 1024), 2) if file_size else 0,
            "conversion_date": conversion_date
        }
        
        if has_epub and epub_path and os.path.exists(epub_path):
            epub_info.update({
                "epub_path": epub_path,
                "download_url": f"/api/books/{book_id}/download-epub",
                "exists": True
            })
        else:
            epub_info.update({
                "exists": False,
                "message": "EPUB file not available. Convert PDF to EPUB first."
            })
        
        return jsonify({
            "status": "success",
            "book": epub_info
        }), 200
        
    except Exception as e:
        logger.error(f"Error getting EPUB info: {e}")
        return jsonify({
            "status": "error",
            "message": f"Server error: {str(e)}"
        }), 500
    
@app.route('/api/books/<int:book_id>/delete-epub', methods=['DELETE'])
def delete_book_epub(book_id):
    """Delete EPUB file for a book"""
    try:
        conn = library.get_connection()
        cursor = conn.cursor()
        
        # Get EPUB path
        cursor.execute("SELECT epub_path FROM books WHERE id = ? AND has_epub = 1", (book_id,))
        result = cursor.fetchone()
        
        if not result:
            conn.close()
            return jsonify({
                "status": "error",
                "message": "No EPUB found for this book"
            }), 404
        
        epub_path = result[0]
        
        # Delete file if exists
        if epub_path and os.path.exists(epub_path):
            try:
                os.remove(epub_path)
                logger.info(f"Deleted EPUB file: {epub_path}")
            except Exception as e:
                logger.warning(f"Could not delete EPUB file: {e}")
        
        # Update database
        cursor.execute("""
            UPDATE books SET 
                epub_path = NULL,
                has_epub = 0,
                file_size = NULL,
                conversion_date = NULL
            WHERE id = ?
        """, (book_id,))
        
        conn.commit()
        conn.close()
        
        return jsonify({
            "status": "success",
            "message": "EPUB file deleted successfully"
        }), 200
        
    except Exception as e:
        logger.error(f"Error deleting EPUB: {e}")
        return jsonify({
            "status": "error",
            "message": f"Deletion error: {str(e)}"
        }), 500
    
@app.route('/api/books/upload-and-convert', methods=['POST'])
def upload_and_convert_pdf():
    """Upload PDF and convert to EPUB for a new or existing book"""
    try:
        # Check if file was uploaded
        if 'pdf_file' not in request.files:
            return jsonify({
                "status": "error",
                "message": "No PDF file provided"
            }), 400
        
        pdf_file = request.files['pdf_file']
        if pdf_file.filename == '':
            return jsonify({
                "status": "error",
                "message": "No selected file"
            }), 400
        
        if not allowed_file(pdf_file.filename):
            return jsonify({
                "status": "error",
                "message": "File type not allowed. Please upload a PDF file."
            }), 400
        
        # Get book information from form
        title = request.form.get('title', '').strip()
        author = request.form.get('author', '').strip()
        
        if not title or not author:
            return jsonify({
                "status": "error",
                "message": "Both title and author are required"
            }), 400
        
        # Check if book already exists
        conn = library.get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT id FROM books WHERE title = ? AND author = ?", (title, author))
        existing_book = cursor.fetchone()
        
        book_id = None
        
        if existing_book:
            # Book exists, update it
            book_id = existing_book[0]
            cursor.execute("UPDATE books SET pdf_path = NULL, epub_path = NULL, has_epub = 0 WHERE id = ?", (book_id,))
            conn.commit()
        else:
            # Add new book to database
            book_id = library.add_book(title, author)
        
        # Save uploaded PDF
        filename = secure_filename(f"book_{book_id if book_id else 'new'}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf")
        pdf_path = os.path.join(app.config['EPUB_UPLOAD_FOLDER'], filename)
        pdf_file.save(pdf_path)
        
        # Update database with PDF path
        cursor.execute("UPDATE books SET pdf_path = ? WHERE id = ?", (pdf_path, book_id))
        conn.commit()
        
        # Convert to EPUB
        epub_path = library.convert_book_to_epub(book_id, pdf_path)
        
        if not epub_path or not os.path.exists(epub_path):
            conn.close()
            return jsonify({
                "status": "error",
                "message": "Failed to convert PDF to EPUB"
            }), 500
        
        # Update database with EPUB info
        epub_size = os.path.getsize(epub_path)
        conversion_date = datetime.now().isoformat()
        
        cursor.execute("""
            UPDATE books SET 
                epub_path = ?,
                has_epub = 1,
                file_size = ?,
                conversion_date = ?
            WHERE id = ?
        """, (epub_path, epub_size, conversion_date, book_id))
        conn.commit()
        conn.close()
        
        return jsonify({
            "status": "success",
            "message": f"Successfully uploaded and converted '{title}' to EPUB",
            "book": {
                "id": book_id,
                "title": title,
                "author": author
            },
            "epub": {
                "path": epub_path,
                "size_mb": round(epub_size / (1024 * 1024), 2),
                "conversion_date": conversion_date
            },
            "download_url": f"/api/books/{book_id}/download-epub",
            "view_url": f"/api/books/{book_id}/view-epub-info"
        }), 201
        
    except Exception as e:
        logger.error(f"Error uploading and converting PDF: {e}")
        return jsonify({
            "status": "error",
            "message": f"Processing error: {str(e)}"
        }), 500
    
@app.route('/api/books/batch-convert', methods=['POST'])
def batch_convert_epubs():
    """Batch convert multiple books with PDFs to EPUB"""
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({
                "status": "error",
                "message": "No data provided"
            }), 400
        
        book_ids = data.get('book_ids', [])
        
        if not book_ids:
            # Convert all books with PDFs but no EPUB
            conn = library.get_connection()
            cursor = conn.cursor()
            cursor.execute("SELECT id FROM books WHERE pdf_path IS NOT NULL AND has_epub = 0")
            book_ids = [row[0] for row in cursor.fetchall()]
            conn.close()
        
        if not book_ids:
            return jsonify({
                "status": "info",
                "message": "No books found that need conversion"
            }), 200
        
        # Convert books
        results = []
        success_count = 0
        
        for book_id in book_ids:
            try:
                # Check if book exists
                book = library.view_book_details(book_id)
                if not book:
                    results.append({
                        "book_id": book_id,
                        "status": "error",
                        "message": "Book not found"
                    })
                    continue
                
                # Check if already has EPUB
                conn = library.get_connection()
                cursor = conn.cursor()
                cursor.execute("SELECT has_epub FROM books WHERE id = ?", (book_id,))
                has_epub = cursor.fetchone()[0]
                
                if has_epub:
                    results.append({
                        "book_id": book_id,
                        "status": "skipped",
                        "message": f"Book already has EPUB"
                    })
                    conn.close()
                    continue
                
                # Check for PDF
                cursor.execute("SELECT pdf_path FROM books WHERE id = ?", (book_id,))
                pdf_result = cursor.fetchone()
                pdf_path = pdf_result[0] if pdf_result else None
                
                if not pdf_path or not os.path.exists(pdf_path):
                    results.append({
                        "book_id": book_id,
                        "status": "error",
                        "message": "No PDF file found"
                    })
                    conn.close()
                    continue
                
                # Convert to EPUB
                epub_path = library.convert_book_to_epub(book_id, pdf_path)
                
                if epub_path and os.path.exists(epub_path):
                    epub_size = os.path.getsize(epub_path)
                    conversion_date = datetime.now().isoformat()
                    
                    cursor.execute("""
                        UPDATE books SET 
                            epub_path = ?,
                            has_epub = 1,
                            file_size = ?,
                            conversion_date = ?
                        WHERE id = ?
                    """, (epub_path, epub_size, conversion_date, book_id))
                    conn.commit()
                    
                    results.append({
                        "book_id": book_id,
                        "status": "success",
                        "title": book.get('title'),
                        "epub_path": epub_path,
                        "size_mb": round(epub_size / (1024 * 1024), 2),
                        "download_url": f"/api/books/{book_id}/download-epub"
                    })
                    success_count += 1
                else:
                    results.append({
                        "book_id": book_id,
                        "status": "error",
                        "message": "Conversion failed"
                    })
                
                conn.close()
                
            except Exception as e:
                results.append({
                    "book_id": book_id,
                    "status": "error",
                    "message": f"Error: {str(e)}"
                })
        
        return jsonify({
            "status": "success",
            "message": f"Batch conversion completed. Successfully converted {success_count}/{len(book_ids)} books",
            "total_books": len(book_ids),
            "successful": success_count,
            "failed": len(book_ids) - success_count,
            "results": results
        }), 200
        
    except Exception as e:
        logger.error(f"Error in batch conversion: {e}")
        return jsonify({
            "status": "error",
            "message": f"Batch conversion error: {str(e)}"
        }), 500

@app.route('/api/books/with-epub', methods=['GET'])
def get_books_with_epub():
    """Get all books that have EPUB versions"""
    try:
        conn = library.get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT id, title, author, epub_path, file_size, conversion_date
            FROM books 
            WHERE has_epub = 1
            ORDER BY title
        """)
        
        books = cursor.fetchall()
        conn.close()
        
        book_list = []
        for book in books:
            book_id, title, author, epub_path, file_size, conversion_date = book
            book_list.append({
                "id": book_id,
                "title": title,
                "author": author,
                "epub_path": epub_path,
                "file_size_mb": round(file_size / (1024 * 1024), 2) if file_size else 0,
                "conversion_date": conversion_date,
                "download_url": f"/api/books/{book_id}/download-epub",
                "info_url": f"/api/books/{book_id}/view-epub-info"
            })
        
        return jsonify({
            "status": "success",
            "count": len(book_list),
            "books": book_list
        }), 200
        
    except Exception as e:
        logger.error(f"Error getting books with EPUB: {e}")
        return jsonify({
            "status": "error",
            "message": f"Server error: {str(e)}"
        }), 500
    
@app.route('/api/epub-stats', methods=['GET'])
def get_epub_stats():
    """Get EPUB conversion statistics"""
    try:
        conn = library.get_connection()
        cursor = conn.cursor()
        
        # Total books
        cursor.execute("SELECT COUNT(*) FROM books")
        total_books = cursor.fetchone()[0]
        
        # Books with EPUB
        cursor.execute("SELECT COUNT(*) FROM books WHERE has_epub = 1")
        books_with_epub = cursor.fetchone()[0]
        
        # Books with PDF but no EPUB
        cursor.execute("SELECT COUNT(*) FROM books WHERE pdf_path IS NOT NULL AND has_epub = 0")
        books_with_pdf_no_epub = cursor.fetchone()[0]
        
        # Total EPUB file size
        cursor.execute("SELECT SUM(file_size) FROM books WHERE has_epub = 1")
        total_size = cursor.fetchone()[0] or 0
        
        # Latest conversions
        cursor.execute("""
            SELECT id, title, author, conversion_date 
            FROM books 
            WHERE has_epub = 1 
            ORDER BY conversion_date DESC 
            LIMIT 5
        """)
        latest_conversions = cursor.fetchall()
        
        conn.close()
        
        latest_list = []
        for book in latest_conversions:
            book_id, title, author, conversion_date = book
            latest_list.append({
                "id": book_id,
                "title": title,
                "author": author,
                "conversion_date": conversion_date,
                "download_url": f"/api/books/{book_id}/download-epub"
            })
        
        return jsonify({
            "status": "success",
            "stats": {
                "total_books": total_books,
                "books_with_epub": books_with_epub,
                "books_with_pdf_no_epub": books_with_pdf_no_epub,
                "conversion_rate": f"{(books_with_epub/total_books*100):.1f}%" if total_books > 0 else "0%",
                "total_epub_size_mb": round(total_size / (1024 * 1024), 2),
                "average_epub_size_mb": round((total_size / books_with_epub) / (1024 * 1024), 2) if books_with_epub > 0 else 0
            },
            "latest_conversions": latest_list
        }), 200
        
    except Exception as e:
        logger.error(f"Error getting EPUB stats: {e}")
        return jsonify({
            "status": "error",
            "message": f"Server error: {str(e)}"
        }), 500
    
@app.route('/convert-epub', methods=['GET'])
def convert_epub_page():
    """Web page for converting books to EPUB"""
    conn = library.get_connection()
    cursor = conn.cursor()
    
    # Get books that have PDFs but no EPUB
    cursor.execute("""
        SELECT id, title, author 
        FROM books 
        WHERE pdf_path IS NOT NULL AND has_epub = 0
        ORDER BY title
    """)
    books_to_convert_rows = cursor.fetchall()
    
    # Convert to list of dictionaries
    books_to_convert = []
    for row in books_to_convert_rows:
        books_to_convert.append({
            'id': row[0],
            'title': row[1],
            'author': row[2]
        })
    
    # Get books that already have EPUB
    cursor.execute("""
        SELECT id, title, author, conversion_date 
        FROM books 
        WHERE has_epub = 1 
        ORDER BY conversion_date DESC
    """)
    converted_books_rows = cursor.fetchall()
    
    # Convert to list of dictionaries
    converted_books = []
    for row in converted_books_rows:
        converted_books.append({
            'id': row[0],
            'title': row[1],
            'author': row[2],
            'conversion_date': row[3]
        })
    
    conn.close()
    
    return render_template(
        'convert_epub.html',
        books_to_convert=books_to_convert,
        converted_books=converted_books
    )

@app.route('/upload-epub', methods=['GET'])
def upload_epub_page():
    """Web page for uploading PDFs and converting to EPUB"""
    return render_template('upload_epub.html')

@app.route('/epub-library', methods=['GET'])
def epub_library_page():
    """Web page showing all EPUB books"""
    conn = library.get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT id, title, author, epub_path, file_size, conversion_date
        FROM books 
        WHERE has_epub = 1
        ORDER BY title
    """)
    books_rows = cursor.fetchall()
    conn.close()
    
    # Convert to list of dictionaries
    books = []
    for row in books_rows:
        books.append({
            'id': row[0],
            'title': row[1],
            'author': row[2],
            'epub_path': row[3],
            'file_size': row[4],
            'size_mb': round(row[4] / (1024 * 1024), 2) if row[4] else 0,
            'conversion_date': row[5]
        })
    
    return render_template('epub_library.html', books=books)

if __name__ == "__main__":
    print("\n=== REGISTERED ROUTES ===")
    for rule in app.url_map.iter_rules():
        print(f"{rule.endpoint}: {rule.rule}")
    print("=======================\n")
    
    print("📚 Book Library Server Starting...")
    print("🌐 Access on your computer: http://localhost:5000")
    print("📱 Access on your phone: http://<your-ip>:5000")
    print("🤖 Chatbot: http://localhost:5000/chatbot")
    print("🔍 PDF Search: http://localhost:5000/search-pdf")
    print("📱 EPUB Converter: http://localhost:5000/convert-epub")
    print("📤 Upload EPUB: http://localhost:5000/upload-epub")
    print("📚 EPUB Library: http://localhost:5000/epub-library")
    print("🔍 PDF Finder: http://localhost:5000/find-pdfs")
    print("📤 PDF Upload: http://localhost:5000/upload-pdf")
    
    app.run(debug=True, host='0.0.0.0', port=5000)