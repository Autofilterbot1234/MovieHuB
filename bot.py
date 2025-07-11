# FINAL, CLEANED CODE FOR VERCEL
import os
import sys
import re
import requests
from flask import Flask, render_template_string, request, redirect, url_for, Response, jsonify
from pymongo import MongoClient
from bson.objectid import ObjectId
from functools import wraps
from datetime import datetime

# ======================================================================
# --- আপনার ব্যক্তিগত ও অ্যাডমিন তথ্য (এনভায়রনমেন্ট থেকে লোড হবে) ---
# ======================================================================
MONGO_URI = os.environ.get("MONGO_URI")
BOT_TOKEN = os.environ.get("BOT_TOKEN")
TMDB_API_KEY = os.environ.get("TMDB_API_KEY")
ADMIN_CHANNEL_ID = os.environ.get("ADMIN_CHANNEL_ID")
BOT_USERNAME = os.environ.get("BOT_USERNAME")
ADMIN_USERNAME = os.environ.get("ADMIN_USERNAME")
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD")

# --- প্রয়োজনীয় ভেরিয়েবলগুলো সেট করা হয়েছে কিনা তা পরীক্ষা করা ---
required_vars = {
    "MONGO_URI": MONGO_URI, "BOT_TOKEN": BOT_TOKEN, "TMDB_API_KEY": TMDB_API_KEY,
    "ADMIN_CHANNEL_ID": ADMIN_CHANNEL_ID, "BOT_USERNAME": BOT_USERNAME,
    "ADMIN_USERNAME": ADMIN_USERNAME, "ADMIN_PASSWORD": ADMIN_PASSWORD,
}

missing_vars = [name for name, value in required_vars.items() if not value]
if missing_vars:
    print(f"FATAL: Missing required environment variables: {', '.join(missing_vars)}")
    sys.exit(1)

# ======================================================================

# --- অ্যাপ্লিকেশন সেটআপ ---
TELEGRAM_API_URL = f"https://api.telegram.org/bot{BOT_TOKEN}"
app = Flask(__name__)

# --- অ্যাডমিন অথেন্টিকেশন ফাংশন ---
def check_auth(username, password):
    return username == ADMIN_USERNAME and password == ADMIN_PASSWORD

def authenticate():
    return Response('Could not verify your access level.', 401, {'WWW-Authenticate': 'Basic realm="Login Required"'})

def requires_auth(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        auth = request.authorization
        if not auth or not check_auth(auth.username, auth.password):
            return authenticate()
        return f(*args, **kwargs)
    return decorated

# --- ডাটাবেস কানেকশন ---
try:
    client = MongoClient(MONGO_URI)
    db = client["movie_db"]
    movies = db["movies"]
    settings = db["settings"]
    feedback = db["feedback"]
    print("SUCCESS: Successfully connected to MongoDB!")
except Exception as e:
    print(f"FATAL: Error connecting to MongoDB: {e}. Exiting.")
    sys.exit(1)

# --- Context Processor: বিজ্ঞাপনের কোড সহজলভ্য করার জন্য ---
@app.context_processor
def inject_ads():
    ad_codes = settings.find_one()
    return dict(ad_settings=(ad_codes or {}), bot_username=BOT_USERNAME)

# --- HTML টেমপ্লেট ---
# [এখানে আপনার বিশাল HTML স্ট্রিংগুলো থাকবে, কোনো পরিবর্তন ছাড়াই]
index_html = """ ... """ # আপনার আগের কোড থেকে কপি করুন
detail_html = """ ... """ # আপনার আগের কোড থেকে কপি করুন
genres_html = """ ... """ # আপনার আগের কোড থেকে কপি করুন
watch_html = """ ... """ # আপনার আগের কোড থেকে কপি করুন
admin_html = """ ... """ # আপনার আগের কোড থেকে কপি করুন
edit_html = """ ... """ # আপনার আগের কোড থেকে কপি করুন
contact_html = """ ... """# আপনার আগের কোড থেকে কপি করুন

# ======================================================================
# --- Helper Functions ---
# ======================================================================
def parse_filename(filename):
    cleaned_name = filename.replace('.', ' ').replace('_', ' ')
    base_name = re.sub(r'(\d{3,4}p|web-?dl|hdrip|bluray|x264|x265|hevc|pack|complete|final|dual audio|hindi|season).*$', '', cleaned_name, flags=re.IGNORECASE).strip()
    series_match = re.search(r'^(.*?)[\s\._-]*[sS](\d+)[eE](\d+)', base_name, re.IGNORECASE)
    if series_match:
        title = series_match.group(1).strip()
        title = re.sub(r'\s*season\s*\d+\s*$', '', title, flags=re.IGNORECASE).strip()
        return {'type': 'series', 'title': title, 'season': int(series_match.group(2)), 'episode': int(series_match.group(3))}
    movie_match = re.search(r'^(.*?)\s*\(?(\d{4})\)?', base_name, re.IGNORECASE)
    if movie_match:
        return {'type': 'movie', 'title': movie_match.group(1).strip(), 'year': movie_match.group(2).strip()}
    return {'type': 'movie', 'title': base_name, 'year': None}

def get_tmdb_details_from_api(title, content_type, year=None):
    if not TMDB_API_KEY: return None
    search_type = "tv" if content_type == "series" else "movie"
    try:
        search_url = f"https://api.themoviedb.org/3/search/{search_type}?api_key={TMDB_API_KEY}&query={requests.utils.quote(title)}"
        if year and search_type == "movie": search_url += f"&primary_release_year={year}"
        search_res = requests.get(search_url, timeout=5).json()
        if not search_res.get("results"): return None
        
        tmdb_id = search_res["results"][0].get("id")
        detail_url = f"https://api.themoviedb.org/3/{search_type}/{tmdb_id}?api_key={TMDB_API_KEY}"
        res = requests.get(detail_url, timeout=5).json()
        
        return {
            "tmdb_id": tmdb_id, "title": res.get("title") if search_type == "movie" else res.get("name"),
            "poster": f"https://image.tmdb.org/t/p/w500{res.get('poster_path')}" if res.get('poster_path') else None,
            "overview": res.get("overview"), "release_date": res.get("release_date") if search_type == "movie" else res.get("first_air_date"),
            "genres": [g['name'] for g in res.get("genres", [])], "vote_average": res.get("vote_average")
        }
    except requests.RequestException as e:
        print(f"TMDb API error for '{title}': {e}")
    return None

def process_movie_list(movie_list):
    for item in movie_list:
        if '_id' in item: item['_id'] = str(item['_id'])
    return movie_list

# ======================================================================
# --- Main Flask Routes ---
# ======================================================================
@app.route('/')
def home():
    query = request.args.get('q')
    if query:
        movies_list = list(movies.find({"title": {"$regex": query, "$options": "i"}}).sort('_id', -1))
        return render_template_string(index_html, movies=process_movie_list(movies_list), query=f'Results for "{query}"', is_full_page_list=True)
    
    all_badges = sorted([badge for badge in movies.distinct("poster_badge") if badge])
    limit = 12
    context = {
        "trending_movies": process_movie_list(list(movies.find({"is_trending": True, "is_coming_soon": {"$ne": True}}).sort('_id', -1).limit(limit))),
        "latest_movies": process_movie_list(list(movies.find({"type": "movie", "is_coming_soon": {"$ne": True}}).sort('_id', -1).limit(limit))),
        "latest_series": process_movie_list(list(movies.find({"type": "series", "is_coming_soon": {"$ne": True}}).sort('_id', -1).limit(limit))),
        "coming_soon_movies": process_movie_list(list(movies.find({"is_coming_soon": True}).sort('_id', -1).limit(limit))),
        "recently_added": process_movie_list(list(movies.find({"is_coming_soon": {"$ne": True}}).sort('_id', -1).limit(6))),
        "recently_added_full": process_movie_list(list(movies.find({"is_coming_soon": {"$ne": True}}).sort('_id', -1).limit(limit))),
        "is_full_page_list": False, "query": "", "all_badges": all_badges
    }
    return render_template_string(index_html, **context)

@app.route('/movie/<movie_id>')
def movie_detail(movie_id):
    try:
        movie = movies.find_one({"_id": ObjectId(movie_id)})
        if not movie: return "Content not found", 404
        
        related_movies = []
        if movie.get("genres"):
            related_movies = list(movies.find({"genres": {"$in": movie["genres"]}, "_id": {"$ne": ObjectId(movie_id)}}).limit(12))
            
        trailer_key = None
        if movie.get("tmdb_id") and TMDB_API_KEY:
            tmdb_type = "tv" if movie.get("type") == "series" else "movie"
            video_url = f"https://api.themoviedb.org/3/{tmdb_type}/{movie['tmdb_id']}/videos?api_key={TMDB_API_KEY}"
            try:
                video_res = requests.get(video_url, timeout=3).json()
                for v in video_res.get("results", []):
                    if v.get('type') == 'Trailer' and v.get('site') == 'YouTube': 
                        trailer_key = v.get('key'); break
            except requests.RequestException: pass
                
        return render_template_string(detail_html, movie=movie, trailer_key=trailer_key, related_movies=process_movie_list(related_movies))
    except Exception as e: return f"An error occurred: {e}", 500

@app.route('/watch/<movie_id>')
def watch_movie(movie_id):
    try:
        movie = movies.find_one({"_id": ObjectId(movie_id)})
        if not movie or not movie.get("watch_link"): return "Content not found.", 404
        return render_template_string(watch_html, watch_link=movie["watch_link"], title=movie["title"])
    except Exception as e: return "An error occurred.", 500

def render_full_list(content_list, title):
    return render_template_string(index_html, movies=process_movie_list(content_list), query=title, is_full_page_list=True)

@app.route('/badge/<badge_name>')
def movies_by_badge(badge_name): return render_full_list(list(movies.find({"poster_badge": badge_name}).sort('_id', -1)), f'Tag: {badge_name}')
@app.route('/genres')
def genres_page(): return render_template_string(genres_html, genres=sorted([g for g in movies.distinct("genres") if g]), title="Browse by Genre")
@app.route('/genre/<genre_name>')
def movies_by_genre(genre_name): return render_full_list(list(movies.find({"genres": genre_name}).sort('_id', -1)), f'Genre: {genre_name}')
@app.route('/trending_movies')
def trending_movies(): return render_full_list(list(movies.find({"is_trending": True, "is_coming_soon": {"$ne": True}}).sort('_id', -1)), "Trending Now")
@app.route('/movies_only')
def movies_only(): return render_full_list(list(movies.find({"type": "movie", "is_coming_soon": {"$ne": True}}).sort('_id', -1)), "All Movies")
@app.route('/webseries')
def webseries(): return render_full_list(list(movies.find({"type": "series", "is_coming_soon": {"$ne": True}}).sort('_id', -1)), "All Web Series")
@app.route('/coming_soon')
def coming_soon(): return render_full_list(list(movies.find({"is_coming_soon": True}).sort('_id', -1)), "Coming Soon")
@app.route('/recently_added')
def recently_added_all(): return render_full_list(list(movies.find({"is_coming_soon": {"$ne": True}}).sort('_id', -1)), "Recently Added")

# ======================================================================
# --- Admin and Webhook Routes ---
# ======================================================================
@app.route('/admin', methods=["GET", "POST"])
@requires_auth
def admin():
    if request.method == "POST":
        content_type = request.form.get("content_type", "movie")
        tmdb_data = get_tmdb_details_from_api(request.form.get("title"), content_type) or {}
        movie_data = {"title": request.form.get("title"), "type": content_type, **tmdb_data, "is_trending": False, "is_coming_soon": False}
        
        if content_type == "movie":
            movie_data["watch_link"] = request.form.get("watch_link", "")
            links = []
            if request.form.get("link_480p"): links.append({"quality": "480p", "url": request.form.get("link_480p")})
            if request.form.get("link_720p"): links.append({"quality": "720p", "url": request.form.get("link_720p")})
            if request.form.get("link_1080p"): links.append({"quality": "1080p", "url": request.form.get("link_1080p")})
            movie_data["links"] = links
        else: # series
            episodes = []
            ep_numbers = request.form.getlist('episode_number[]')
            for i in range(len(ep_numbers)):
                ep_links = []
                if request.form.getlist('episode_link_480p[]')[i]: ep_links.append({"quality": "480p", "url": request.form.getlist('episode_link_480p[]')[i]})
                if request.form.getlist('episode_link_720p[]')[i]: ep_links.append({"quality": "720p", "url": request.form.getlist('episode_link_720p[]')[i]})
                episodes.append({"season": int(request.form.getlist('episode_season[]')[i]), "episode_number": int(ep_numbers[i]), "title": request.form.getlist('episode_title[]')[i], "watch_link": request.form.getlist('episode_watch_link[]')[i], "links": ep_links})
            movie_data["episodes"] = episodes
        movies.insert_one(movie_data)
        return redirect(url_for('admin'))
    
    all_content = process_movie_list(list(movies.find().sort('_id', -1)))
    feedback_list = process_movie_list(list(feedback.find().sort('timestamp', -1)))
    return render_template_string(admin_html, all_content=all_content, feedback_list=feedback_list)

@app.route('/admin/save_ads', methods=['POST'])
@requires_auth
def save_ads():
    ad_codes = {
        "popunder_code": request.form.get("popunder_code", ""), 
        "social_bar_code": request.form.get("social_bar_code", ""), 
        "banner_ad_code": request.form.get("banner_ad_code", ""), 
        "native_banner_code": request.form.get("native_banner_code", "")
    }
    settings.update_one({}, {"$set": ad_codes}, upsert=True)
    return redirect(url_for('admin'))

@app.route('/edit_movie/<movie_id>', methods=["GET", "POST"])
@requires_auth
def edit_movie(movie_id):
    movie_obj = movies.find_one({"_id": ObjectId(movie_id)})
    if not movie_obj: return "Movie not found", 404
    if request.method == "POST":
        content_type = request.form.get("content_type", "movie")
        update_data = {
            "title": request.form.get("title"), 
            "type": content_type, 
            "is_trending": request.form.get("is_trending") == "true", 
            "is_coming_soon": request.form.get("is_coming_soon") == "true", 
            "poster": request.form.get("poster", "").strip(), 
            "overview": request.form.get("overview", "").strip(), 
            "genres": [g.strip() for g in request.form.get("genres", "").split(',') if g.strip()], 
            "poster_badge": request.form.get("poster_badge", "").strip() or None
        }
        if content_type == "movie":
            update_data["watch_link"] = request.form.get("watch_link", "")
            links = []
            if request.form.get("link_480p"): links.append({"quality": "480p", "url": request.form.get("link_480p")})
            if request.form.get("link_720p"): links.append({"quality": "720p", "url": request.form.get("link_720p")})
            if request.form.get("link_1080p"): links.append({"quality": "1080p", "url": request.form.get("link_1080p")})
            update_data["links"] = links
            movies.update_one({"_id": ObjectId(movie_id)}, {"$unset": {"episodes": ""}})
        else: # series
            episodes = []
            ep_numbers = request.form.getlist('episode_number[]')
            for i in range(len(ep_numbers)):
                ep_links = []
                if request.form.getlist('episode_link_480p[]')[i]: ep_links.append({"quality": "480p", "url": request.form.getlist('episode_link_480p[]')[i]})
                if request.form.getlist('episode_link_720p[]')[i]: ep_links.append({"quality": "720p", "url": request.form.getlist('episode_link_720p[]')[i]})
                episodes.append({
                    "season": int(request.form.getlist('episode_season[]')[i]), 
                    "episode_number": int(ep_numbers[i]), 
                    "title": request.form.getlist('episode_title[]')[i], 
                    "watch_link": request.form.getlist('episode_watch_link[]')[i], 
                    "links": ep_links
                })
            update_data["episodes"] = episodes
            movies.update_one({"_id": ObjectId(movie_id)}, {"$unset": {"links": "", "watch_link": ""}})
        
        movies.update_one({"_id": ObjectId(movie_id)}, {"$set": update_data})
        return redirect(url_for('admin'))
    return render_template_string(edit_html, movie=movie_obj)

@app.route('/delete_movie/<movie_id>')
@requires_auth
def delete_movie(movie_id):
    movies.delete_one({"_id": ObjectId(movie_id)})
    return redirect(url_for('admin'))

@app.route('/contact', methods=['GET', 'POST'])
def contact():
    if request.method == 'POST':
        feedback_data = {
            "type": request.form.get("type"), 
            "content_title": request.form.get("content_title"), 
            "message": request.form.get("message"), 
            "email": request.form.get("email", "").strip(), 
            "reported_content_id": request.form.get("reported_content_id"), 
            "timestamp": datetime.utcnow()
        }
        feedback.insert_one(feedback_data)
        return render_template_string(contact_html, message_sent=True)
    prefill_title, prefill_id = request.args.get('title', ''), request.args.get('report_id', '')
    prefill_type = 'Problem Report' if prefill_id else 'Movie Request'
    return render_template_string(contact_html, message_sent=False, prefill_title=prefill_title, prefill_id=prefill_id, prefill_type=prefill_type)
    
@app.route('/delete_feedback/<feedback_id>')
@requires_auth
def delete_feedback(feedback_id):
    feedback.delete_one({"_id": ObjectId(feedback_id)})
    return redirect(url_for('admin'))

@app.route('/webhook', methods=['POST'])
def telegram_webhook():
    data = request.get_json()
    if 'channel_post' in data:
        post = data['channel_post']
        if str(post.get('chat', {}).get('id')) != ADMIN_CHANNEL_ID:
            return jsonify(status='ok', reason='not_admin_channel')

        file = post.get('video') or post.get('document')
        if not (file and file.get('file_name')):
            return jsonify(status='ok', reason='no_file_in_post')

        filename = file.get('file_name')
        parsed_info = parse_filename(filename)
        quality_match = re.search(r'(\d{3,4})p', filename, re.IGNORECASE)
        quality = quality_match.group(1) + "p" if quality_match else "HD"
        tmdb_data = get_tmdb_details_from_api(parsed_info['title'], parsed_info['type'], parsed_info.get('year'))

        if not tmdb_data or not tmdb_data.get("tmdb_id"):
            print(f"Webhook FATAL: Could not find TMDb data or tmdb_id for '{parsed_info['title']}'. Skipping.")
            return jsonify(status='ok', reason='no_tmdb_data_or_id')
        
        tmdb_id = tmdb_data.get("tmdb_id")

        if parsed_info['type'] == 'series':
            existing_series = movies.find_one({"tmdb_id": tmdb_id})
            new_episode = {"season": parsed_info['season'], "episode_number": parsed_info['episode'], "message_id": post['message_id'], "quality": quality}
            if existing_series:
                movies.update_one(
                    {"_id": existing_series['_id']}, 
                    {"$pull": {"episodes": {"season": new_episode['season'], "episode_number": new_episode['episode_number']}}}
                )
                movies.update_one({"_id": existing_series['_id']}, {"$push": {"episodes": new_episode}})
            else:
                series_doc = {**tmdb_data, "type": "series", "is_trending": False, "is_coming_soon": False, "episodes": [new_episode]}
                movies.insert_one(series_doc)
        else: # movie
            existing_movie = movies.find_one({"tmdb_id": tmdb_id})
            new_file = {"quality": quality, "message_id": post['message_id']}
            if existing_movie:
                movies.update_one(
                    {"_id": existing_movie['_id']}, 
                    {"$pull": {"files": {"quality": new_file['quality']}}}
                )
                movies.update_one({"_id": existing_movie['_id']}, {"$push": {"files": new_file}})
            else:
                movie_doc = {**tmdb_data, "type": "movie", "is_trending": False, "is_coming_soon": False, "files": [new_file]}
                movies.insert_one(movie_doc)

    elif 'message' in data:
        message = data['message']
        chat_id = message['chat']['id']
        text = message.get('text', '')
        if text.startswith('/start'):
            parts = text.split()
            if len(parts) > 1:
                try:
                    payload_parts = parts[1].split('_')
                    doc_id_str = payload_parts[0]
                    content = movies.find_one({"_id": ObjectId(doc_id_str)})
                    if not content:
                        requests.get(f"{TELEGRAM_API_URL}/sendMessage", params={'chat_id': chat_id, 'text': "Content not found."})
                        return jsonify(status='ok')

                    message_to_copy_id = None
                    if content.get('type') == 'series' and len(payload_parts) == 3:
                        s_num, e_num = int(payload_parts[1]), int(payload_parts[2])
                        target_episode = next((ep for ep in content.get('episodes', []) if ep.get('season') == s_num and ep.get('episode_number') == e_num), None)
                        if target_episode: message_to_copy_id = target_episode.get('message_id')
                    elif content.get('type') == 'movie' and len(payload_parts) == 2:
                        quality_to_find = payload_parts[1]
                        target_file = next((f for f in content.get('files', []) if f.get('quality') == quality_to_find), None)
                        if target_file: message_to_copy_id = target_file.get('message_id')
                    
                    if message_to_copy_id:
                        payload = {'chat_id': chat_id, 'from_chat_id': ADMIN_CHANNEL_ID, 'message_id': message_to_copy_id}
                        res = requests.post(f"{TELEGRAM_API_URL}/copyMessage", json=payload)
                        if not res.json().get('ok'):
                             print(f"Failed to copy message: {res.text}")
                             requests.get(f"{TELEGRAM_API_URL}/sendMessage", params={'chat_id': chat_id, 'text': "Error sending file. It might have been deleted."})
                    else:
                        requests.get(f"{TELEGRAM_API_URL}/sendMessage", params={'chat_id': chat_id, 'text': "Requested file/quality not found."})
                except Exception as e:
                    print(f"Error processing /start command: {e}")
                    requests.get(f"{TELEGRAM_API_URL}/sendMessage", params={'chat_id': chat_id, 'text': "An unexpected error occurred."})
            else:
                requests.get(f"{TELEGRAM_API_URL}/sendMessage", params={'chat_id': chat_id, 'text': "Welcome! Browse our site to find content."})

    return jsonify(status='ok')

# The if __name__ == "__main__": block is not needed for Vercel, but it's good for local testing.
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
