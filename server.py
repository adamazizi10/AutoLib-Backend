from datetime import datetime, timedelta

import pytz
from flask import Flask, jsonify, request
import psycopg2
from flask_cors import CORS
from dotenv import load_dotenv
import os

app = Flask(__name__)
CORS(app)

load_dotenv()


# Establish database connection using the environment variable
DATABASE_URL = os.getenv("DATABASE_URL")


if DATABASE_URL is not None:
    conn = psycopg2.connect(DATABASE_URL, sslmode='require')
else:
    print("DATABASE_URL environment variable is not set. Unable to establish database connection.")



# Establish database connection
# conn = psycopg2.connect(
#     host="127.0.0.1",
#     port="5432",
#     user="adamazizi",
#     password="",  # Add password if required
#     database="librarycoe892"
# )

# Define routes and handlers

@app.route('/')
def home():
    return "Welcome to the AutoLib"


@app.route('/register', methods=['POST'])
def register():
    data = request.get_json()
    username = data.get('username')
    password = data.get('password')
    confirm_password = data.get('confirm_password')

    if not username or not password or not confirm_password:
        return jsonify({'error': 'All fields are required'}), 400

    if password != confirm_password:
        return jsonify({'error': 'Passwords do not match'}), 400

    cursor = conn.cursor()
    try:
        cursor.execute("INSERT INTO library_users (username, password) VALUES (%s, %s) RETURNING id, username", (username, password))
        user = cursor.fetchone()
        conn.commit()
        user_id, username = user
        return jsonify({'user_id': user_id, 'username': username, 'message': 'User registered successfully'}), 201
    except psycopg2.IntegrityError:
        conn.rollback()
        return jsonify({'error': 'Username already exists'}), 400
    finally:
        cursor.close()


@app.route('/login', methods=['POST'])
def login():
    data = request.get_json()
    username = data.get('username')
    password = data.get('password')

    if not username or not password:
        return jsonify({'error': 'Username and password are required'}), 400

    cursor = conn.cursor()
    try:
        cursor.execute("SELECT id, username FROM library_users WHERE username = %s AND password = %s", (username, password))
        user = cursor.fetchone()
        if user:
            user_id, username = user
            return jsonify({'user_id': user_id, 'username': username}), 200
        else:
            return jsonify({'error': 'Invalid username or password'}), 401
    finally:
        cursor.close()

@app.route('/user/books/<int:user_id>', methods=['GET'])
def get_user_books(user_id):
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT id, title, author, borrowed_by, borrowed_by_username, expires FROM books WHERE borrowed_by = %s", (user_id,))
        books = cursor.fetchall()
        books_data = [{'id': book[0], 'title': book[1], 'author': book[2], 'borrowed_by': book[3], 'borrowed_by_username': book[4], 'expires': book[5]} for book in books]
        return jsonify(books_data), 200
    finally:
        cursor.close()

@app.route('/books', methods=['GET'])
def get_books():
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT id, title, author, borrowed_by, borrowed_by_username, expires FROM books")
        books = cursor.fetchall()
        books_data = [{'id': book[0], 'title': book[1], 'author': book[2], 'borrowed_by': book[3], 'borrowed_by_username': book[4], 'expires': book[5]} for book in books]
        return jsonify(books_data), 200
    finally:
        cursor.close()

@app.route('/borrow/<int:book_id>', methods=['PUT'])
def borrow_book(book_id):
    data = request.get_json()
    user_id = data.get('userId')

    cursor = conn.cursor()
    try:
        # Get the username of the user borrowing the book
        cursor.execute("SELECT username FROM library_users WHERE id = %s", (user_id,))
        borrower_username = cursor.fetchone()[0]  # Assuming username is the first column

        # Calculate expiration date (1 month from now) in Eastern Standard Time (EST)
        eastern = pytz.timezone('America/Toronto')
        expires = datetime.now() + timedelta(days=30)
        expires = expires.astimezone(eastern)

        cursor.execute("UPDATE books SET borrowed_by = %s, borrowed_by_username = %s, expires = %s WHERE id = %s AND borrowed_by IS NULL", (user_id, borrower_username, expires, book_id))
        if cursor.rowcount == 1:
            conn.commit()
            return jsonify({'message': 'Book borrowed successfully', 'expires': expires, 'borrowed_by': user_id, 'borrowed_by_username': borrower_username}), 200
        else:
            return jsonify({'error': 'Book is already borrowed or does not exist'}), 404
    finally:
        cursor.close()

@app.route('/renew/<int:book_id>', methods=['PUT'])
def renew_book(book_id):
    data = request.get_json()
    user_id = data.get('userId')

    cursor = conn.cursor()
    try:
        # Calculate new expiration date (30 days from now)
        eastern = pytz.timezone('America/Toronto')
        new_expires = datetime.now() + timedelta(days=30)
        new_expires = new_expires.astimezone(eastern)

        cursor.execute("UPDATE books SET expires = %s WHERE id = %s AND borrowed_by = %s", (new_expires, book_id, user_id))
        if cursor.rowcount == 1:
            conn.commit()
            return jsonify({'message': 'Book renewed successfully', 'new_expires': new_expires}), 200
        else:
            return jsonify({'error': 'Book renewal failed. It may not be borrowed by the user or does not exist'}), 404
    finally:
        cursor.close()


@app.route('/return/<int:book_id>', methods=['PUT'])
def return_book(book_id):
    cursor = conn.cursor()
    try:
        cursor.execute("UPDATE books SET borrowed_by = DEFAULT, borrowed_by_username = DEFAULT, expires = DEFAULT WHERE id = %s", (book_id,))
        if cursor.rowcount == 1:
            conn.commit()
            return jsonify({'message': 'Book returned successfully'}), 200
        else:
            return jsonify({'error': 'Book return failed. It may not exist'}), 404
    finally:
        cursor.close()


if __name__ == '__main__':
    # Use the dynamic port provided by Heroku through the PORT environment variable
    port = int(os.environ.get("PORT", 5000))
    app.run(debug=False, host='0.0.0.0', port=port)
