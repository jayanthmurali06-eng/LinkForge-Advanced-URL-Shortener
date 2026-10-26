# LinkForge — Advanced URL Shortener

LinkForge is a web application built using Python, Flask, and SQLite. It converts long URLs into short links and provides click tracking and link analytics.

## Features

- Generate short URLs from long links
- Redirect visitors to original destinations
- Track link clicks
- View link statistics through an analytics dashboard
- Search links in the dashboard
- Validate submitted URLs
- Handle invalid URLs and unknown short codes safely
- Store link information in SQLite

## Technology Stack

- Python
- Flask
- SQLite
- HTML, CSS, and JavaScript
- Git and GitHub

## Project Structure

    LinkForge/
    ├── app/
    │   ├── __init__.py
    │   ├── routes.py
    │   ├── static/
    │   │   └── style.css
    │   └── templates/
    │       ├── index.html
    │       └── analytics.html
    ├── requirements.txt
    ├── run.py
    ├── .gitignore
    ├── LICENSE
    └── README.md

## Requirements

- Python 3
- pip

## Installation

### 1. Clone the repository

    git clone https://github.com/jayanthmurali06-eng/LinkForge-Advanced-URL-Shortener.git
    cd LinkForge-Advanced-URL-Shortener

### 2. Create a virtual environment

    python3 -m venv venv

### 3. Activate the environment on macOS or Linux

    source venv/bin/activate

### 4. Install dependencies

    pip install -r requirements.txt

### 5. Start the application

    python run.py

Open http://127.0.0.1:5000 in your browser.

Press Control+C in Terminal to stop the server.

## Testing

Manually tested functionality includes URL shortening, redirects, URL validation, handling malformed short links, click tracking, and analytics search.

## Future Enhancements

- Custom short URL aliases
- QR code generation
- Link expiration dates
- Additional analytics
- Production deployment

## License

This project is licensed under the MIT License. See the LICENSE file for details.
