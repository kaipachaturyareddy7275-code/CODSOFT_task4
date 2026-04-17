from flask import Flask, render_template, request, redirect, session
import sqlite3, requests
import pandas as pd
from sklearn.feature_extraction.text import CountVectorizer
from sklearn.metrics.pairwise import cosine_similarity
from werkzeug.security import generate_password_hash, check_password_hash
from openai import OpenAI

app = Flask(__name__)
app.secret_key = "supersecretkey"

# 🔑 ADD YOUR KEYS HERE
TMDB_KEY = "YOUR_TMDB_API_KEY"
client = OpenAI(api_key="YOUR_OPENAI_KEY")

# ---------------- LOAD DATA ----------------
df = pd.read_csv("movies.csv")

cv = CountVectorizer()
matrix = cv.fit_transform(df["description"])
similarity = cosine_similarity(matrix)

# ---------------- DATABASE ----------------
def get_db():
    return sqlite3.connect("database.db")

# ---------------- 🎬 POSTER (FIXED) ----------------
def get_poster(movie):
    try:
        url = "https://api.themoviedb.org/3/search/movie"
        params = {
            "api_key": TMDB_KEY,
            "query": movie
        }

        res = requests.get(url, params=params, timeout=5)
        data = res.json()

        if data.get("results") and len(data["results"]) > 0:
            poster_path = data["results"][0].get("poster_path")
            if poster_path:
                return "https://image.tmdb.org/t/p/w500" + poster_path

    except Exception as e:
        print("Poster Error:", e)

    # fallback image (ALWAYS WORKS)
    return "https://via.placeholder.com/300x450?text=No+Image"

# ---------------- 🔥 TRENDING (FIXED) ----------------
def get_trending():
    try:
        url = "https://api.themoviedb.org/3/trending/movie/day"
        params = {"api_key": TMDB_KEY}

        res = requests.get(url, params=params, timeout=5)
        data = res.json()

        trending = []
        for m in data.get("results", [])[:10]:
            poster = m.get("poster_path")
            trending.append({
                "title": m.get("title", "Unknown"),
                "poster": "https://image.tmdb.org/t/p/w500" + poster if poster else "https://via.placeholder.com/300x450"
            })

        return trending

    except Exception as e:
        print("Trending Error:", e)
        return []

# ---------------- 🧠 HYBRID RECOMMENDER ----------------
def hybrid_recommend(user_id, movie):
    try:
        idx = df[df["title"] == movie].index[0]
        scores = list(enumerate(similarity[idx]))

        content_rec = [
            df.iloc[i[0]].title
            for i in sorted(scores, key=lambda x: x[1], reverse=True)[1:5]
        ]

        conn = get_db()
        likes = pd.read_sql_query("SELECT * FROM likes", conn)
        conn.close()

        liked_movies = likes[likes["user_id"] == user_id]["movie"].tolist()

        final = list(set(content_rec + liked_movies))
        return final[:6]

    except Exception as e:
        print("Recommendation Error:", e)
        return []

# ---------------- 🔐 AUTH ----------------
@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        username = request.form["username"]
        password = generate_password_hash(request.form["password"])

        conn = get_db()
        conn.execute("INSERT INTO users (username, password) VALUES (?, ?)",
                     (username, password))
        conn.commit()
        conn.close()

        return redirect("/login")

    return render_template("register.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]

        conn = get_db()
        cur = conn.cursor()
        cur.execute("SELECT * FROM users WHERE username=?", (username,))
        user = cur.fetchone()
        conn.close()

        if user and check_password_hash(user[2], password):
            session["user_id"] = user[0]
            return redirect("/")
        else:
            return "❌ Invalid login"

    return render_template("login.html")


@app.route("/logout")
def logout():
    session.clear()
    return redirect("/login")

# ---------------- 🏠 HOME ----------------
@app.route("/", methods=["GET", "POST"])
def home():
    if "user_id" not in session:
        return redirect("/login")

    recs = []
    selected = None

    if request.method == "POST":
        selected = request.form["movie"]

        recommendations = hybrid_recommend(session["user_id"], selected)

        for m in recommendations:
            recs.append({
                "title": m,
                "poster": get_poster(m)
            })

    return render_template("index.html",
                           movies=df["title"].tolist(),
                           recs=recs,
                           trending=get_trending(),
                           selected=selected)

# ---------------- ⭐ RATE ----------------
@app.route("/rate", methods=["POST"])
def rate():
    conn = get_db()
    conn.execute("INSERT INTO ratings VALUES (?, ?, ?)",
                 (session["user_id"], request.form["movie"], request.form["rating"]))
    conn.commit()
    conn.close()
    return redirect("/")

# ---------------- ❤️ LIKE ----------------
@app.route("/like", methods=["POST"])
def like():
    conn = get_db()
    conn.execute("INSERT INTO likes VALUES (?, ?)",
                 (session["user_id"], request.form["movie"]))
    conn.commit()
    conn.close()
    return redirect("/")

# ---------------- 🤖 CHATBOT ----------------
@app.route("/chat", methods=["POST"])
def chat():
    try:
        user_input = request.form["message"]

        response = client.chat.completions.create(
            model="gpt-4.1-mini",
            messages=[
                {"role": "system", "content": "You are a movie recommendation assistant."},
                {"role": "user", "content": user_input}
            ]
        )

        return response.choices[0].message.content

    except Exception as e:
        print("Chat Error:", e)
        return "⚠️ AI not available"

# ---------------- 📊 ADMIN ----------------
@app.route("/admin")
def admin():
    conn = get_db()

    users = pd.read_sql_query("SELECT * FROM users", conn)
    likes = pd.read_sql_query(
        "SELECT movie, COUNT(*) as count FROM likes GROUP BY movie",
        conn
    )

    conn.close()

    return render_template("admin.html",
                           users=users.to_dict("records"),
                           likes=likes.to_dict("records"))

# ---------------- 🚀 RUN ----------------
if __name__ == "__main__":
    app.run(debug=True)