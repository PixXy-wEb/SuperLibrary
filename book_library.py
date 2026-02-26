import sqlite3
import datetime
import requests
import json
import re
from bs4 import BeautifulSoup
import time
import urllib.parse
import logging
from typing import Optional, Dict, Any

import os
import tempfile
from io import BytesIO
from PyPDF2 import PdfReader
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
from ebooklib import epub
import html2text
from bs4 import BeautifulSoup
import markdown
from typing import Optional, Tuple, List
import zipfile
import json

class PDFtoEPUBConverter:
    """Handles conversion of PDF files to EPUB format"""
    
    def __init__(self, temp_dir: str = None):
        self.temp_dir = temp_dir or tempfile.gettempdir()
        
    def pdf_to_text(self, pdf_path: str) -> str:
        """Extract text from PDF file"""
        try:
            text = ""
            with open(pdf_path, 'rb') as file:
                pdf_reader = PdfReader(file)
                for page in pdf_reader.pages:
                    text += page.extract_text() + "\n\n"
            return text.strip()
        except Exception as e:
            logger.error(f"Error extracting text from PDF: {e}")
            raise
    
    def text_to_epub(self, text: str, title: str, author: str, 
                     output_path: str, cover_image: str = None) -> bool:
        """Convert text to EPUB format"""
        try:
            # Create EPUB book
            book = epub.EpubBook()
            
            # Set metadata
            book.set_identifier(f'book-{title}-{author}'.replace(' ', '-').lower())
            book.set_title(title)
            book.set_language('en')
            book.add_author(author)
            
            # Add cover if provided
            if cover_image and os.path.exists(cover_image):
                with open(cover_image, 'rb') as img_file:
                    book.set_cover("cover.jpg", img_file.read())
            
            # Create chapters from text
            chapters = self._split_into_chapters(text)
            
            # Add chapters to book
            spine_items = ['nav']
            for i, chapter_text in enumerate(chapters):
                chapter_title = f"Chapter {i+1}"
                if i == 0 and len(chapters) > 1:
                    chapter_title = "Introduction"
                
                # Create chapter
                chapter = epub.EpubHtml(
                    title=chapter_title,
                    file_name=f'chap_{i+1:03d}.xhtml',
                    lang='en'
                )
                
                # Convert text to HTML
                html_content = self._text_to_html(chapter_text)
                chapter.content = html_content
                
                # Add chapter to book
                book.add_item(chapter)
                spine_items.append(chapter)
            
            # Add table of contents
            book.toc = tuple(spine_items[1:])  # Skip 'nav'
            
            # Add navigation files
            book.add_item(epub.EpubNcx())
            book.add_item(epub.EpubNav())
            
            # Define spine
            book.spine = spine_items
            
            # Write EPUB file
            epub.write_epub(output_path, book)
            return True
            
        except Exception as e:
            logger.error(f"Error creating EPUB: {e}")
            return False
    
    def _split_into_chapters(self, text: str, max_chars_per_chapter: int = 50000) -> List[str]:
        """Split text into manageable chapters"""
        if len(text) <= max_chars_per_chapter:
            return [text]
        
        chapters = []
        paragraphs = text.split('\n\n')
        current_chapter = []
        current_length = 0
        
        for para in paragraphs:
            para_length = len(para)
            if current_length + para_length > max_chars_per_chapter and current_chapter:
                chapters.append('\n\n'.join(current_chapter))
                current_chapter = [para]
                current_length = para_length
            else:
                current_chapter.append(para)
                current_length += para_length
        
        if current_chapter:
            chapters.append('\n\n'.join(current_chapter))
        
        return chapters
    
    def _text_to_html(self, text: str) -> str:
        """Convert plain text to HTML for EPUB"""
        # Simple conversion - you can enhance this with markdown or more complex formatting
        html = f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE html>
<html xmlns="http://www.w3.org/1999/xhtml">
<head>
    <title>Chapter</title>
    <style type="text/css">
        body {{ font-family: serif; line-height: 1.6; margin: 2em; }}
        p {{ text-align: justify; margin-bottom: 1em; }}
    </style>
</head>
<body>
    <div>
        {text.replace('\n\n', '</p><p>').replace('\n', '<br/>')}
    </div>
</body>
</html>"""
        return html
    
    def convert_pdf_to_epub(self, pdf_path: str, title: str, author: str, 
                            output_dir: str = None, cover_image: str = None) -> Optional[str]:
        """
        Main conversion method
        
        Args:
            pdf_path: Path to PDF file
            title: Book title
            author: Book author
            output_dir: Directory to save EPUB (defaults to same as PDF)
            cover_image: Optional path to cover image
            
        Returns:
            Path to created EPUB file or None if failed
        """
        try:
            if not os.path.exists(pdf_path):
                logger.error(f"PDF file not found: {pdf_path}")
                return None
            
            # Set output path
            if output_dir is None:
                output_dir = os.path.dirname(pdf_path)
            os.makedirs(output_dir, exist_ok=True)
            
            epub_filename = f"{title.replace(' ', '_')}.epub"
            epub_path = os.path.join(output_dir, epub_filename)
            
            # Extract text from PDF
            print(f"📖 Extracting text from PDF...")
            text = self.pdf_to_text(pdf_path)
            
            if not text.strip():
                logger.error("No text extracted from PDF")
                return None
            
            # Convert to EPUB
            print(f"🔄 Converting to EPUB...")
            success = self.text_to_epub(text, title, author, epub_path, cover_image)
            
            if success:
                print(f"✅ EPUB created successfully: {epub_path}")
                return epub_path
            else:
                return None
                
        except Exception as e:
            logger.error(f"Conversion error: {e}")
            return None

logger = logging.getLogger(__name__)

class BookLibrary:
    def __init__(self, db_path="library.db"):
        self.db_path = db_path      
        self.setup_database()
        self.converter = PDFtoEPUBConverter()
        self.epub_dir = "epub_library"


    def get_connection(self):
        conn = sqlite3.connect(
            self.db_path,
            timeout=30,
            check_same_thread=False
        )
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute("PRAGMA synchronous=NORMAL;")
        return conn



    def setup_database(self):
        conn = self.get_connection()
        cursor = conn.cursor()

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS books (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                author TEXT NOT NULL,
                date_added TEXT
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS sagas (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE,
                description TEXT
            )
            """)


        # Add missing columns safely
        existing_columns = {
            row[1] for row in cursor.execute("PRAGMA table_info(books)")
        }

        columns_to_add = {
            "isbn": "TEXT",
            "genre": "TEXT",
            "synopsis": "TEXT",
            "cover_url": "TEXT",
            "page_count": "INTEGER",
            "publisher": "TEXT",
            "published_date": "TEXT",
            "rating": "REAL",
            "last_updated": "TEXT",
        }

        for column, col_type in columns_to_add.items():
            if column not in existing_columns:
                cursor.execute(
                    f"ALTER TABLE books ADD COLUMN {column} {col_type}"
                )
        
        # Add missing columns safely SAGA
        existing_columns = {
            row[1] for row in cursor.execute("PRAGMA table_info(sagas)")
        }

        columns_to_add = {
                "num_books": "INTEGER",
                "author": "TEXT",
                "cover_url": "TEXT",
                "genre": "TEXT",
        }

        for column, col_type in columns_to_add.items():
            if column not in existing_columns:
                cursor.execute(
                    f"ALTER TABLE sagas ADD COLUMN {column} {col_type}"
                )

        # EPUB related stuff ahh columns // paulette
        existing_columns = {
            row[1] for row in cursor.execute("PRAGMA table_info(books)")
        }

        epub_columns = {
            "pdf_path" : "TEXT",
            "epub_path" : "TEXT",
            "has_epub" : "BOOLEAN DEFAULT 0",
            "file_size" : "INTERGER",
            "conversion_date" : "TEXT"
        }

        for column, col_type in epub_columns.items():
            if column not in existing_columns:
                cursor.execute(
                    f"ALTER TABLE books ADD COLUMN {column} {col_type}"
                )

        conn.commit()
        conn.close()

    def add_book_with_pdf(self, title: str, author: str, pdf_path: str, saga_id=None, conver_to_epub=None):
        """
        Add book with PDF and optionally convert to EPUB

        args: 
        title: Book title
        author: Book author
        pdf_path: Path to PDF file
        saga_id: Optional saga ID
        convert_to_epub: Wether to convert PDF to EPUB
        """
        
        book_id = self.add_book(title, author, saga_id)

        if book_id and os.path.exists(pdf_path):
            conn = self.get_connection()
            cursor = conn.cursor()

            # update book with pdf info
            cursor.execute("""
                UPDATE books SET
                           pdf_path = ?,
                           file_size = ?
                    WHERE id = ?
            """, (pdf_path, os.path.getsize(pdf_path), book_id))

            # convert to EPUB if requested
            if conver_to_epub:
                epub_path = self.convert_book_to_epub(book_id, pdf_path)
                if epub_path:
                    cursor.execute("""
                        UPDATE books SET
                                   epub_path = ?,
                                   has_epub = 1,
                                   conversion_date = ?
                                WHERE id = ?
                    """, (epub_path, datetime.datetime.now().isoformat(), book_id))
            
            conn.commit()
            conn.close()

            print(f"✅ Book = '{title}' added with PDF")
            if conver_to_epub:
                print(f"📁 EPUB version avaliable")

        return book_id
    
    def convert_book_to_epub(self, book_id: int, pdf_path: str = None, db_pdf_path: str = None) -> Optional[str]:
        """
        Convert a book's PDF to EPUB

        Args:
        book_id: Book ID in database
        pdf_path: Optional PDF path (if not stored)

        Returns:
        Path to created EPUB file or None
        """
        conn =  self.get_connection()
        cursor = conn.cursor()

        # get books details
        cursor.execute("""
            SELECT title, author, pdf_path, cover_url
            FROM books WHERE id = ?
        """, (book_id,))

        book = cursor.fetchone

        if not book:
            conn.close()
            return None
        
        title, author, pdf_path, cover_url = book 

        # use provided pdf_path or database path
        pdf_to_convert = pdf_path or db_pdf_path

        if not pdf_to_convert or not os.path.exists(pdf_to_convert):
            print(f"PDF not found for book ID {book_id}")
            conn.close() 
            return None
        
        # create epub directory
        os.makedirs(self.epub_dir, exist_ok=True)

        # download cover if URL exists
        cover_path = None
        if cover_url:
            try:
                cover_path = self.download_cover(cover_url, book_id)
            except Exception as e:
                logger.error(f"Error downloading cover: {e}")

        # conver pdf to epub
        print(f"Converting '{title}' to EPUB...")
        epub_path = self.converter.convert_pdf_to_epub(
            pdf_path=pdf_to_convert,
            title =title,
            author=author,
            output_dir=self.epub_dir,
            cover_image=cover_url
        )

        # clean up temporary cover
        if cover_path and os.path.exists(cover_path):
            try:
                os.remove(cover_path)
            except:
                pass 

        conn.close()
        return epub_path

    def download_cover(self, cover_url: str, book_id: int) -> Optional[str]:
        """Download cover for EPUB"""
        try:
            response = requests.get(cover_url, timeout=10)
            if response.status_code == 200:
                cover_path = os.path.join(self.epub_dir, f"cover_{book_id}.jpg")
                with open(cover_path, 'wb') as f:
                    f.write(response.content)
                return cover_path
        except Exception as e:
            logger.error(f"Error downloading cover: {e}")
        return None 
    
    def batch_convert_pdfs_to_epub(self, book_ids: List[int] = None):
        """
        Convert multiple PDFs to EPUB

        Args:
        book_ids: List of book IDs (if None, convert all with PDFs)
        """
        conn = self.get_connection()
        cursor = conn.cursor()

        if book_ids:
            placeholders = ",".join(['?']) * len(book_ids)
            cursor.execute(f"""
                SELECT id, title, pdf_path
                FROM books
                WHERE id IN ({placeholders}) AND pdf_path IS NOT NULL
            """, book_ids)
        else:
            cursor.execute("""
                SELECT id, title, pdf_path
                FROM books
                WHERE pdf_path IS NOT NULL AND has_epub = 0
            """)

        books = cursor.fetchall()

        print(f"\nConverting {len(books)} books to EPUB...")

        success_count = 0
        for book_id, title, pdf_path in books:
            print(f"\nProcessing: {title}")

            if os.path.exists(pdf_path):
                epub_path = self.convert_book_to_epub(book_id, pdf_path)

                if epub_path:
                    # update database
                    cursor.execute("""
                        UPDATE books SET
                            epub_path = ?,
                            has_epub = 0,
                            conversion_date = ?
                        WHERE id = ?
                    """, (epub_path, datetime.datetime.now().isoformat(), book_id))
                    success_count += 1
                    print(f"✅ Succesfully converted.")
                else:
                    print(f"❌ Conversion failed.")
            else:
                print(f"⚠️ PDF not found: {pdf_path}")

        conn.commit()
        conn.close()

        print(f"\n🎉 Conversion complete!")
        print(f"Succesfully converted '{success_count}/{len(books)}' books")

    def get_books_with_epub(self):
        """Get all books that have EPUB versions"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT id, title, author, epub_path, file_size, conversion_date
            FROM books 
            WHERE has_epub = 1
            ORDER BY title
        """)
        
        books = cursor.fetchall()
        conn.close()
        return books
    
    def view_book_with_files(self, book_id):
        """View book details including file information"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT 
                b.id, b.title, b.author, b.synopsis, b.cover_url,
                b.pdf_path, b.epub_path, b.has_epub, b.file_size,
                b.conversion_date, s.name as saga_name
            FROM books b
            LEFT JOIN sagas s ON b.saga_id = s.id
            WHERE b.id = ?
        """, (book_id,))
        
        book = cursor.fetchone()
        
        if book:
            print(f"\n📚 Book Details:")
            print(f"Title: {book[1]}")
            print(f"Author: {book[2]}")
            if book[9]:  # Saga name
                print(f"Saga: {book[9]}")
            
            print(f"\n📁 File Information:")
            if book[5]:  # PDF path
                print(f"PDF: {book[5]}")
                if book[7]:  # has_epub
                    print(f"EPUB: {book[6]}")
                    print(f"Converted: {book[9]}")
                else:
                    print("EPUB: Not available (use convert_book_to_epub)")
            
            if book[8]:  # File size
                size_mb = book[8] / (1024 * 1024)
                print(f"Size: {size_mb:.2f} MB")
        
        conn.close()
        return book


    def add_book(self, title, author, saga_id=None):
        conn = self.get_connection()
        cursor = conn.cursor()

        date_added = datetime.datetime.now().isoformat()

        cursor.execute(
            "INSERT INTO books (title, author, saga_id, date_added) VALUES (?, ?, ?, ?)",
            (title, author, saga_id, date_added)
        )

        if saga_id:
            self.update_saga_metadata(cursor, saga_id)

        book_id = cursor.lastrowid

        # Try to enrich with online data
        print(f"\n🔍 Searching online for '{title}' by {author}...")
        book_info = self.search_book_online(title, author)

        if book_info:
            print("✅ Found book information online!")

            cursor.execute(
                """
                UPDATE books SET
                    isbn = ?,
                    genre = ?,
                    synopsis = ?,
                    cover_url = ?,
                    page_count = ?,
                    publisher = ?,
                    published_date = ?,
                    rating = ?,
                    last_updated = ?
                WHERE id = ?
                """,
                (
                    book_info.get("isbn"),
                    book_info.get("genre"),
                    book_info.get("synopsis"),
                    book_info.get("cover_url"),
                    book_info.get("page_count"),
                    book_info.get("publisher"),
                    book_info.get("published_date"),
                    book_info.get("rating", 0.0),
                    date_added,
                    book_id,
                )
            )
        else:
            print("⚠️ No online information found. Keeping basic entry.")

        if saga_id:
            self.update_saga_metadata(cursor, saga_id)

        conn.commit()
        conn.close()

        return book_id
    
    def update_saga_metadata(self, cursor, saga_id):
        # Get all books in the saga
        cursor.execute("""
            SELECT author, genre, cover_url
            FROM books
            WHERE saga_id = ?
        """, (saga_id,))
        books = cursor.fetchall()

        if not books:
            cursor.execute("""
                UPDATE sagas
                SET num_books = 0
                WHERE id = ?
            """, (saga_id,))
            return

        authors = [b[0] for b in books if b[0]]
        genres = [b[1] for b in books if b[1]]
        covers = [b[2] for b in books if b[2]]

        author = max(set(authors), key=authors.count) if authors else ""
        genre = max(set(genres), key=genres.count) if genres else ""
        cover = covers[0] if covers else ""
        num_books = len(books)

        cursor.execute("""
            UPDATE sagas SET
                author = ?,
                genre = ?,
                cover_url = ?,
                num_books = ?
            WHERE id = ?
        """, (author, genre, cover, num_books, saga_id))


    
    def add_saga(self, name, description=""):
        conn = self.get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO sagas (name, num_books, author, description, cover_url, genre)"
                " VALUES (?, ?, ?, ?, ?, ?)",
                (name, 0, "", description, "", "")
            )
            conn.commit()
        finally:
            conn.close()


    def saga_details(self, saga_id):
        conn = self.get_connection()
        cursor = conn.cursor()

        cursor.execute("""
            SELECT id, name, author, description, cover_url, genre, num_books
            FROM sagas
            WHERE id = ?
        """, (saga_id,))
        saga = cursor.fetchone()

        conn.close()
        return saga




    def get_all_sagas(self):
        conn = self.get_connection()
        cursor = conn.cursor()

        cursor.execute("""
            SELECT id, name, author, cover_url
            FROM sagas
            ORDER BY name
        """)

        sagas = cursor.fetchall()

        conn.close()
        return sagas
    
    def get_books_by_saga(self, saga_id):
        conn = self.get_connection()
        cursor = conn.cursor()

        cursor.execute("""
            SELECT id, title, author, cover_url
            FROM books
            WHERE saga_id = ?
            ORDER BY date_added DESC
        """, (saga_id,))  # <-- MUST be exactly this

        books = cursor.fetchall()
        conn.close()
        return books



    def search_saga_online(self, title, author):
        """Search for book information from multiple online sources"""
        saga_info = {}
            
            # Try Google Books API first
        try:
            print("  Trying Google Books API...")
            google_info = self.search_google_books(title, author)
            if google_info and google_info.get('synopsis'):
                return google_info
        except Exception as e:
            print(f" Google Books failed: {e}")
            
            # Try Open Library API
        try:
            print("  Trying Open Library API...")
            openlib_info = self.search_open_library(title, author)
            if openlib_info and openlib_info.get('synopsis'):
                return openlib_info
        except Exception as e:
            print(f"    Open Library failed: {e}")
            
            # Try Wikipedia
        try:
            print("  Trying Wikipedia...")
            wiki_info = self.search_wikipedia(title, author)
            if wiki_info and wiki_info.get('synopsis'):
                return wiki_info
        except Exception as e:
                print(f"    Wikipedia failed: {e}")
            
        return None

    def search_google_data(self, title, author):
        """Search Google Books API for book information"""
        try:
            search_query = f"{title} {author}"
            search_query = requests.utils.quote(search_query)

            url = (
                "https://www.googleapis.com/books/v1/volumes"
                f"?q={search_query}&maxResults=1"
            )

            headers = {
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36"
                )
            }

            response = requests.get(url, headers=headers, timeout=10)
            data = response.json()

            if "items" in data and len(data["items"]) > 0:
                volume_info = data["items"][0]["volumeInfo"]

                saga_info = {
                    "synopsis": volume_info.get("description", ""),
                    "isbn": self.extract_isbn(
                        volume_info.get("industryIdentifiers", [])
                    ),
                    "genre": ", ".join(
                        volume_info.get("categories", [])
                    )[:100],
                    "cover_url": volume_info.get(
                        "imageLinks", {}
                    ).get("thumbnail", ""),
                    "page_count": volume_info.get("pageCount", 0),
                    "publisher": volume_info.get("publisher", ""),
                    "published_date": volume_info.get("publishedDate", ""),
                    "rating": volume_info.get("averageRating", 0.0),
                }

                return saga_info

        except Exception as e:
            print(f"    Error with Google Books: {e}")

        return None


    def search_open_library(self, title, author):
            """Search Open Library API for book information"""
            try:
                search_query = f"{title} {author}"
                search_query = requests.utils.quote(search_query)
                url = f"https://openlibrary.org/search.json?q={search_query}&limit=1"
                
                headers = {
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
                }
                
                response = requests.get(url, headers=headers, timeout=10)
                data = response.json()
                
                if data.get('docs') and len(data['docs']) > 0:
                    book = data['docs'][0]
                    
                    # Get cover image if available
                    cover_url = ""
                    if 'cover_i' in book:
                        cover_url = f"https://covers.openlibrary.org/b/id/{book['cover_i']}-L.jpg"
                    
                    # Try to get description from work
                    synopsis = ""
                    if 'key' in book:
                        work_url = f"https://openlibrary.org{book['key']}.json"
                        work_response = requests.get(work_url, headers=headers, timeout=10)
                        work_data = work_response.json()
                        
                        if 'description' in work_data:
                            if isinstance(work_data['description'], dict):
                                synopsis = work_data['description'].get('value', '')
                            else:
                                synopsis = work_data['description']
                    
                    saga_info = {
                        'synopsis': synopsis[:2000],  # Limit length
                        'isbn': book.get('isbn', [''])[0] if book.get('isbn') else '',
                        'genre': ', '.join(book.get('subject', []))[:100],
                        'cover_url': cover_url,
                        'page_count': book.get('number_of_pages_median', 0),
                        'publisher': ', '.join(book.get('publisher', []))[:100],
                        'published_date': str(book.get('first_publish_year', ''))
                    }
                    
                    return saga_info
            except Exception as e:
                print(f"    Error with Open Library: {e}")
            
            return None

    def search_wikipedia(self, title, author):
            """Search Wikipedia for book information"""
            try:
                search_query = f"{title} ({author} book)"
                search_query = requests.utils.quote(search_query)
                
                # First, search for the page
                search_url = f"https://en.wikipedia.org/w/api.php?action=query&list=search&srsearch={search_query}&format=json&srlimit=1"
                
                headers = {
                    'User-Agent': 'LibraryBot/1.0 (https://github.com/your-repo)'
                }
                
                response = requests.get(search_url, headers=headers, timeout=10)
                data = response.json()
                
                if data['query']['search']:
                    page_title = data['query']['search'][0]['title']
                    
                    # Get page content
                    content_url = f"https://en.wikipedia.org/w/api.php?action=query&prop=extracts&exintro=1&explaintext=1&titles={requests.utils.quote(page_title)}&format=json"
                    
                    content_response = requests.get(content_url, headers=headers, timeout=10)
                    content_data = content_response.json()
                    
                    pages = content_data['query']['pages']
                    page = list(pages.values())[0]
                    
                    if 'extract' in page:
                        synopsis = page['extract']
                        
                        # Clean up the text
                        synopsis = re.sub(r'\([^)]*\)', '', synopsis)  # Remove parentheses
                        synopsis = re.sub(r'\[[^\]]*\]', '', synopsis)  # Remove brackets
                        synopsis = ' '.join(synopsis.split())  # Remove extra whitespace
                        
                        if len(synopsis) > 1500:
                            synopsis = synopsis[:1500] + "..."
                        
                        saga_info = {
                            'synopsis': synopsis,
                            'source': 'Wikipedia'
                        }
                        
                        return saga_info
            except Exception as e:
                print(f"    Error with Wikipedia: {e}")
            
            return None

    def extract_isbn(self, identifiers):
            """Extract ISBN from industry identifiers"""
            for identifier in identifiers:
                if identifier.get('type') in ['ISBN_13', 'ISBN_10']:
                    return identifier.get('identifier', '')
            return ''

    def update_saga_synopsis(self, saga_id):
        conn = self.get_connection()
        cursor = conn.cursor()

        cursor.execute(
            "SELECT title, author FROM saga WHERE id = ?",
            (saga_id,)
        )
        saga = cursor.fetchone()

        if not saga:
            conn.close()
            print(f"❌ No book found with ID {saga_id}")
            return

        title, author = saga
        print(f"\n🔍 Searching online for '{title}' by {author}...")

        saga_info = self.search_saga_online(title, author)

        if saga_info and saga_info.get("synopsis"):
            update_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

            cursor.execute("""
                UPDATE saga SET
                    genre = COALESCE(?, genre),
                    cover_url = COALESCE(?, cover_url),
                WHERE id = ?
            """, (
                saga_info.get("genre"),
                saga_info.get("cover_url"),
                saga_id
            ))

            conn.commit()
            print(f"✅ Updated '{title}'")

        conn.close()

    def search_book_online(self, title, author):
        """Search for book information from multiple online sources"""
        book_info = {}
            
            # Try Google Books API first
        try:
            print("  Trying Google Books API...")
            google_info = self.search_google_books(title, author)
            if google_info and google_info.get('synopsis'):
                return google_info
        except Exception as e:
            print(f" Google Books failed: {e}")
            
            # Try Open Library API
        try:
            print("  Trying Open Library API...")
            openlib_info = self.search_open_library(title, author)
            if openlib_info and openlib_info.get('synopsis'):
                return openlib_info
        except Exception as e:
            print(f"    Open Library failed: {e}")
            
            # Try Wikipedia
        try:
            print("  Trying Wikipedia...")
            wiki_info = self.search_wikipedia(title, author)
            if wiki_info and wiki_info.get('synopsis'):
                return wiki_info
        except Exception as e:
                print(f"    Wikipedia failed: {e}")
            
        return None
    
    def search_google_books(self, title, author):
        """Search Google Books API for book information"""
        try:
            search_query = f"{title} {author}"
            search_query = requests.utils.quote(search_query)

            url = (
                "https://www.googleapis.com/books/v1/volumes"
                f"?q={search_query}&maxResults=1"
            )

            headers = {
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36"
                )
            }

            response = requests.get(url, headers=headers, timeout=10)
            data = response.json()

            if "items" in data and len(data["items"]) > 0:
                volume_info = data["items"][0]["volumeInfo"]

                book_info = {
                    "synopsis": volume_info.get("description", ""),
                    "isbn": self.extract_isbn(
                        volume_info.get("industryIdentifiers", [])
                    ),
                    "genre": ", ".join(
                        volume_info.get("categories", [])
                    )[:100],
                    "cover_url": volume_info.get(
                        "imageLinks", {}
                    ).get("thumbnail", ""),
                    "page_count": volume_info.get("pageCount", 0),
                    "publisher": volume_info.get("publisher", ""),
                    "published_date": volume_info.get("publishedDate", ""),
                    "rating": volume_info.get("averageRating", 0.0),
                }

                return book_info

        except Exception as e:
            print(f"    Error with Google Books: {e}")

        return None


    def search_open_library(self, title, author):
            """Search Open Library API for book information"""
            try:
                search_query = f"{title} {author}"
                search_query = requests.utils.quote(search_query)
                url = f"https://openlibrary.org/search.json?q={search_query}&limit=1"
                
                headers = {
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
                }
                
                response = requests.get(url, headers=headers, timeout=10)
                data = response.json()
                
                if data.get('docs') and len(data['docs']) > 0:
                    book = data['docs'][0]
                    
                    # Get cover image if available
                    cover_url = ""
                    if 'cover_i' in book:
                        cover_url = f"https://covers.openlibrary.org/b/id/{book['cover_i']}-L.jpg"
                    
                    # Try to get description from work
                    synopsis = ""
                    if 'key' in book:
                        work_url = f"https://openlibrary.org{book['key']}.json"
                        work_response = requests.get(work_url, headers=headers, timeout=10)
                        work_data = work_response.json()
                        
                        if 'description' in work_data:
                            if isinstance(work_data['description'], dict):
                                synopsis = work_data['description'].get('value', '')
                            else:
                                synopsis = work_data['description']
                    
                    book_info = {
                        'synopsis': synopsis[:2000],  # Limit length
                        'isbn': book.get('isbn', [''])[0] if book.get('isbn') else '',
                        'genre': ', '.join(book.get('subject', []))[:100],
                        'cover_url': cover_url,
                        'page_count': book.get('number_of_pages_median', 0),
                        'publisher': ', '.join(book.get('publisher', []))[:100],
                        'published_date': str(book.get('first_publish_year', ''))
                    }
                    
                    return book_info
            except Exception as e:
                print(f"    Error with Open Library: {e}")
            
            return None

    def search_wikipedia(self, title, author):
            """Search Wikipedia for book information"""
            try:
                search_query = f"{title} ({author} book)"
                search_query = requests.utils.quote(search_query)
                
                # First, search for the page
                search_url = f"https://en.wikipedia.org/w/api.php?action=query&list=search&srsearch={search_query}&format=json&srlimit=1"
                
                headers = {
                    'User-Agent': 'LibraryBot/1.0 (https://github.com/your-repo)'
                }
                
                response = requests.get(search_url, headers=headers, timeout=10)
                data = response.json()
                
                if data['query']['search']:
                    page_title = data['query']['search'][0]['title']
                    
                    # Get page content
                    content_url = f"https://en.wikipedia.org/w/api.php?action=query&prop=extracts&exintro=1&explaintext=1&titles={requests.utils.quote(page_title)}&format=json"
                    
                    content_response = requests.get(content_url, headers=headers, timeout=10)
                    content_data = content_response.json()
                    
                    pages = content_data['query']['pages']
                    page = list(pages.values())[0]
                    
                    if 'extract' in page:
                        synopsis = page['extract']
                        
                        # Clean up the text
                        synopsis = re.sub(r'\([^)]*\)', '', synopsis)  # Remove parentheses
                        synopsis = re.sub(r'\[[^\]]*\]', '', synopsis)  # Remove brackets
                        synopsis = ' '.join(synopsis.split())  # Remove extra whitespace
                        
                        if len(synopsis) > 1500:
                            synopsis = synopsis[:1500] + "..."
                        
                        book_info = {
                            'synopsis': synopsis,
                            'source': 'Wikipedia'
                        }
                        
                        return book_info
            except Exception as e:
                print(f"    Error with Wikipedia: {e}")
            
            return None

    def extract_isbn(self, identifiers):
            """Extract ISBN from industry identifiers"""
            for identifier in identifiers:
                if identifier.get('type') in ['ISBN_13', 'ISBN_10']:
                    return identifier.get('identifier', '')
            return ''

    def update_book_synopsis(self, book_id):
        conn = self.get_connection()
        cursor = conn.cursor()

        cursor.execute(
            "SELECT title, author FROM books WHERE id = ?",
            (book_id,)
        )
        book = cursor.fetchone()

        if not book:
            conn.close()
            print(f"❌ No book found with ID {book_id}")
            return

        title, author = book
        print(f"\n🔍 Searching online for '{title}' by {author}...")

        book_info = self.search_book_online(title, author)

        if book_info and book_info.get("synopsis"):
            update_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

            cursor.execute("""
                UPDATE books SET
                    synopsis = ?,
                    isbn = COALESCE(?, isbn),
                    genre = COALESCE(?, genre),
                    cover_url = COALESCE(?, cover_url),
                    page_count = COALESCE(?, page_count),
                    publisher = COALESCE(?, publisher),
                    published_date = COALESCE(?, published_date),
                    rating = COALESCE(?, rating),
                    last_updated = ?
                WHERE id = ?
            """, (
                book_info.get("synopsis"),
                book_info.get("isbn"),
                book_info.get("genre"),
                book_info.get("cover_url"),
                book_info.get("page_count"),
                book_info.get("publisher"),
                book_info.get("published_date"),
                book_info.get("rating", 0.0),
                update_time,
                book_id
            ))

            conn.commit()
            print(f"✅ Updated '{title}'")

        conn.close()


    def view_books(self):
        conn = self.get_connection()
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        cursor.execute("""
            SELECT id, title, author, cover_url
            FROM books
            ORDER BY date_added DESC
        """)

        books = cursor.fetchall()
        conn.close()
        return books


    def view_book_details(self, book_id):
        conn = self.get_connection()
        cursor = conn.cursor()

        cursor.execute("""
            SELECT
                id, title, author, isbn, genre, synopsis,
                cover_url, page_count, publisher, published_date, rating
            FROM books
            WHERE id = ?
        """, (book_id,))

        book = cursor.fetchone()
        conn.close()
        return book


    def search_books(self, query):
        conn = self.get_connection()
        cursor = conn.cursor()

        cursor.execute("""
            SELECT id, title, author
            FROM books
            WHERE title LIKE ? OR author LIKE ?
            ORDER BY title
        """, (f"%{query}%", f"%{query}%"))

        results = cursor.fetchall()
        conn.close()

        return results


    def delete_book(self, book_id):
        conn = self.get_connection()
        cursor = conn.cursor()

        cursor.execute("DELETE FROM books WHERE id = ?", (book_id,))
        deleted = cursor.rowcount

        conn.commit()
        conn.close()
        return deleted > 0

    def delete_saga(self, saga_id):
        conn = self.get_connection()
        cursor = conn.cursor()

        cursor.execute("DELETE FROM sagas WHERE id = ?", (saga_id,))
        deleted = cursor.rowcount

        conn.commit()
        conn.close()
        return deleted > 0

    def get_library_stats(self):
        """Display library statistics."""
        try:
            self.cursor.execute("SELECT COUNT(*) FROM books")
            total_books = self.cursor.fetchone()[0]

            self.cursor.execute("SELECT COUNT(DISTINCT author) FROM books")
            unique_authors = self.cursor.fetchone()[0]

            print("\nLibrary Statistics 💹")
            print(f"Total books: {total_books}")
            print(f"Unique authors: {unique_authors}")

        except sqlite3.Error as e:
            print(f"Error getting statistics: {e}")

    def rate_book(self, book_id, rating):
        conn = self.get_connection()
        cursor = conn.cursor()

        cursor.execute("""
            UPDATE books
            SET rating = ?
            WHERE id = ?
        """, (rating, book_id))

        conn.commit()
        conn.close()

    def get_book_pdf(title: str, author: str) -> Optional[str]:
        """
        Search for a book PDF online
        
        Args:
            title: Book title
            author: Book author
            
        Returns:
            PDF URL if found, None otherwise
        """
        try:
            # Clean inputs
            title = title.strip() if title else ""
            author = author.strip() if author else ""
            
            if not title or not author:
                logger.warning("Title or author is empty")
                return None
            
            # Build the search query
            query = f"{title} {author}"
            encoded_query = urllib.parse.quote(query)
            
            # FIX: Remove parentheses around encoded_query
            search_url = f"https://www.google.com/search?q={encoded_query}"
            
            logger.info(f"Searching for PDF: {query}")
            
            # Add headers to avoid being blocked
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
            }
            
            # Fetch search results page
            response = requests.get(search_url, headers=headers)
            if response.status_code != 200:
                logger.error(f"Google search failed with status: {response.status_code}")
                return None
            
            # Parse HTML
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # FIX: Google doesn't use 'li.booklink' - we need to find actual links
            # Look for PDF links in search results
            pdf_links = []
            
            # Method 1: Look for links containing "pdf" in href
            for link in soup.find_all('a', href=True):
                href = link['href']
                if 'pdf' in href.lower() and 'google' not in href.lower():
                    # Extract actual URL from Google redirect
                    if 'url=' in href:
                        # FIX: Extract URL from Google redirect
                        start = href.find('url=') + 4
                        end = href.find('&', start)
                        pdf_url = href[start:end] if end != -1 else href[start:]
                        pdf_url = urllib.parse.unquote(pdf_url)
                        pdf_links.append(pdf_url)
            
            # Method 2: Look for text containing "PDF"
            for link in soup.find_all('a'):
                if link.text and 'pdf' in link.text.lower():
                    href = link.get('href', '')
                    if href.startswith('/url?q='):
                        # FIX: Handle Google redirect URLs properly
                        pdf_url = href[7:].split('&')[0]
                        pdf_url = urllib.parse.unquote(pdf_url)
                        pdf_links.append(pdf_url)
            
            # Return first PDF link if found
            if pdf_links:
                logger.info(f"Found PDF links: {pdf_links}")
                return pdf_links[0]
            
            # FIX: Alternative approach - search for book previews
            # Look for links to Google Books
            for link in soup.find_all('a', href=True):
                href = link['href']
                if 'books.google.com' in href and 'id=' in href:
                    # Extract book ID
                    book_id = href.split('id=')[1].split('&')[0]
                    
                    # Try to construct PDF URL for Google Books
                    # Note: Many Google Books don't have full PDFs available
                    pdf_url = f"https://books.google.com/books?id={book_id}&printsec=frontcover&source=gbs_ge_summary_r&cad=0#v=onepage&q&f=false"
                    
                    # Check if this might be a PDF (we can't guarantee)
                    logger.info(f"Found Google Books link: {pdf_url}")
                    return pdf_url
            
            logger.info("No PDF found")
            return None
            
        except Exception as e:
            logger.error(f"Error searching for PDF: {e}")
            return None

    def close_connection(self):
        if self.conn:
            self.conn.close()
            print("Database connection closed.")

    
    def get_book_pdf(title, author):
        # build the link
        query = f"{title} {author}"
        encoded_query = urllib.parse.quote(query)
        search_url = f"https://www.google.com/search?query=(encoded_query)"

        # fetch search results page
        response = requests.get(search_url)
        if response.status_code != 200:
            return None
        
        # parse html
        soup = BeautifulSoup(response.text,'html.parser')

        # look for the first book result
        first_book = soup.find('li', class_='booklink')
        if not first_book:
            return None
        
        # get book's page url
        book_page_url = "https://www.google.com" + first_book.find('a')['href']

        # fetch the book page
        book_response = requests.get(book_page_url)
        if book_response.status_code != 200:
            return None
        
        book_soup = BeautifulSoup(book_response.text, 'html.parser')

        # find the pdf link
        pdf_link_tag = book_soup.find('a', string='PDF')
        if pdf_link_tag:
            pdf_url = "https://www.google.com/search?" + pdf_link_tag['href']
            return pdf_url
        
        # if no pdf avaliable
        return None

    # Flask API endpoint version
    def get_book_pdf_api(title: str, author: str, get_book_pdf) -> Dict[str, Any]:
        """
        Flask-friendly version that returns JSON response
        
        Args:
            title: Book title
            author: Book author
            
        Returns:
            Dictionary with status and PDF URL
        """
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
            logger.error(f"API error: {e}")
            return {
                "status": "error",
                "pdf_url": None,
                "message": f"Error searching for PDF: {str(e)}"
            }
        
    def get_book_pdf_enhanced(self, title: str, author: str) -> Optional[str]:
        """
        Enhanced PDF search with multiple sources and methods
        Returns: PDF URL if found, None otherwise
        """
        try:
            # Clean inputs
            title = title.strip()
            author = author.strip()
            
            if not title or not author:
                logger.warning("Title or author is empty")
                return None
            
            print(f"🔍 Searching for PDF: '{title}' by {author}")
            
            # Try multiple search methods in order
            pdf_url = None
            
            # Method 1: Try common book PDF sources
            pdf_url = self._search_multiple_sources(title, author)
            
            # Method 2: Try Google search with specific PDF queries
            if not pdf_url:
                pdf_url = self._search_google_with_queries(title, author)
            
            # Method 3: Try direct searches on known book sites
            if not pdf_url:
                pdf_url = self._search_direct_sites(title, author)
            
            if pdf_url:
                print(f"✅ Found PDF: {pdf_url[:100]}...")
                return pdf_url
            else:
                print("❌ No PDF found")
                return None
                
        except Exception as e:
            logger.error(f"Error searching for PDF: {e}")
            return None

    def _search_multiple_sources(self, title: str, author: str) -> Optional[str]:
        """Try multiple known book PDF sources"""
        sources = [
            self._search_libgen,
            self._search_archive_org_books,
            self._search_pdfdrive_simple,
            self._search_google_books_pdf,
            self._search_openlibrary_pdf
        ]
        
        for source_func in sources:
            try:
                pdf_url = source_func(title, author)
                if pdf_url:
                    return pdf_url
            except Exception as e:
                logger.debug(f"Source {source_func.__name__} failed: {e}")
                continue
        
        return None
    
    def _search_google_with_queries(self, title: str, author: str) -> Optional[str]:
        """Search Google with optimized queries for PDFs"""
        # Common PDF search queries
        queries = [
            f'"{title}" "{author}" filetype:pdf',
            f'"{title}" by {author} pdf download',
            f'{title} {author} pdf free',
            f'{title} book pdf',
            f'{title} pdf download',
            f'intitle:"{title}" filetype:pdf',
            f'{title} {author} "pdf" "download"'
        ]
        
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
        
        for query in queries:
            try:
                encoded_query = urllib.parse.quote(query)
                search_url = f"https://www.google.com/search?q={encoded_query}"
                
                response = requests.get(search_url, headers=headers, timeout=10)
                if response.status_code != 200:
                    continue
                
                soup = BeautifulSoup(response.text, 'html.parser')
                
                # Look for PDF links in search results
                for link in soup.find_all('a', href=True):
                    href = link['href']
                    
                    # Skip Google's own links
                    if 'google.com' in href or href.startswith('/search?') or 'webcache' in href:
                        continue
                    
                    # Check for PDF indicators
                    is_pdf = ('.pdf' in href.lower() or 
                            'pdf' in href.lower() or
                            (link.text and 'pdf' in link.text.lower()))
                    
                    if is_pdf:
                        # Handle Google redirects
                        if href.startswith('/url?q='):
                            # Extract actual URL
                            url_part = href.split('q=')[1]
                            pdf_url = url_part.split('&')[0]
                            pdf_url = urllib.parse.unquote(pdf_url)
                            
                            # Validate it's a real PDF URL
                            if self._is_valid_pdf_url(pdf_url):
                                return pdf_url
                        
                        # Direct PDF link
                        elif href.startswith('http'):
                            if self._is_valid_pdf_url(href):
                                return href
                                
            except Exception as e:
                logger.debug(f"Query '{query}' failed: {e}")
                continue
        
        return None
    
    def _is_valid_pdf_url(self, url: str) -> bool:
        """Check if URL looks like a valid PDF URL"""
        if not url.startswith('http'):
            return False
        
        # Common PDF file extensions
        pdf_extensions = ['.pdf', '.PDF']
        if any(url.endswith(ext) for ext in pdf_extensions):
            return True
        
        # Check for PDF in URL path
        if '/pdf' in url.lower() or 'format=pdf' in url.lower():
            return True
        
        # Known PDF hosting domains
        pdf_domains = [
            'archive.org', 'libgen', 'pdfdrive', 'docdroid',
            'docslib', 'researchgate.net', 'academia.edu',
            'sci-hub', 'booksc.org', 'b-ok', 'zlibrary'
        ]
        
        # Check if URL contains any PDF domain
        for domain in pdf_domains:
            if domain in url.lower():
                return True
        
        return False
    
    def _search_libgen(self, title: str, author: str) -> Optional[str]:
        """Search Library Genesis for PDFs"""
        try:
            # Clean search query
            search_query = f"{title} {author}"
            search_query = urllib.parse.quote(search_query.replace(' ', '+'))
            
            # Try multiple LibGen mirrors
            mirrors = [
                'http://libgen.rs',
                'http://libgen.is',
                'http://libgen.st'
            ]
            
            for mirror in mirrors:
                try:
                    search_url = f"{mirror}/search.php?req={search_query}&lg_topic=libgen&open=0&view=simple&res=25&phrase=1&column=def"
                    
                    headers = {'User-Agent': 'Mozilla/5.0'}
                    response = requests.get(search_url, headers=headers, timeout=15)
                    
                    if response.status_code == 200:
                        soup = BeautifulSoup(response.text, 'html.parser')
                        
                        # Look for download links in the table
                        for row in soup.find_all('tr'):
                            links = row.find_all('a', href=True)
                            for link in links:
                                href = link['href']
                                text = link.get_text().lower()
                                
                                # Check for download links
                                if any(x in text for x in ['download', 'pdf', 'djvu', 'epub']):
                                    # Follow the link to get direct download
                                    try:
                                        if href.startswith('http'):
                                            download_page = requests.get(href, timeout=10)
                                            if download_page.status_code == 200:
                                                soup2 = BeautifulSoup(download_page.text, 'html.parser')
                                                # Look for direct PDF links
                                                for link2 in soup2.find_all('a', href=True):
                                                    link_href = link2['href']
                                                    if link_href.endswith('.pdf'):
                                                        return link_href
                                        elif href.startswith('book/index.php'):
                                            # LibGen direct book link
                                            return f"{mirror}/{href}"
                                    except:
                                        continue
                except:
                    continue
            
            return None
        except Exception as e:
            logger.debug(f"LibGen search failed: {e}")
            return None
        
    def _search_archive_org_books(self, title: str, author: str) -> Optional[str]:
        """Search Archive.org for books"""
        try:
            search_query = f"{title} {author}"
            search_query = urllib.parse.quote(search_query)
            
            # Search Archive.org
            search_url = f"https://archive.org/advancedsearch.php?q={search_query}+AND+mediatype:texts&fl[]=identifier&sort[]=&sort[]=&sort[]=&rows=5&page=1&output=json"
            
            response = requests.get(search_url, timeout=10)
            if response.status_code == 200:
                data = response.json()
                
                if data.get('response', {}).get('docs'):
                    for doc in data['response']['docs']:
                        identifier = doc.get('identifier')
                        if identifier:
                            # Check if PDF exists for this identifier
                            pdf_url = f"https://archive.org/download/{identifier}/{identifier}.pdf"
                            
                            # Test if PDF exists
                            head_response = requests.head(pdf_url, timeout=5)
                            if head_response.status_code == 200:
                                # Check content type
                                content_type = head_response.headers.get('content-type', '')
                                if 'pdf' in content_type.lower():
                                    return pdf_url
            
            return None
        except:
            return None
        
    def _search_pdfdrive_simple(self, title: str, author: str) -> Optional[str]:
        """Search PDF Drive"""
        try:
            search_query = f"{title} {author}"
            search_query = urllib.parse.quote(search_query.replace(' ', '+'))
            
            url = f"https://www.pdfdrive.com/search?q={search_query}"
            
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8'
            }
            
            response = requests.get(url, headers=headers, timeout=10)
            
            if response.status_code == 200:
                soup = BeautifulSoup(response.text, 'html.parser')
                
                # Look for download buttons
                for link in soup.find_all('a', href=True):
                    href = link['href']
                    
                    # PDF Drive download links
                    if '/download' in href and not href.startswith('http'):
                        # Get the actual download link
                        download_url = f"https://www.pdfdrive.com{href}"
                        
                        # Follow to get direct download
                        try:
                            download_page = requests.get(download_url, headers=headers, timeout=10)
                            if download_page.status_code == 200:
                                soup2 = BeautifulSoup(download_page.text, 'html.parser')
                                
                                # Look for the download button with data-id
                                download_btn = soup2.find('button', {'id': 'download-button'})
                                if download_btn and download_btn.get('data-id'):
                                    file_id = download_btn['data-id']
                                    return f"https://www.pdfdrive.com/download.pdf?id={file_id}"
                        except:
                            continue
            
            return None
        except:
            return None
        
    def _search_direct_sites(self, title: str, author: str) -> Optional[str]:

        """Try direct searches on known book sites"""
        try:
            # Clean the title and author for URL
            clean_title = urllib.parse.quote(title.replace(' ', '+'))
            clean_author = urllib.parse.quote(author.replace(' ', '+'))
            
            # Common book PDF sites patterns
            sites_patterns = [
                f"https://www.gutenberg.org/ebooks/search/?query={clean_title}+{clean_author}",
                f"https://manybooks.net/search-book?search={clean_title}",
                f"https://www.free-ebooks.net/search/{clean_title}",
                f"https://www.smashwords.com/books/search?query={clean_title}"
            ]
            
            headers = {'User-Agent': 'Mozilla/5.0'}
            
            for url in sites_patterns:
                try:
                    response = requests.get(url, headers=headers, timeout=10)
                    if response.status_code == 200:
                        soup = BeautifulSoup(response.text, 'html.parser')
                        
                        # Look for PDF download links
                        for link in soup.find_all('a', href=True):
                            href = link['href']
                            text = link.get_text().lower()
                            
                            if 'pdf' in text or '.pdf' in href.lower():
                                # Make absolute URL if relative
                                if href.startswith('/'):
                                    # Handle relative URLs based on site
                                    if 'gutenberg.org' in url:
                                        return f"https://www.gutenberg.org{href}"
                                elif href.startswith('http'):
                                    return href
                except:
                    continue
            
            return None
        except:
            return None
        
    def download_pdf_file(self, pdf_url: str, book_id: int = None) -> Optional[str]:
        """
        Download PDF from URL and save it
        Returns: Path to downloaded PDF file or None if failed
        """
        try:
            if not pdf_url:
                logger.warning("No PDF URL provided")
                return None
            
            print(f"📥 Downloading PDF from: {pdf_url[:100]}...")
            
            # Set up headers for download
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                'Accept': 'application/pdf,application/octet-stream,*/*',
                'Accept-Language': 'en-US,en;q=0.5',
                'Accept-Encoding': 'gzip, deflate, br',
                'Referer': 'https://www.google.com/',
                'DNT': '1',
                'Connection': 'keep-alive',
                'Upgrade-Insecure-Requests': '1',
                'Sec-Fetch-Dest': 'document',
                'Sec-Fetch-Mode': 'navigate',
                'Sec-Fetch-Site': 'none',
                'Sec-Fetch-User': '?1'
            }
            
            # First, send a HEAD request to check the file
            try:
                head_response = requests.head(pdf_url, headers=headers, timeout=10, allow_redirects=True)
                
                # Check if it's actually a PDF
                content_type = head_response.headers.get('content-type', '').lower()
                content_length = head_response.headers.get('content-length', '0')
                
                if 'pdf' not in content_type and not pdf_url.lower().endswith('.pdf'):
                    print(f"⚠️ URL doesn't appear to be a PDF. Content-Type: {content_type}")
                    # Continue anyway, some sites don't set proper headers
            except Exception as e:
                print(f"⚠️ Could not check file headers: {e}")
                # Continue with download anyway
            
            # Download the file with streaming
            response = requests.get(pdf_url, headers=headers, stream=True, timeout=30)
            response.raise_for_status()
            
            # Create filename
            filename = self._create_pdf_filename(pdf_url, response, book_id)
            
            # Create downloads directory if it doesn't exist
            download_dir = self.epub_dir
            os.makedirs(download_dir, exist_ok=True)
            
            filepath = os.path.join(download_dir, filename)
            
            # Save file with progress
            total_size = int(response.headers.get('content-length', 0))
            downloaded = 0
            
            print(f"💾 Saving to: {filepath}")
            
            with open(filepath, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
                        downloaded += len(chunk)
                        
                        # Show progress for large files
                        if total_size > 0:
                            percent = (downloaded / total_size) * 100
                            if int(percent) % 10 == 0:  # Update every 10%
                                print(f"📦 Downloading: {percent:.1f}% ({downloaded/1024/1024:.1f} MB / {total_size/1024/1024:.1f} MB)")
            
            # Verify file was downloaded
            if not os.path.exists(filepath):
                print(f"❌ File was not saved: {filepath}")
                return None
            
            file_size = os.path.getsize(filepath)
            
            # Verify it's a valid PDF
            is_valid_pdf = self._verify_pdf_file(filepath)
            
            if not is_valid_pdf:
                print(f"⚠️ Downloaded file may not be a valid PDF: {filepath}")
                # Don't delete it yet - let user decide
            
            print(f"✅ PDF downloaded successfully!")
            print(f"   Size: {file_size:,} bytes ({file_size/1024/1024:.2f} MB)")
            print(f"   Path: {filepath}")
            
            return filepath
            
        except requests.exceptions.Timeout:
            print(f"❌ Download timeout: {pdf_url}")
            return None
        except requests.exceptions.RequestException as e:
            print(f"❌ Download error: {e}")
            return None
        except Exception as e:
            logger.error(f"Error downloading PDF: {e}")
            return None
        
    def _create_pdf_filename(self, pdf_url: str, response: requests.Response, book_id: int = None) -> str:
        """Create a safe filename for the PDF"""
        filename = ""
        
        # Try to get filename from Content-Disposition header
        if 'content-disposition' in response.headers:
            content_disp = response.headers['content-disposition']
            if 'filename=' in content_disp:
                filename = content_disp.split('filename=')[1].strip('"\'').strip()
        
        # If no filename from header, use URL or book info
        if not filename:
            if book_id:
                filename = f"book_{book_id}.pdf"
            elif pdf_url.lower().endswith('.pdf'):
                # Extract filename from URL
                filename = pdf_url.split('/')[-1].split('?')[0]
            else:
                # Generate a generic filename
                filename = f"book_{int(time.time())}.pdf"
        
        # Clean the filename
        filename = re.sub(r'[^\w\-_. ]', '', filename)
        filename = filename.strip()
        
        # Ensure it has .pdf extension
        if not filename.lower().endswith('.pdf'):
            filename += '.pdf'
        
        return filename
    
    def _verify_pdf_file(self, filepath: str) -> bool:
        """Verify if file is a valid PDF"""
        try:
            # Check file exists and has content
            if not os.path.exists(filepath):
                return False
            
            file_size = os.path.getsize(filepath)
            if file_size < 100:  # Less than 100 bytes is probably not a PDF
                return False
            
            # Check PDF header
            with open(filepath, 'rb') as f:
                header = f.read(4)
                if header == b'%PDF':
                    return True
                
                # Some PDFs might have version number immediately after
                f.seek(0)
                first_bytes = f.read(1024)
                if b'%PDF' in first_bytes:
                    return True
                
                # Check for other PDF indicators
                f.seek(0)
                content = f.read(4096)
                if b'obj' in content and b'endobj' in content:
                    return True
            
            return False
        except Exception as e:
            logger.debug(f"PDF verification error: {e}")
            return False
        
    def find_and_download_pdf_for_book(self, book_id: int) -> Optional[str]:
        """
        Complete function: Find and download PDF for a specific book
        Returns: Path to downloaded PDF or None
        """
        try:
            # Get book details from database
            book = self.view_book_details(book_id)
            if not book:
                print(f"❌ Book with ID {book_id} not found")
                return None
            
            title = book['title']
            author = book['author']
            
            print(f"\n{'='*60}")
            print(f"📚 Searching for PDF: '{title}' by {author}")
            print('='*60)
            
            # Search for PDF URL
            pdf_url = self.get_book_pdf_enhanced(title, author)
            
            if not pdf_url:
                print("❌ No PDF URL found")
                return None
            
            # Download the PDF
            pdf_path = self.download_pdf_file(pdf_url, book_id)
            
            if pdf_path:
                # Update database with PDF path
                conn = self.get_connection()
                cursor = conn.cursor()
                
                file_size = os.path.getsize(pdf_path) if os.path.exists(pdf_path) else 0
                
                cursor.execute("""
                    UPDATE books SET 
                        pdf_path = ?,
                        file_size = ?
                    WHERE id = ?
                """, (pdf_path, file_size, book_id))
                
                conn.commit()
                conn.close()
                
                print(f"✅ Database updated with PDF path")
                return pdf_path
            else:
                print("❌ PDF download failed")
                return None
                
        except Exception as e:
            logger.error(f"Error in find_and_download_pdf_for_book: {e}")
            return None


def display_menu():
    print("\n" + "=" * 50)
    print("Book Library Management System")
    print("=" * 50)
    print("1. Add a new book")
    print("2. View all books")
    print("3. Search for books")
    print("4. Delete a book")
    print("5. View library statistics")
    print("6. Exit")
    print("=" * 50)


def main():
    library = BookLibrary()

    while True:
        display_menu()
        choice = input("Enter your choice (1-6): ").strip()

        if choice == '1':
            library.add_book()
        elif choice == '2':
            library.view_books()
        elif choice == '3':
            library.search_books()
        elif choice == '4':
            library.delete_book()
        elif choice == '5':
            library.get_library_stats()
        elif choice == '6':
            library.close_connection()
            print("Goodbye 👋")
            break
        else:
            print("Invalid choice.")


if __name__ == "__main__":
    main()