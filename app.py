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

# Tools page HTML template
TOOLS_TEMPLATE = '''
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>PDF Tools - Professional PDF Solutions</title>
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }

        body {
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            display: flex;
            flex-direction: column;
        }

        /* Navigation */
        .navbar {
            background: rgba(255, 255, 255, 0.95);
            backdrop-filter: blur(10px);
            padding: 1rem 0;
            box-shadow: 0 2px 20px rgba(0,0,0,0.1);
            position: sticky;
            top: 0;
            z-index: 1000;
        }

        .nav-container {
            max-width: 1400px;
            margin: 0 auto;
            padding: 0 2rem;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }

        .logo {
            display: flex;
            align-items: center;
            font-size: 1.5rem;
            font-weight: bold;
            color: #2c3e50;
            text-decoration: none;
        }

        .logo-icon {
            font-size: 2rem;
            margin-right: 0.5rem;
        }

        .nav-menu {
            display: flex;
            list-style: none;
            gap: 2rem;
        }

        .nav-link {
            color: #2c3e50;
            text-decoration: none;
            font-weight: 500;
            transition: all 0.3s ease;
            padding: 0.5rem 1rem;
            border-radius: 8px;
        }

        .nav-link:hover, .nav-link.active {
            background: #667eea;
            color: white;
            transform: translateY(-2px);
        }

        /* Main Content */
        .main-wrapper {
            flex: 1;
            padding: 3rem 0;
        }

        .container {
            max-width: 1400px;
            margin: 0 auto;
            padding: 0 2rem;
        }

        .hero-section {
            text-align: center;
            margin-bottom: 4rem;
            color: white;
        }

        .hero-title {
            font-size: 3rem;
            margin-bottom: 1rem;
            font-weight: 700;
        }

        .hero-subtitle {
            font-size: 1.3rem;
            opacity: 0.9;
            max-width: 600px;
            margin: 0 auto;
            line-height: 1.6;
        }

        .tools-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(350px, 1fr));
            gap: 2rem;
            margin-bottom: 4rem;
        }

        .tool-card {
            background: rgba(255, 255, 255, 0.95);
            backdrop-filter: blur(10px);
            border-radius: 20px;
            padding: 2rem;
            text-align: center;
            transition: all 0.3s ease;
            border: 2px solid transparent;
            position: relative;
            overflow: hidden;
        }

        .tool-card::before {
            content: '';
            position: absolute;
            top: 0;
            left: 0;
            right: 0;
            height: 4px;
            background: linear-gradient(90deg, #667eea, #764ba2);
        }

        .tool-card:hover {
            transform: translateY(-8px);
            box-shadow: 0 20px 40px rgba(0,0,0,0.15);
            border-color: #667eea;
        }

        .tool-card.featured {
            border: 2px solid #f39c12;
            transform: scale(1.02);
        }

        .tool-card.featured::before {
            background: linear-gradient(90deg, #f39c12, #e67e22);
        }

        .tool-card.featured .tool-badge {
            position: absolute;
            top: 1rem;
            right: 1rem;
            background: #f39c12;
            color: white;
            padding: 0.3rem 0.8rem;
            border-radius: 20px;
            font-size: 0.8rem;
            font-weight: bold;
        }

        .tool-icon {
            font-size: 4rem;
            margin-bottom: 1rem;
            display: block;
        }

        .tool-title {
            font-size: 1.5rem;
            font-weight: 600;
            color: #2c3e50;
            margin-bottom: 0.8rem;
        }

        .tool-description {
            color: #7f8c8d;
            line-height: 1.6;
            margin-bottom: 1.5rem;
            min-height: 3rem;
        }

        .tool-features {
            list-style: none;
            margin-bottom: 2rem;
            text-align: left;
        }

        .tool-features li {
            color: #34495e;
            margin-bottom: 0.5rem;
            display: flex;
            align-items: center;
        }

        .tool-features li::before {
            content: "✓";
            color: #27ae60;
            font-weight: bold;
            margin-right: 0.5rem;
            background: #e8f5e8;
            border-radius: 50%;
            width: 20px;
            height: 20px;
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 0.8rem;
        }

        .tool-button {
            background: linear-gradient(45deg, #667eea, #764ba2);
            color: white;
            padding: 12px 24px;
            border: none;
            border-radius: 25px;
            font-size: 1rem;
            font-weight: 600;
            cursor: pointer;
            text-decoration: none;
            display: inline-block;
            transition: all 0.3s ease;
            width: 100%;
        }

        .tool-button:hover {
            transform: translateY(-2px);
            box-shadow: 0 8px 20px rgba(102, 126, 234, 0.3);
        }

        .tool-button.coming-soon {
            background: #bdc3c7;
            cursor: not-allowed;
        }

        .tool-button.coming-soon:hover {
            transform: none;
            box-shadow: none;
        }

        .categories {
            margin-bottom: 3rem;
        }

        .category-filters {
            display: flex;
            justify-content: center;
            gap: 1rem;
            margin-bottom: 3rem;
            flex-wrap: wrap;
        }

        .filter-btn {
            background: rgba(255, 255, 255, 0.2);
            color: white;
            border: 2px solid rgba(255, 255, 255, 0.3);
            padding: 0.8rem 1.5rem;
            border-radius: 25px;
            cursor: pointer;
            transition: all 0.3s ease;
            font-weight: 500;
        }

        .filter-btn:hover, .filter-btn.active {
            background: rgba(255, 255, 255, 0.9);
            color: #2c3e50;
            border-color: transparent;
        }

        .stats-section {
            background: rgba(255, 255, 255, 0.1);
            backdrop-filter: blur(10px);
            border-radius: 20px;
            padding: 3rem;
            margin: 3rem 0;
            text-align: center;
        }

        .stats-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 2rem;
        }

        .stat-item {
            color: white;
        }

        .stat-number {
            font-size: 2.5rem;
            font-weight: bold;
            display: block;
            margin-bottom: 0.5rem;
        }

        .stat-label {
            font-size: 1rem;
            opacity: 0.9;
        }

        /* Footer */
        .footer {
            background: rgba(255, 255, 255, 0.95);
            backdrop-filter: blur(10px);
            padding: 3rem 0 1rem;
            margin-top: auto;
        }

        .footer-container {
            max-width: 1400px;
            margin: 0 auto;
            padding: 0 2rem;
        }

        .footer-content {
            display: grid;
            grid-template-columns: 2fr 1fr 1fr 1fr;
            gap: 2rem;
            margin-bottom: 2rem;
        }

        .footer-section h3 {
            color: #2c3e50;
            margin-bottom: 1rem;
            font-size: 1.2rem;
        }

        .footer-section p, .footer-section li {
            color: #7f8c8d;
            line-height: 1.6;
            margin-bottom: 0.5rem;
        }

        .footer-section ul {
            list-style: none;
        }

        .footer-section a {
            color: #7f8c8d;
            text-decoration: none;
            transition: color 0.3s ease;
        }

        .footer-section a:hover {
            color: #667eea;
        }

        .footer-bottom {
            border-top: 1px solid #e0e0e0;
            padding-top: 1rem;
            text-align: center;
            color: #7f8c8d;
        }

        /* Responsive Design */
        @media (max-width: 768px) {
            .container {
                padding: 0 1rem;
            }

            .nav-container {
                padding: 0 1rem;
                flex-direction: column;
                gap: 1rem;
            }

            .nav-menu {
                flex-wrap: wrap;
                justify-content: center;
                gap: 1rem;
            }

            .hero-title {
                font-size: 2rem;
            }

            .tools-grid {
                grid-template-columns: 1fr;
                gap: 1.5rem;
            }

            .footer-content {
                grid-template-columns: 1fr;
                gap: 1.5rem;
            }

            .category-filters {
                gap: 0.5rem;
            }

            .filter-btn {
                padding: 0.6rem 1rem;
                font-size: 0.9rem;
            }
        }

        /* Animation for loading */
        .tool-card {
            animation: slideUp 0.6s ease-out;
        }

        @keyframes slideUp {
            from {
                opacity: 0;
                transform: translateY(30px);
            }
            to {
                opacity: 1;
                transform: translateY(0);
            }
        }

        .tool-card:nth-child(1) { animation-delay: 0.1s; }
        .tool-card:nth-child(2) { animation-delay: 0.2s; }
        .tool-card:nth-child(3) { animation-delay: 0.3s; }
        .tool-card:nth-child(4) { animation-delay: 0.4s; }
        .tool-card:nth-child(5) { animation-delay: 0.5s; }
        .tool-card:nth-child(6) { animation-delay: 0.6s; }
    </style>
</head>
<body>
    <!-- Navigation -->
    <nav class="navbar">
        <div class="nav-container">
            <a href="/" class="logo">
                <span class="logo-icon">🔓</span>
                PDF Tools Pro
            </a>
            <ul class="nav-menu">
                <li><a href="/" class="nav-link">Home</a></li>
                <li><a href="/tools" class="nav-link active">Tools</a></li>
                <li><a href="#" class="nav-link">About</a></li>
                <li><a href="#" class="nav-link">Privacy</a></li>
                <li><a href="#" class="nav-link">Contact</a></li>
            </ul>
        </div>
    </nav>

    <!-- Main Content -->
    <div class="main-wrapper">
        <div class="container">
            <!-- Hero Section -->
            <div class="hero-section">
                <h1 class="hero-title">🛠️ PDF Tools Collection</h1>
                <p class="hero-subtitle">Professional PDF processing tools for all your document needs. Fast, secure, and easy to use.</p>
            </div>

            <!-- Category Filters -->
            <div class="categories">
                <div class="category-filters">
                    <button class="filter-btn active" onclick="filterTools('all')">All Tools</button>
                    <button class="filter-btn" onclick="filterTools('security')">Security</button>
                    <button class="filter-btn" onclick="filterTools('conversion')">Convert</button>
                    <button class="filter-btn" onclick="filterTools('editing')">Edit</button>
                    <button class="filter-btn" onclick="filterTools('optimization')">Optimize</button>
                </div>
            </div>

            <!-- Tools Grid -->
            <div class="tools-grid">
                <!-- Password Removal Tool -->
                <div class="tool-card featured" data-category="security">
                    <div class="tool-badge">Popular</div>
                    <span class="tool-icon">🔓</span>
                    <h3 class="tool-title">Remove PDF Password</h3>
                    <p class="tool-description">Unlock password-protected PDFs instantly and securely</p>
                    <ul class="tool-features">
                        <li>Remove user and owner passwords</li>
                        <li>Maintain document quality</li>
                        <li>Secure processing</li>
                    </ul>
                    <a href="/" class="tool-button">Use Tool</a>
                </div>

                <!-- Compress PDF -->
                <div class="tool-card" data-category="optimization">
                    <span class="tool-icon">🗜️</span>
                    <h3 class="tool-title">Compress PDF</h3>
                    <p class="tool-description">Reduce PDF file size while maintaining quality</p>
                    <ul class="tool-features">
                        <li>Multiple compression levels</li>
                        <li>Preserve document quality</li>
                        <li>Batch processing</li>
                    </ul>
                    <button class="tool-button coming-soon">Coming Soon</button>
                </div>

                <!-- Merge PDFs -->
                <div class="tool-card" data-category="editing">
                    <span class="tool-icon">📑</span>
                    <h3 class="tool-title">Merge PDFs</h3>
                    <p class="tool-description">Combine multiple PDF files into one document</p>
                    <ul class="tool-features">
                        <li>Drag and drop ordering</li>
                        <li>Custom page ranges</li>
                        <li>Bookmark preservation</li>
                    </ul>
                    <button class="tool-button coming-soon">Coming Soon</button>
                </div>

                <!-- Split PDF -->
                <div class="tool-card" data-category="editing">
                    <span class="tool-icon">✂️</span>
                    <h3 class="tool-title">Split PDF</h3>
                    <p class="tool-description">Extract pages or split PDF into multiple files</p>
                    <ul class="tool-features">
                        <li>Split by page ranges</li>
                        <li>Extract specific pages</li>
                        <li>Bulk splitting options</li>
                    </ul>
                    <button class="tool-button coming-soon">Coming Soon</button>
                </div>

                <!-- PDF to Word -->
                <div class="tool-card" data-category="conversion">
                    <span class="tool-icon">📄</span>
                    <h3 class="tool-title">PDF to Word</h3>
                    <p class="tool-description">Convert PDF documents to editable Word files</p>
                    <ul class="tool-features">
                        <li>Maintain formatting</li>
                        <li>OCR text recognition</li>
                        <li>Table preservation</li>
                    </ul>
                    <button class="tool-button coming-soon">Coming Soon</button>
                </div>

                <!-- Word to PDF -->
                <div class="tool-card" data-category="conversion">
                    <span class="tool-icon">📋</span>
                    <h3 class="tool-title">Word to PDF</h3>
                    <p class="tool-description">Convert Word documents to PDF format</p>
                    <ul class="tool-features">
                        <li>Perfect formatting</li>
                        <li>Font embedding</li>
                        <li>Multiple file support</li>
                    </ul>
                    <button class="tool-button coming-soon">Coming Soon</button>
                </div>

                <!-- PDF to Images -->
                <div class="tool-card" data-category="conversion">
                    <span class="tool-icon">🖼️</span>
                    <h3 class="tool-title">PDF to Images</h3>
                    <p class="tool-description">Convert PDF pages to high-quality images</p>
                    <ul class="tool-features">
                        <li>Multiple formats (PNG, JPG)</li>
                        <li>Custom DPI settings</li>
                        <li>Batch conversion</li>
                    </ul>
                    <button class="tool-button coming-soon">Coming Soon</button>
                </div>

                <!-- Images to PDF -->
                <div class="tool-card" data-category="conversion">
                    <span class="tool-icon">🖼️➡️📄</span>
                    <h3 class="tool-title">Images to PDF</h3>
                    <p class="tool-description">Create PDF from multiple images</p>
                    <ul class="tool-features">
                        <li>Multiple image formats</li>
                        <li>Custom page sizes</li>
                        <li>Image optimization</li>
                    </ul>
                    <button class="tool-button coming-soon">Coming Soon</button>
                </div>

                <!-- Rotate PDF -->
                <div class="tool-card" data-category="editing">
                    <span class="tool-icon">🔄</span>
                    <h3 class="tool-title">Rotate PDF</h3>
                    <p class="tool-description">Rotate PDF pages to correct orientation</p>
                    <ul class="tool-features">
                        <li>Rotate individual pages</li>
                        <li>Bulk rotation options</li>
                        <li>Preview before saving</li>
                    </ul>
                    <button class="tool-button coming-soon">Coming Soon</button>
                </div>

                <!-- Add Watermark -->
                <div class="tool-card" data-category="editing">
                    <span class="tool-icon">🏷️</span>
                    <h3 class="tool-title">Add Watermark</h3>
                    <p class="tool-description">Add text or image watermarks to PDF</p>
                    <ul class="tool-features">
                        <li>Text and image watermarks</li>
                        <li>Custom positioning</li>
                        <li>Transparency control</li>
                    </ul>
                    <button class="tool-button coming-soon">Coming Soon</button>
                </div>

                <!-- Encrypt PDF -->
                <div class="tool-card" data-category="security">
                    <span class="tool-icon">🔒</span>
                    <h3 class="tool-title">Encrypt PDF</h3>
                    <p class="tool-description">Add password protection to your PDFs</p>
                    <ul class="tool-features">
                        <li>Strong encryption</li>
                        <li>Permission settings</li>
                        <li>Custom passwords</li>
                    </ul>
                    <button class="tool-button coming-soon">Coming Soon</button>
                </div>

                <!-- PDF Reader -->
                <div class="tool-card" data-category="editing">
                    <span class="tool-icon">👁️</span>
                    <h3 class="tool-title">PDF Viewer</h3>
                    <p class="tool-description">View and read PDF files online</p>
                    <ul class="tool-features">
                        <li>Fast rendering</li>
                        <li>Zoom and navigation</li>
                        <li>Search within document</li>
                    </ul>
                    <button class="tool-button coming-soon">Coming Soon</button>
                </div>
            </div>

            <!-- Stats Section -->
            <div class="stats-section">
                <div class="stats-grid">
                    <div class="stat-item">
                        <span class="stat-number">50,000+</span>
                        <span class="stat-label">Files Processed</span>
                    </div>
                    <div class="stat-item">
                        <span class="stat-number">12</span>
                        <span class="stat-label">PDF Tools</span>
                    </div>
                    <div class="stat-item">
                        <span class="stat-number">99.9%</span>
                        <span class="stat-label">Uptime</span>
                    </div>
                    <div class="stat-item">
                        <span class="stat-number">24/7</span>
                        <span class="stat-label">Available</span>
                    </div>
                </div>
            </div>
        </div>
    </div>

    <!-- Footer -->
    <footer class="footer">
        <div class="footer-container">
            <div class="footer-content">
                <div class="footer-section">
                    <h3>PDF Tools Pro</h3>
                    <p>Professional PDF processing tools for individuals and businesses. Secure, fast, and reliable PDF solutions at your fingertips.</p>
                    <p style="margin-top: 1rem;">© 2024 PDF Tools Pro. All rights reserved.</p>
                </div>
                <div class="footer-section">
                    <h3>Tools</h3>
                    <ul>
                        <li><a href="/">Remove Password</a></li>
                        <li><a href="#">Compress PDF</a></li>
                        <li><a href="#">Merge PDFs</a></li>
                        <li><a href="#">Split PDF</a></li>
                        <li><a href="#">Convert to PDF</a></li>
                    </ul>
                </div>
                <div class="footer-section">
                    <h3>Support</h3>
                    <ul>
                        <li><a href="#">Help Center</a></li>
                        <li><a href="#">FAQ</a></li>
                        <li><a href="#">Contact Us</a></li>
                        <li><a href="#">Bug Report</a></li>
                        <li><a href="#">Feature Request</a></li>
                    </ul>
                </div>
                <div class="footer-section">
                    <h3>Legal</h3>
                    <ul>
                        <li><a href="#">Privacy Policy</a></li>
                        <li><a href="#">Terms of Service</a></li>
                        <li><a href="#">Cookie Policy</a></li>
                        <li><a href="#">GDPR</a></li>
                    </ul>
                </div>
            </div>
            <div class="footer-bottom">
                <p>Built with ❤️ for secure and efficient PDF processing</p>
            </div>
        </div>
    </footer>

    <script>
        function filterTools(category) {
            const cards = document.querySelectorAll('.tool-card');
            const buttons = document.querySelectorAll('.filter-btn');

            // Update active button
            buttons.forEach(btn => btn.classList.remove('active'));
            event.target.classList.add('active');

            // Filter cards
            cards.forEach(card => {
                if (category === 'all' || card.dataset.category === category) {
                    card.style.display = 'block';
                    card.style.animation = 'slideUp 0.6s ease-out';
                } else {
                    card.style.display = 'none';
                }
            });
        }

        // Smooth scroll for navigation
        document.querySelectorAll('.nav-link').forEach(link => {
            link.addEventListener('click', (e) => {
                if (link.getAttribute('href').startsWith('#')) {
                    e.preventDefault();
                }
            });
        });

        // Add hover effects to tool cards
        document.querySelectorAll('.tool-card').forEach(card => {
            card.addEventListener('mouseenter', () => {
                card.style.transform = 'translateY(-8px)';
            });

            card.addEventListener('mouseleave', () => {
                if (!card.classList.contains('featured')) {
                    card.style.transform = 'translateY(0)';
                } else {
                    card.style.transform = 'scale(1.02)';
                }
            });
        });

        // Counter animation for stats
        function animateCounters() {
            const counters = document.querySelectorAll('.stat-number');
            const duration = 2000;

            counters.forEach(counter => {
                const target = counter.textContent;
                let number = parseFloat(target.replace(/[^0-9.]/g, ''));

                if (isNaN(number)) return;

                let current = 0;
                const increment = number / (duration / 16);

                const timer = setInterval(() => {
                    current += increment;

                    if (current >= number) {
                        current = number;
                        clearInterval(timer);
                    }

                    if (target.includes('+')) {
                        counter.textContent = Math.floor(current).toLocaleString() + '+';
                    } else if (target.includes('%')) {
                        counter.textContent = current.toFixed(1) + '%';
                    } else if (target.includes('/')) {
                        counter.textContent = target;
                    } else {
                        counter.textContent = Math.floor(current).toLocaleString();
                    }
                }, 16);
            });
        }

        // Trigger counter animation when stats section is visible
        const observer = new IntersectionObserver((entries) => {
            entries.forEach(entry => {
                if (entry.isIntersecting) {
                    animateCounters();
                    observer.unobserve(entry.target);
                }
            });
        });

        observer.observe(document.querySelector('.stats-section'));
    </script>
</body>
</html>
'''

# Main page HTML template (updated navigation)
HTML_TEMPLATE = '''
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>PDF Password Remover - Secure PDF Tool</title>
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }

        body {
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            display: flex;
            flex-direction: column;
        }

        /* Navigation */
        .navbar {
            background: rgba(255, 255, 255, 0.95);
            backdrop-filter: blur(10px);
            padding: 1rem 0;
            box-shadow: 0 2px 20px rgba(0,0,0,0.1);
            position: sticky;
            top: 0;
            z-index: 1000;
        }

        .nav-container {
            max-width: 1400px;
            margin: 0 auto;
            padding: 0 2rem;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }

        .logo {
            display: flex;
            align-items: center;
            font-size: 1.5rem;
            font-weight: bold;
            color: #2c3e50;
            text-decoration: none;
        }

        .logo-icon {
            font-size: 2rem;
            margin-right: 0.5rem;
        }

        .nav-menu {
            display: flex;
            list-style: none;
            gap: 2rem;
        }

        .nav-link {
            color: #2c3e50;
            text-decoration: none;
            font-weight: 500;
            transition: all 0.3s ease;
            padding: 0.5rem 1rem;
            border-radius: 8px;
        }

        .nav-link:hover, .nav-link.active {
            background: #667eea;
            color: white;
            transform: translateY(-2px);
        }

        /* Rest of the existing styles remain the same... */
        /* Main Content */
        .main-wrapper {
            flex: 1;
            padding: 2rem 0;
        }

        .container {
            max-width: 1400px;
            margin: 0 auto;
            padding: 0 2rem;
        }

        .content-grid {
            display: grid;
            grid-template-columns: 1fr 2fr 1fr;
            gap: 2rem;
            min-height: 70vh;
        }

        .sidebar-left, .sidebar-right {
            background: rgba(255, 255, 255, 0.1);
            backdrop-filter: blur(10px);
            border-radius: 15px;
            padding: 2rem;
            height: fit-content;
        }

        .sidebar-left h3, .sidebar-right h3 {
            color: white;
            margin-bottom: 1rem;
            font-size: 1.2rem;
        }

        .sidebar-left p, .sidebar-right p {
            color: rgba(255, 255, 255, 0.9);
            line-height: 1.6;
            margin-bottom: 1rem;
        }

        .feature-list {
            list-style: none;
            padding: 0;
        }

        .feature-list li {
            color: rgba(255, 255, 255, 0.9);
            padding: 0.5rem 0;
            display: flex;
            align-items: center;
        }

        .feature-list li::before {
            content: "✓";
            color: #27ae60;
            font-weight: bold;
            margin-right: 0.5rem;
            background: white;
            border-radius: 50%;
            width: 20px;
            height: 20px;
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 0.8rem;
        }

        .main-content {
            background: white;
            border-radius: 20px;
            box-shadow: 0 20px 40px rgba(0,0,0,0.1);
            overflow: hidden;
        }

        .content-header {
            background: linear-gradient(45deg, #2c3e50, #34495e);
            color: white;
            padding: 2rem;
            text-align: center;
        }

        .content-header h1 {
            font-size: 2.5rem;
            margin-bottom: 0.5rem;
        }

        .content-header p {
            opacity: 0.9;
            font-size: 1.2rem;
        }

        .content-body {
            padding: 3rem;
        }

        .upload-section {
            border: 3px dashed #e0e0e0;
            border-radius: 15px;
            padding: 3rem;
            text-align: center;
            margin-bottom: 2rem;
            background: #fafafa;
            transition: all 0.3s ease;
            cursor: pointer;
        }

        .upload-section:hover {
            border-color: #667eea;
            background: #f0f4ff;
            transform: translateY(-5px);
            box-shadow: 0 10px 30px rgba(0,0,0,0.1);
        }

        .upload-section.dragover {
            border-color: #667eea;
            background: #f0f4ff;
            transform: scale(1.02);
        }

        .upload-icon {
            font-size: 4rem;
            color: #667eea;
            margin-bottom: 1rem;
        }

        .upload-title {
            font-size: 1.5rem;
            color: #2c3e50;
            margin-bottom: 1rem;
        }

        .upload-description {
            color: #7f8c8d;
            margin-bottom: 2rem;
            font-size: 1.1rem;
        }

        .file-input {
            display: none;
        }

        .upload-btn {
            background: linear-gradient(45deg, #667eea, #764ba2);
            color: white;
            padding: 15px 40px;
            border: none;
            border-radius: 30px;
            font-size: 1.2rem;
            cursor: pointer;
            transition: all 0.3s ease;
            text-transform: uppercase;
            letter-spacing: 1px;
            font-weight: 600;
        }

        .upload-btn:hover {
            transform: translateY(-3px);
            box-shadow: 0 10px 25px rgba(102, 126, 234, 0.4);
        }

        .file-info {
            background: linear-gradient(45deg, #e8f4fd, #f0f8ff);
            padding: 1.5rem;
            border-radius: 12px;
            margin-bottom: 2rem;
            display: none;
            border-left: 4px solid #667eea;
        }

        .file-name {
            font-weight: bold;
            color: #2c3e50;
            margin-bottom: 0.5rem;
            font-size: 1.1rem;
        }

        .file-size {
            color: #7f8c8d;
            font-size: 0.95rem;
        }

        .password-section {
            background: linear-gradient(45deg, #fff9e6, #fffbf0);
            padding: 2rem;
            border-radius: 15px;
            margin-bottom: 2rem;
            border-left: 4px solid #f39c12;
        }

        .form-group {
            margin-bottom: 1.5rem;
        }

        .form-group label {
            display: block;
            margin-bottom: 0.5rem;
            font-weight: 600;
            color: #2c3e50;
            font-size: 1.1rem;
        }

        .form-group input {
            width: 100%;
            padding: 15px;
            border: 2px solid #e0e0e0;
            border-radius: 10px;
            font-size: 1.1rem;
            transition: all 0.3s ease;
        }

        .form-group input:focus {
            outline: none;
            border-color: #667eea;
            box-shadow: 0 0 0 4px rgba(102, 126, 234, 0.1);
            transform: translateY(-2px);
        }

        .process-btn {
            background: linear-gradient(45deg, #27ae60, #2ecc71);
            color: white;
            padding: 18px 0;
            border: none;
            border-radius: 12px;
            font-size: 1.2rem;
            cursor: pointer;
            width: 100%;
            transition: all 0.3s ease;
            margin-bottom: 2rem;
            text-transform: uppercase;
            letter-spacing: 1px;
            font-weight: 600;
        }

        .process-btn:hover {
            transform: translateY(-3px);
            box-shadow: 0 8px 25px rgba(39, 174, 96, 0.3);
        }

        .process-btn:disabled {
            background: #bdc3c7;
            cursor: not-allowed;
            transform: none;
            box-shadow: none;
        }

        .progress-bar {
            width: 100%;
            height: 8px;
            background: #e0e0e0;
            border-radius: 4px;
            margin-bottom: 2rem;
            display: none;
            overflow: hidden;
            position: relative;
        }

        .progress-fill {
            height: 100%;
            background: linear-gradient(45deg, #667eea, #764ba2);
            border-radius: 4px;
            width: 0%;
            transition: width 0.3s ease;
            position: relative;
        }

        .progress-fill::after {
            content: '';
            position: absolute;
            top: 0;
            left: 0;
            right: 0;
            bottom: 0;
            background: linear-gradient(90deg, transparent, rgba(255,255,255,0.3), transparent);
            animation: shimmer 1.5s infinite;
        }

        @keyframes shimmer {
            0% { transform: translateX(-100%); }
            100% { transform: translateX(100%); }
        }

        .download-section {
            background: linear-gradient(45deg, #e8f5e8, #f0fff0);
            padding: 2rem;
            border-radius: 15px;
            text-align: center;
            display: none;
            border-left: 4px solid #27ae60;
        }

        .download-btn {
            background: linear-gradient(45deg, #e74c3c, #c0392b);
            color: white;
            padding: 18px 40px;
            border: none;
            border-radius: 12px;
            font-size: 1.2rem;
            cursor: pointer;
            text-decoration: none;
            display: inline-block;
            transition: all 0.3s ease;
            text-transform: uppercase;
            letter-spacing: 1px;
            font-weight: 600;
        }

        .download-btn:hover {
            transform: translateY(-3px);
            box-shadow: 0 8px 25px rgba(231, 76, 60, 0.3);
        }

        .success-message {
            color: #27ae60;
            font-weight: bold;
            margin-bottom: 1rem;
            font-size: 1.3rem;
        }

        .error-message {
            background: #ffe6e6;
            color: #e74c3c;
            padding: 1rem;
            border-radius: 10px;
            margin-bottom: 1.5rem;
            display: none;
            border-left: 4px solid #e74c3c;
            font-weight: 500;
        }

        /* Footer */
        .footer {
            background: rgba(255, 255, 255, 0.95);
            backdrop-filter: blur(10px);
            padding: 3rem 0 1rem;
            margin-top: auto;
        }

        .footer-container {
            max-width: 1400px;
            margin: 0 auto;
            padding: 0 2rem;
        }

        .footer-content {
            display: grid;
            grid-template-columns: 2fr 1fr 1fr 1fr;
            gap: 2rem;
            margin-bottom: 2rem;
        }

        .footer-section h3 {
            color: #2c3e50;
            margin-bottom: 1rem;
            font-size: 1.2rem;
        }

        .footer-section p, .footer-section li {
            color: #7f8c8d;
            line-height: 1.6;
            margin-bottom: 0.5rem;
        }

        .footer-section ul {
            list-style: none;
        }

        .footer-section a {
            color: #7f8c8d;
            text-decoration: none;
            transition: color 0.3s ease;
        }

        .footer-section a:hover {
            color: #667eea;
        }

        .footer-bottom {
            border-top: 1px solid #e0e0e0;
            padding-top: 1rem;
            text-align: center;
            color: #7f8c8d;
        }

        .disclaimer {
            background: rgba(255, 255, 255, 0.1);
            backdrop-filter: blur(10px);
            padding: 1.5rem;
            border-radius: 12px;
            margin-top: 2rem;
            color: rgba(255, 255, 255, 0.9);
            border-left: 4px solid #f39c12;
        }

        .disclaimer h3 {
            color: white;
            margin-bottom: 0.5rem;
        }

        /* Responsive Design */
        @media (max-width: 1200px) {
            .content-grid {
                grid-template-columns: 1fr;
                gap: 1rem;
            }

            .sidebar-left, .sidebar-right {
                display: none;
            }
        }

        @media (max-width: 768px) {
            .container {
                padding: 0 1rem;
            }

            .nav-container {
                padding: 0 1rem;
                flex-direction: column;
                gap: 1rem;
            }

            .nav-menu {
                flex-wrap: wrap;
                justify-content: center;
                gap: 1rem;
            }

            .content-body {
                padding: 1.5rem;
            }

            .content-header {
                padding: 1.5rem;
            }

            .content-header h1 {
                font-size: 2rem;
            }

            .footer-content {
                grid-template-columns: 1fr;
                gap: 1.5rem;
            }
        }

        @media (max-width: 480px) {
            .upload-section {
                padding: 1.5rem;
            }

            .upload-icon {
                font-size: 3rem;
            }

            .upload-btn, .process-btn, .download-btn {
                padding: 15px 20px;
                font-size: 1rem;
            }
        }
    </style>
</head>
<body>
    <!-- Navigation -->
    <nav class="navbar">
        <div class="nav-container">
            <a href="/" class="logo">
                <span class="logo-icon">🔓</span>
                PDF Tools Pro
            </a>
            <ul class="nav-menu">
                <li><a href="/" class="nav-link active">Home</a></li>
                <li><a href="/tools" class="nav-link">Tools</a></li>
                <li><a href="#" class="nav-link">About</a></li>
                <li><a href="#" class="nav-link">Privacy</a></li>
                <li><a href="#" class="nav-link">Contact</a></li>
            </ul>
        </div>
    </nav>

    <!-- Main Content -->
    <div class="main-wrapper">
        <div class="container">
            <div class="content-grid">
                <!-- Left Sidebar -->
                <div class="sidebar-left">
                    <h3>🚀 Features</h3>
                    <ul class="feature-list">
                        <li>Remove PDF passwords instantly</li>
                        <li>Secure & private processing</li>
                        <li>No file size limits</li>
                        <li>Fast processing speed</li>
                        <li>Download immediately</li>
                        <li>No registration required</li>
                    </ul>

                    <h3 style="margin-top: 2rem;">🔒 Security</h3>
                    <p>Your files are processed securely and automatically deleted after download. We never store your documents or passwords.</p>
                </div>

                <!-- Main Content -->
                <div class="main-content">
                    <div class="content-header">
                        <h1>🔓 PDF Password Remover</h1>
                        <p>Remove passwords from your PDF documents safely and securely</p>
                    </div>

                    <div class="content-body">
                        <div class="upload-section" id="uploadSection">
                            <div class="upload-icon">📄</div>
                            <h3 class="upload-title">Select or Drop Your PDF File</h3>
                            <p class="upload-description">Choose a password-protected PDF file to process</p>
                            <button class="upload-btn" onclick="document.getElementById('fileInput').click()">
                                Choose PDF File
                            </button>
                            <input type="file" id="fileInput" class="file-input" accept=".pdf" onchange="handleFileSelect(this)">
                        </div>

                        <div class="file-info" id="fileInfo">
                            <div class="file-name" id="fileName"></div>
                            <div class="file-size" id="fileSize"></div>
                        </div>

                        <div class="error-message" id="errorMessage"></div>

                        <div class="password-section">
                            <div class="form-group">
                                <label for="currentPassword">🔐 Current PDF Password:</label>
                                <input type="password" id="currentPassword" placeholder="Enter the current password for your PDF">
                            </div>

                            <button class="process-btn" id="processBtn" onclick="processFile()" disabled>
                                🚀 Remove Password & Process File
                            </button>
                        </div>

                        <div class="progress-bar" id="progressBar">
                            <div class="progress-fill" id="progressFill"></div>
                        </div>

                        <div class="download-section" id="downloadSection">
                            <div class="success-message">✅ Password removed successfully!</div>
                            <p style="margin-bottom: 20px;">Your PDF is now unlocked and ready for download.</p>
                            <a href="#" class="download-btn" id="downloadBtn" download="unlocked_document.pdf">
                                📥 Download Unlocked PDF
                            </a>
                        </div>
                    </div>
                </div>

                <!-- Right Sidebar -->
                <div class="sidebar-right">
                    <h3>📖 How it Works</h3>
                    <p>1. Upload your password-protected PDF</p>
                    <p>2. Enter the current password</p>
                    <p>3. Click process to remove password</p>
                    <p>4. Download your unlocked PDF</p>

                    <h3 style="margin-top: 2rem;">💡 Tips</h3>
                    <p>• Make sure you have the correct password</p>
                    <p>• Files are automatically deleted after 1 hour</p>
                    <p>• Maximum file size is 50MB</p>
                    <p>• Only PDF files are supported</p>

                    <h3 style="margin-top: 2rem;">🛠️ More Tools</h3>
                    <p><a href="/tools" style="color: white; text-decoration: underline;">Explore all PDF tools →</a></p>
                </div>
            </div>

            <div class="disclaimer">
                <h3>⚠️ Important Notice</h3>
                <p>This tool is intended for legitimate use only. Please ensure you have the legal right to remove passwords from the PDF documents you process. Only use this service for documents you own or have explicit permission to modify. We do not store any files or passwords on our servers.</p>
            </div>
        </div>
    </div>

    <!-- Footer -->
    <footer class="footer">
        <div class="footer-container">
            <div class="footer-content">
                <div class="footer-section">
                    <h3>PDF Tools Pro</h3>
                    <p>Professional PDF processing tools for individuals and businesses. Secure, fast, and reliable PDF solutions at your fingertips.</p>
                    <p style="margin-top: 1rem;">© 2024 PDF Tools Pro. All rights reserved.</p>
                </div>
                <div class="footer-section">
                    <h3>Tools</h3>
                    <ul>
                        <li><a href="/">Remove Password</a></li>
                        <li><a href="/tools">All Tools</a></li>
                        <li><a href="#">Compress PDF</a></li>
                        <li><a href="#">Merge PDFs</a></li>
                        <li><a href="#">Split PDF</a></li>
                    </ul>
                </div>
                <div class="footer-section">
                    <h3>Support</h3>
                    <ul>
                        <li><a href="#">Help Center</a></li>
                        <li><a href="#">FAQ</a></li>
                        <li><a href="#">Contact Us</a></li>
                        <li><a href="#">Bug Report</a></li>
                        <li><a href="#">Feature Request</a></li>
                    </ul>
                </div>
                <div class="footer-section">
                    <h3>Legal</h3>
                    <ul>
                        <li><a href="#">Privacy Policy</a></li>
                        <li><a href="#">Terms of Service</a></li>
                        <li><a href="#">Cookie Policy</a></li>
                        <li><a href="#">GDPR</a></li>
                    </ul>
                </div>
            </div>
            <div class="footer-bottom">
                <p>Built with ❤️ for secure and efficient PDF processing</p>
            </div>
        </div>
    </footer>

    <script>
        let selectedFile = null;

        // Drag and drop functionality
        const uploadSection = document.getElementById('uploadSection');

        uploadSection.addEventListener('dragover', (e) => {
            e.preventDefault();
            uploadSection.classList.add('dragover');
        });

        uploadSection.addEventListener('dragleave', () => {
            uploadSection.classList.remove('dragover');
        });

        uploadSection.addEventListener('drop', (e) => {
            e.preventDefault();
            uploadSection.classList.remove('dragover');
            const files = e.dataTransfer.files;
            if (files.length > 0) {
                handleFile(files[0]);
            }
        });

        function handleFileSelect(input) {
            if (input.files.length > 0) {
                handleFile(input.files[0]);
            }
        }

        function handleFile(file) {
            if (file.type !== 'application/pdf') {
                showError('Please select a PDF file.');
                return;
            }

            if (file.size > 50 * 1024 * 1024) { // 50MB limit
                showError('File size too large. Please select a file under 50MB.');
                return;
            }

            selectedFile = file;
            displayFileInfo(file);
            document.getElementById('processBtn').disabled = false;
            hideError();
        }

        function displayFileInfo(file) {
            document.getElementById('fileName').textContent = file.name;
            document.getElementById('fileSize').textContent = formatFileSize(file.size);
            document.getElementById('fileInfo').style.display = 'block';
        }

        function formatFileSize(bytes) {
            if (bytes === 0) return '0 Bytes';
            const k = 1024;
            const sizes = ['Bytes', 'KB', 'MB', 'GB'];
            const i = Math.floor(Math.log(bytes) / Math.log(k));
            return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
        }

        function showError(message) {
            const errorDiv = document.getElementById('errorMessage');
            errorDiv.textContent = message;
            errorDiv.style.display = 'block';
        }

        function hideError() {
            document.getElementById('errorMessage').style.display = 'none';
        }

        async function processFile() {
            const password = document.getElementById('currentPassword').value.trim();

            if (!selectedFile) {
                showError('Please select a PDF file first.');
                return;
            }

            if (!password) {
                showError('Please enter the current password.');
                return;
            }

            // Show progress bar
            document.getElementById('progressBar').style.display = 'block';
            document.getElementById('processBtn').disabled = true;

            // Start progress animation
            let progress = 0;
            const progressInterval = setInterval(() => {
                progress += 2;
                if (progress <= 90) {
                    document.getElementById('progressFill').style.width = progress + '%';
                }
            }, 100);

            try {
                const formData = new FormData();
                formData.append('pdf_file', selectedFile);
                formData.append('password', password);

                const response = await fetch('/api/remove-password', {
                    method: 'POST',
                    body: formData
                });

                clearInterval(progressInterval);
                document.getElementById('progressFill').style.width = '100%';

                if (response.ok) {
                    const result = await response.json();
                    if (result.success) {
                        document.getElementById('downloadBtn').href = '/api/download/' + result.file_id;
                        document.getElementById('downloadBtn').download = 'unlocked_' + selectedFile.name;
                        showDownloadSection();
                    } else {
                        throw new Error(result.error || 'Failed to process PDF');
                    }
                } else {
                    const errorData = await response.json();
                    throw new Error(errorData.error || 'Failed to process PDF');
                }

            } catch (error) {
                clearInterval(progressInterval);
                document.getElementById('progressBar').style.display = 'none';
                document.getElementById('processBtn').disabled = false;
                showError('Error: ' + error.message);
            }
        }

        function showDownloadSection() {
            document.getElementById('downloadSection').style.display = 'block';
            document.getElementById('progressBar').style.display = 'none';

            // Smooth scroll to download section
            document.getElementById('downloadSection').scrollIntoView({
                behavior: 'smooth',
                block: 'center'
            });
        }

        // Smooth scrolling for navigation links
        document.querySelectorAll('.nav-link').forEach(link => {
            link.addEventListener('click', (e) => {
                if (link.getAttribute('href').startsWith('#')) {
                    e.preventDefault();
                }
            });
        });
    </script>
</body>
</html>
'''

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

if __name__ == '__main__':
    # Create uploads directory if it doesn't exist
    os.makedirs('uploads', exist_ok=True)

    logger.info(f"Using PDF library: {PDF_LIB}")
    logger.info("Starting PDF Password Remover application...")

    # Run the app
    app.run(debug=True, host='0.0.0.0', port=5001)
