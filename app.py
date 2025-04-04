import os
import sqlite3
import requests
import fitz  # PyMuPDF for PDF text extraction
from flask import Flask, request, jsonify, render_template, g

app = Flask(__name__)

# API Keys
GROQ_API_KEY = ""

# API Endpoint
GROQ_API_URL = ""
MODEL_NAME = ""

DATABASE = "chat_history.db"
uploaded_pdf_text = ""  # Store extracted PDF text

# -------------------- DATABASE FUNCTIONS --------------------
def get_db():
    """Connects to the database and returns the connection object."""
    db = getattr(g, '_database', None)
    if db is None:
        db = g._database = sqlite3.connect(DATABASE, check_same_thread=False)
        db.row_factory = sqlite3.Row
    return db

def init_db():
    """Creates the chat history table if it doesn't exist."""
    with app.app_context():
        db = get_db()
        cursor = db.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS chat_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_message TEXT,
                bot_reply TEXT
            )
        ''')
        db.commit()

@app.teardown_appcontext
def close_connection(exception):
    """Closes the database connection after each request."""
    db = getattr(g, '_database', None)
    if db is not None:
        db.close()

# -------------------- ROUTES --------------------

@app.route("/")
def index():
    return render_template("index.html")

# -------------------- PDF UPLOAD --------------------
@app.route("/upload", methods=["POST"])
def upload_pdf():
    global uploaded_pdf_text
    if "file" not in request.files:
        return jsonify({"message": "No file uploaded"}), 400

    file = request.files["file"]
    if file.filename == "" or not file.filename.endswith(".pdf"):
        return jsonify({"message": "Invalid file type"}), 400

    try:
        uploaded_pdf_text = extract_text_from_pdf(file)
        return jsonify({"message": "PDF uploaded successfully"})
    except Exception as e:
        return jsonify({"message": f"Error processing PDF: {str(e)}"}), 500

def extract_text_from_pdf(file):
    """Extracts text from an uploaded PDF."""
    doc = fitz.open(stream=file.read(), filetype="pdf")
    text = "\n".join([page.get_text("text") for page in doc])
    return text if text.strip() else "No text found in PDF."

# -------------------- CHAT FUNCTION --------------------
@app.route("/chat", methods=["POST"])
def chat():
    global uploaded_pdf_text
    user_message = request.json.get("message", "").strip()

    if not user_message:
        return jsonify({"reply": "Please enter a message"}), 400

    system_prompt = (
        f"You are KiitGPT, an AI assistant for KIIT students.I am developed and trained by Arya Vats,a lovable kiitianAnswer queries based on uploaded documents if available, "
        f"or provide normal responses if no PDF is uploaded.\n\n"
        f"Uploaded PDF Content:\n\n{uploaded_pdf_text}\n\n"
        if uploaded_pdf_text else "You are KiitGPT, an AI assistant for KIIT students. Answer queries as best as you can."
    )

    payload = {
        "model": MODEL_NAME,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message}
        ],
        "temperature": 0.7
    }

    headers = {
        "Authorization": f"Bearer {GROQ_API_KEY}",
        "Content-Type": "application/json"
    }

    try:
        response = requests.post(GROQ_API_URL, headers=headers, json=payload)
        response_json = response.json()
        bot_reply = response_json["choices"][0]["message"]["content"].strip()

        # Store chat in the database
        db = get_db()
        cursor = db.cursor()
        cursor.execute("INSERT INTO chat_history (user_message, bot_reply) VALUES (?, ?)", (user_message, bot_reply))
        db.commit()

        return jsonify({"reply": bot_reply})
    except Exception as e:
        return jsonify({"reply": f"Error: {str(e)}"}), 500

# -------------------- HISTORY --------------------
@app.route("/history", methods=["GET"])
def get_chat_history():
    """Fetches the stored chat history from the database."""
    db = get_db()
    cursor = db.cursor()
    cursor.execute("SELECT user_message, bot_reply FROM chat_history ORDER BY id DESC")
    history = cursor.fetchall()
    
    chat_list = [{"user": row["user_message"], "bot": row["bot_reply"]} for row in history]
    return jsonify({"history": chat_list})

# Initialize database when the app starts
init_db()

if __name__ == "__main__":
    app.run(debug=True)
