from flask import Flask, request, jsonify, send_file
from flask_cors import CORS
from bs4 import BeautifulSoup
# import pandas as pd
import io
import os
import tempfile
import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from functools import wraps
import gc
import logging
import pandas as pd
from werkzeug.serving import WSGIRequestHandler

from services import convert_html_to_excel, extract_html_content

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)
CORS(app)

# Configuration for concurrent users
MAX_WORKERS = 15  # Can handle more than 10 concurrent requests
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB
REQUEST_TIMEOUT = 300  # 5 minutes timeout
MAX_CONCURRENT_REQUESTS = 12

# Thread pool for processing requests
executor = ThreadPoolExecutor(max_workers=MAX_WORKERS)

# Request tracking
active_requests = {}
request_lock = threading.Lock()

class RequestTracker:
    def __init__(self):
        self.count = 0
        self.lock = threading.Lock()
    
    def can_accept_request(self):
        with self.lock:
            return self.count < MAX_CONCURRENT_REQUESTS
    
    def add_request(self):
        with self.lock:
            self.count += 1
            logger.info(f"Active requests: {self.count}")
    
    def remove_request(self):
        with self.lock:
            self.count = max(0, self.count - 1)
            logger.info(f"Active requests: {self.count}")

request_tracker = RequestTracker()

def rate_limit(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not request_tracker.can_accept_request():
            return jsonify({
                'error': 'Server is busy. Please try again in a moment.',
                'code': 'SERVER_BUSY'
            }), 503
        
        request_tracker.add_request()
        request_id = str(uuid.uuid4())
        
        try:
            with request_lock:
                active_requests[request_id] = time.time()
            
            result = f(*args, **kwargs)
            return result
        finally:
            request_tracker.remove_request()
            with request_lock:
                active_requests.pop(request_id, None)
            # Force garbage collection after each request
            gc.collect()
    
    return decorated_function

def process_html_content(html_content, filename):
    """Process HTML content in a separate thread"""
    try:
        logger.info(f"Processing file: {filename}")
        
        # Extract tables with memory efficiency
        tables = extract_tables_from_html(html_content)
        logger.info(f"Extracted {len(tables)} tables")
        
        # Extract text content
        text_content = extract_text_content(html_content)
        logger.info(f"Extracted {len(text_content)} text elements")
        
        # Extract meta information
        meta_info = extract_meta_information(html_content)
        logger.info(f"Extracted {len(meta_info)} meta tags")
        
        # Create a temporary HTML file
        current_directory = os.getcwd()
        extractedhtml_file_path = os.path.join(current_directory, 'temporaryHTML.html')
        print(extractedhtml_file_path)
        # Write the extracted HTML file 
        extract_html_content(extractedhtml_file_path, html_content)

        # Convert HTML to Excel
        excel_output = os.path.join(current_directory,"html2image2excel_output.xlsx")
        convert_html_to_excel(extractedhtml_file_path, excel_output_path=excel_output, class_selector=".image-box")

        # Read the Excel file into memory
        with open(excel_output, "rb") as f:
            file_data = f.read()

        # Load workbook from memory
        excel_output = io.BytesIO(file_data)

        # Save Excel to memory
        excel_output.seek(0)

        return excel_output
        
    except Exception as e:
        logger.error(f"Error processing {filename}: {str(e)}")
        raise e

def extract_tables_from_html(html_content):
    """Extract tables from HTML content with memory optimization"""
    try:
        soup = BeautifulSoup(html_content, 'html.parser')
        tables = soup.find_all('table')
        
        dataframes = []
        
        for i, table in enumerate(tables):
            try:
                # Extract table data efficiently
                rows = []
                headers = []
                
                # Find headers
                header_row = table.find('thead')
                if header_row:
                    header_cells = header_row.find_all(['th', 'td'])
                    headers = [cell.get_text(strip=True) for cell in header_cells]
                else:
                    first_row = table.find('tr')
                    if first_row:
                        first_row_cells = first_row.find_all(['th', 'td'])
                        if any(cell.name == 'th' for cell in first_row_cells):
                            headers = [cell.get_text(strip=True) for cell in first_row_cells]
                
                # Extract all rows efficiently
                for row in table.find_all('tr'):
                    cells = row.find_all(['td', 'th'])
                    if cells:
                        row_data = [cell.get_text(strip=True) for cell in cells]
                        rows.append(row_data)
                
                if rows:
                    # Skip header row if it matches
                    if headers and len(rows) > 0 and len(headers) == len(rows[0]):
                        if headers == rows[0]:
                            rows = rows[1:]
                    
                    # Create DataFrame with error handling
                    if headers and len(headers) > 0:
                        max_cols = len(headers)
                        for j, row in enumerate(rows):
                            while len(row) < max_cols:
                                row.append('')
                            rows[j] = row[:max_cols]
                        
                        df = pd.DataFrame(rows, columns=headers)
                    else:
                        df = pd.DataFrame(rows)
                    
                    dataframes.append({
                        'data': df,
                        'title': f'Table_{i+1}',
                        'index': i
                    })
                    
            except Exception as e:
                logger.warning(f"Error processing table {i}: {str(e)}")
                continue
        
        # Clean up BeautifulSoup object
        soup.decompose()
        return dataframes
        
    except Exception as e:
        logger.error(f"Error in table extraction: {str(e)}")
        return []

def extract_text_content(html_content):
    """Extract text content with memory optimization"""
    try:
        soup = BeautifulSoup(html_content, 'html.parser')
        
        # Remove script and style elements
        for script in soup(["script", "style"]):
            script.decompose()
        
        content_data = []
        
        # Extract title
        title = soup.find('title')
        if title:
            content_data.append(['Title', title.get_text(strip=True)])
        
        # Extract headings
        headings = soup.find_all(['h1', 'h2', 'h3', 'h4', 'h5', 'h6'])
        for heading in headings:
            level = heading.name.upper()
            text = heading.get_text(strip=True)
            if text:
                content_data.append([f'{level}', text])
        
        # Extract paragraphs (limit to prevent memory issues)
        paragraphs = soup.find_all('p')[:100]  # Limit to first 100 paragraphs
        for i, p in enumerate(paragraphs):
            text = p.get_text(strip=True)
            if text:
                content_data.append([f'Paragraph_{i+1}', text[:500]])  # Limit text length
        
        # Extract lists (limit to prevent memory issues)
        lists = soup.find_all(['ul', 'ol'])[:20]  # Limit to first 20 lists
        for i, lst in enumerate(lists):
            list_type = 'Ordered List' if lst.name == 'ol' else 'Unordered List'
            items = lst.find_all('li')[:20]  # Limit items per list
            for j, item in enumerate(items):
                text = item.get_text(strip=True)
                if text:
                    content_data.append([f'{list_type}_{i+1}_Item_{j+1}', text[:200]])
        
        # Extract links (limit to prevent memory issues)
        links = soup.find_all('a', href=True)[:50]  # Limit to first 50 links
        for i, link in enumerate(links):
            text = link.get_text(strip=True)
            href = link['href']
            if text and href:
                content_data.append([f'Link_{i+1}_Text', text[:100]])
                content_data.append([f'Link_{i+1}_URL', href[:200]])
        
        soup.decompose()
        return content_data
        
    except Exception as e:
        logger.error(f"Error in text extraction: {str(e)}")
        return []

def extract_meta_information(html_content):
    """Extract meta information with error handling"""
    try:
        soup = BeautifulSoup(html_content, 'html.parser')
        
        meta_data = []
        
        # Extract meta tags
        meta_tags = soup.find_all('meta')
        for meta in meta_tags:
            try:
                if meta.get('name'):
                    content = meta.get('content', '')[:500]  # Limit content length
                    meta_data.append([f'Meta_{meta["name"]}', content])
                elif meta.get('property'):
                    content = meta.get('content', '')[:500]
                    meta_data.append([f'Property_{meta["property"]}', content])
            except Exception:
                continue
        
        soup.decompose()
        return meta_data
        
    except Exception as e:
        logger.error(f"Error in meta extraction: {str(e)}")
        return []

@app.route('/process', methods=['POST'])
@rate_limit
def process_html():
    try:
        # Validate request
        if 'html_file' not in request.files:
            return jsonify({'error': 'No file uploaded', 'code': 'NO_FILE'}), 400
        
        file = request.files['html_file']
        
        if file.filename == '':
            return jsonify({'error': 'No file selected', 'code': 'EMPTY_FILENAME'}), 400
        
        # Check file size
        file.seek(0, os.SEEK_END)
        file_size = file.tell()
        file.seek(0)
        
        if file_size > MAX_FILE_SIZE:
            return jsonify({
                'error': f'File size ({file_size} bytes) exceeds limit ({MAX_FILE_SIZE} bytes)',
                'code': 'FILE_TOO_LARGE'
            }), 413
        
        # Read HTML content with encoding handling
        try:
            html_content = file.read().decode('utf-8', errors='ignore')
        except UnicodeDecodeError:
            try:
                file.seek(0)
                html_content = file.read().decode('latin-1', errors='ignore')
            except:
                return jsonify({
                    'error': 'Unable to decode file content',
                    'code': 'ENCODING_ERROR'
                }), 400
        
        # Process in thread pool
        future = executor.submit(process_html_content, html_content, file.filename)
        
        try:
            # Wait for processing with timeout
            output = future.result(timeout=REQUEST_TIMEOUT)
            
            # Generate output filename
            original_name = os.path.splitext(file.filename)[0]
            output_filename = f"{original_name}_processed.xlsx"
            
            return send_file(
                output,
                as_attachment=True,
                download_name=output_filename,
                mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
            )
            
        except TimeoutError:
            return jsonify({
                'error': 'Processing timeout. File may be too complex.',
                'code': 'TIMEOUT'
            }), 408
        
    except Exception as e:
        logger.error(f"Error in process_html: {str(e)}")
        return jsonify({
            'error': f'Processing failed: {str(e)}',
            'code': 'PROCESSING_ERROR'
        }), 500

@app.route('/health', methods=['GET'])
def health_check():
    with request_lock:
        active_count = len(active_requests)
    
    return jsonify({
        'status': 'Server is running',
        'message': 'HTML to Excel converter is ready',
        'active_requests': active_count,
        'max_concurrent': MAX_CONCURRENT_REQUESTS,
        'server_load': f"{(active_count/MAX_CONCURRENT_REQUESTS)*100:.1f}%"
    })

@app.route('/status', methods=['GET'])
def server_status():
    with request_lock:
        active_count = len(active_requests)
    
    return jsonify({
        'server_info': {
            'active_requests': active_count,
            'max_concurrent_requests': MAX_CONCURRENT_REQUESTS,
            'max_workers': MAX_WORKERS,
            'server_load_percentage': round((active_count/MAX_CONCURRENT_REQUESTS)*100, 1),
            'available_slots': MAX_CONCURRENT_REQUESTS - active_count
        },
        'limits': {
            'max_file_size_mb': MAX_FILE_SIZE / (1024*1024),
            'request_timeout_seconds': REQUEST_TIMEOUT
        }
    })

@app.route('/', methods=['GET'])
def home():
    return jsonify({
        'message': 'HTML to Excel Converter API - Production Ready',
        'endpoints': {
            '/process': 'POST - Upload HTML file for processing',
            '/health': 'GET - Health check',
            '/status': 'GET - Detailed server status'
        },
        'features': {
            'concurrent_users': f'Up to {MAX_CONCURRENT_REQUESTS} concurrent requests',
            'max_file_size': f'{MAX_FILE_SIZE/(1024*1024)}MB',
            'thread_pool_workers': MAX_WORKERS
        }
    })

# Custom request handler to improve performance
class ThreadedWSGIRequestHandler(WSGIRequestHandler):
    def handle(self):
        """Handle a single HTTP request with improved error handling"""
        try:
            super().handle()
        except Exception as e:
            logger.error(f"Request handling error: {str(e)}")

if __name__ == '__main__':
    print("=" * 60)
    print("HTML to Excel Converter Server - Production Ready")
    print("=" * 60)
    print(f"Server Configuration:")
    print(f"  • Max Concurrent Users: {MAX_CONCURRENT_REQUESTS}")
    print(f"  • Thread Pool Workers: {MAX_WORKERS}")
    print(f"  • Max File Size: {MAX_FILE_SIZE/(1024*1024)}MB")
    print(f"  • Request Timeout: {REQUEST_TIMEOUT}s")
    print("=" * 60)
    print("Server will run on http://localhost:5000")
    print("Available endpoints:")
    print("  • POST /process - Upload HTML file for conversion")
    print("  • GET /health - Health check with load info")
    print("  • GET /status - Detailed server status")
    print("  • GET / - API information")
    print("=" * 60)
    print("Required dependencies:")
    print("  pip install flask flask-cors beautifulsoup4 pandas openpyxl")
    print("=" * 60)
    
    # Run with threading enabled
    app.run(
        debug=False,  # Disabled for production
        host='0.0.0.0',
        port=5000,
        threaded=True,  # Enable threading
        request_handler=ThreadedWSGIRequestHandler
    )