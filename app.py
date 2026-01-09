from flask import Flask, request, render_template_string, send_file, jsonify, flash, redirect, url_for, render_template
import os
import io
import tempfile
import uuid
from werkzeug.utils import secure_filename
from werkzeug.exceptions import RequestEntityTooLarge
import logging
from datetime import datetime, timedelta
import threading
import time
from tools.unminify import unminify_bp

# PDF processing libraries
try:
    from pypdf import PdfReader, PdfWriter
    PDF_LIB = 'pypdf'
except ImportError:
    try:
        from PyPDF2 import PdfReader, PdfWriter
        PDF_LIB = 'PyPDF2'
    except ImportError:
        raise ImportError("Please install pypdf or PyPDF2: pip install pypdf")

app = Flask(__name__)
app.secret_key = 'your-secret-key-change-this-in-production'
app.config['MAX_CONTENT_LENGTH'] = 50 * 1024 * 1024  # 50MB max file size

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Store for processed files (in production, use Redis or database)
processed_files = {}
cleanup_interval = 3600  # Clean up files older than 1 hour


def remove_pdf_password(file_content, password):
    """Remove password from PDF file"""
    try:
        # Create a BytesIO object from file content
        pdf_file = io.BytesIO(file_content)

        # Read the PDF
        reader = PdfReader(pdf_file)

        # Check if the PDF is encrypted
        if reader.is_encrypted:
            # Try to decrypt with the provided password
            if not reader.decrypt(password):
                raise ValueError("Incorrect password provided")

        # Create a new PDF writer
        writer = PdfWriter()

        # Copy all pages to the new PDF
        for page in reader.pages:
            writer.add_page(page)

        # Write the new PDF to a BytesIO object
        output_pdf = io.BytesIO()
        writer.write(output_pdf)
        output_pdf.seek(0)

        return output_pdf.getvalue()

    except Exception as e:
        logger.error(f"Error removing PDF password: {str(e)}")
        raise

def cleanup_old_files():
    """Clean up old processed files"""
    while True:
        try:
            current_time = datetime.now()
            to_remove = []

            for file_id, file_info in processed_files.items():
                if current_time - file_info['created_at'] > timedelta(seconds=cleanup_interval):
                    to_remove.append(file_id)

            for file_id in to_remove:
                if file_id in processed_files:
                    # Remove from memory
                    del processed_files[file_id]
                    logger.info(f"Cleaned up file: {file_id}")

        except Exception as e:
            logger.error(f"Error in cleanup: {str(e)}")

        time.sleep(300)  # Run cleanup every 5 minutes

# Start cleanup thread
cleanup_thread = threading.Thread(target=cleanup_old_files, daemon=True)
cleanup_thread.start()

@app.route('/')
def index():
    """Serve the main page"""
    #return render_template_string(HTML_TEMPLATE)
    return render_template("index.html")

@app.route('/tools')
def tools():
    """Serve the tools page"""
    #return render_template_string(TOOLS_TEMPLATE)
    return render_template("tools.html")

@app.route('/api/remove-password', methods=['POST'])
def remove_password():
    """API endpoint to remove PDF password"""
    try:
        # Check if file is present
        if 'pdf_file' not in request.files:
            return jsonify({'success': False, 'error': 'No file uploaded'}), 400

        file = request.files['pdf_file']
        password = request.form.get('password', '')

        if file.filename == '':
            return jsonify({'success': False, 'error': 'No file selected'}), 400

        if not password:
            return jsonify({'success': False, 'error': 'Password is required'}), 400

        # Validate file type
        if not file.filename.lower().endswith('.pdf'):
            return jsonify({'success': False, 'error': 'Only PDF files are allowed'}), 400

        # Read file content
        file_content = file.read()

        # Validate file size
        if len(file_content) > 50 * 1024 * 1024:  # 50MB
            return jsonify({'success': False, 'error': 'File size too large (max 50MB)'}), 400

        # Process the PDF
        try:
            unlocked_pdf = remove_pdf_password(file_content, password)
        except ValueError as e:
            return jsonify({'success': False, 'error': str(e)}), 400
        except Exception as e:
            logger.error(f"PDF processing error: {str(e)}")
            return jsonify({'success': False, 'error': 'Failed to process PDF. The file may be corrupted or the password is incorrect.'}), 500

        # Generate unique file ID
        file_id = str(uuid.uuid4())

        # Store the processed file in memory (use database/Redis in production)
        processed_files[file_id] = {
            'content': unlocked_pdf,
            'filename': file.filename,
            'created_at': datetime.now()
        }

        logger.info(f"Successfully processed PDF: {file.filename}")

        return jsonify({
            'success': True,
            'file_id': file_id,
            'message': 'Password removed successfully'
        })

    except RequestEntityTooLarge:
        return jsonify({'success': False, 'error': 'File too large'}), 413
    except Exception as e:
        logger.error(f"Unexpected error: {str(e)}")
        return jsonify({'success': False, 'error': 'An unexpected error occurred'}), 500

@app.route('/api/download/<file_id>')
def download_file(file_id):
    """Download the processed PDF file"""
    try:
        if file_id not in processed_files:
            return jsonify({'error': 'File not found or expired'}), 404

        file_info = processed_files[file_id]

        # Create a BytesIO object with the PDF content
        pdf_io = io.BytesIO(file_info['content'])
        pdf_io.seek(0)

        # Generate download filename
        original_filename = file_info['filename']
        download_filename = f"unlocked_{original_filename}"

        return send_file(
            pdf_io,
            as_attachment=True,
            download_name=download_filename,
            mimetype='application/pdf'
        )

    except Exception as e:
        logger.error(f"Download error: {str(e)}")
        return jsonify({'error': 'Failed to download file'}), 500

@app.errorhandler(413)
def too_large(e):
    """Handle file too large error"""
    return jsonify({'success': False, 'error': 'File too large (max 50MB)'}), 413

@app.errorhandler(500)
def internal_error(e):
    """Handle internal server error"""
    return jsonify({'success': False, 'error': 'Internal server error'}), 500
# Register unminify blueprint
app.register_blueprint(unminify_bp)
if __name__ == '__main__':
    # Create uploads directory if it doesn't exist
    os.makedirs('uploads', exist_ok=True)

    logger.info(f"Using PDF library: {PDF_LIB}")
    logger.info("Starting PDF Password Remover application...")

    # Run the app
    app.run(debug=True, host='0.0.0.0', port=5001)