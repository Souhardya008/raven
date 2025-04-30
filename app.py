from flask import Flask, render_template, request, jsonify
import os
import datetime
import requests
import logging
from flask_sqlalchemy import SQLAlchemy

app = Flask(__name__)
logging.basicConfig(level=logging.DEBUG)

# Log environment variables for debugging (without showing sensitive values)
print("Environment variables present:", list(os.environ.keys()))

# Configure Database with fallback for local development
database_url = os.environ.get("DATABASE_URL")
if database_url:
    print("Database URL found in environment")
else:
    print("No Database URL found in environment, using fallback")
    database_url = "sqlite:///temp.db"  # Local fallback

app.config["SQLALCHEMY_DATABASE_URI"] = database_url
app.config["SQLALCHEMY_ENGINE_OPTIONS"] = {
    "pool_recycle": 300,
    "pool_pre_ping": True,
}
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

# Initialize database
db = SQLAlchemy(app)

# Define Vouch model directly in app.py
class Vouch(db.Model):
    __tablename__ = 'vouches'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.String(20), nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.datetime.utcnow)
    stars = db.Column(db.Integer, nullable=False)
    message = db.Column(db.Text, nullable=False)
    
    def __repr__(self):
        return f'<Vouch {self.id} from {self.user_id}>'

# Create tables if they don't exist
with app.app_context():
    db.create_all()

DISCORD_API_BASE = "https://discord.com/api/v10"
DISCORD_BOT_TOKEN = os.getenv("DISCORD_TOKEN")  # Get from environment variable

# Cache to store Discord user data to minimize API calls
user_cache = {}

def get_discord_user(user_id):
    """Fetch Discord user data from the API or cache"""
    if user_id in user_cache:
        return user_cache[user_id]
    
    # If we don't have a bot token, return default user data
    if not DISCORD_BOT_TOKEN:
        default_user = {
            'id': user_id,
            'username': f'User {user_id[:6]}' if len(user_id) > 6 else f'User {user_id}',
            'avatar': None,
            'discriminator': '0000'
        }
        return default_user
    
    headers = {
        'Authorization': f'Bot {DISCORD_BOT_TOKEN}'
    }
    
    try:
        response = requests.get(f"{DISCORD_API_BASE}/users/{user_id}", headers=headers)
        if response.status_code == 200:
            user_data = response.json()
            user_cache[user_id] = user_data
            return user_data
        else:
            logging.error(f"Failed to fetch Discord user: {response.status_code} - {response.text}")
    except Exception as e:
        logging.error(f"Error fetching Discord user: {str(e)}")
    
    # Default fallback data
    default_user = {
        'id': user_id,
        'username': f'User {user_id[:6]}',
        'avatar': None,
        'discriminator': '0000'
    }
    return default_user

def get_avatar_url(user_data):
    """Generate proper Discord avatar URL based on user data"""
    user_id = user_data['id']
    avatar_hash = user_data.get('avatar')
    
    if avatar_hash:
        # Check if it's an animated avatar (starts with 'a_')
        if avatar_hash.startswith('a_'):
            return f"https://cdn.discordapp.com/avatars/{user_id}/{avatar_hash}.gif"
        else:
            return f"https://cdn.discordapp.com/avatars/{user_id}/{avatar_hash}.png"
    else:
        # Return default Discord avatar
        discriminator = int(user_data.get('discriminator', '0000')) % 5
        return f"https://cdn.discordapp.com/embed/avatars/{discriminator}.png"

@app.route('/')
def home():
    # Get vouches from database
    vouches_db = Vouch.query.order_by(Vouch.timestamp.desc()).all()
    
    vouches = []
    stars_total = 0
    user_counts = {}

    for vouch in vouches_db:
        user_id = vouch.user_id
        
        # Get user data from Discord API or cache
        user_data = get_discord_user(user_id)
        
        stars_total += vouch.stars
        user_counts[user_id] = user_counts.get(user_id, 0) + 1
        
        vouches.append({
            'user_id': user_id,
            'timestamp': vouch.timestamp.strftime("%Y-%m-%d %H:%M:%S"),  # Keep original format for sorting
            'display_time': vouch.timestamp.strftime("%b %d, %Y %I:%M %p"),
            'stars': vouch.stars,
            'message': vouch.message,
            'user_name': user_data['username'],
            'user_avatar': get_avatar_url(user_data)
        })

    avg_rating = round(stars_total / len(vouches_db), 2) if vouches_db else 0

    stats = {
        'total_vouches': len(vouches_db),
        'average_rating': avg_rating
    }

    # Calculate top vouchers
    top_vouchers_list = []
    for user_id, count in sorted(user_counts.items(), key=lambda x: x[1], reverse=True)[:3]:
        user_data = get_discord_user(user_id)
        
        top_vouchers_list.append({
            'user_id': user_id,
            'user_name': user_data['username'],
            'discord_avatar_url': get_avatar_url(user_data),
            'vouch_count': count,
            'score': count,
            'currency': 'vouches'
        })

    return render_template('index.html', 
                          recent_vouches=vouches, 
                          top_vouchers=top_vouchers_list, 
                          stats=stats)

@app.route('/api/vouches', methods=['POST'])
def add_vouch():
    data = request.json
    user_id = data.get('user_id')
    stars = data.get('stars')
    msg = data.get('msg')

    if not user_id or not stars or not msg:
        return jsonify({"error": "Missing required fields"}), 400

    # Create a new vouch in the database
    new_vouch = Vouch(
        user_id=user_id,
        stars=stars,
        message=msg
    )
    
    db.session.add(new_vouch)
    db.session.commit()

    return jsonify({"success": True}), 201

@app.route('/migrate', methods=['GET'])
def migrate_data():
    """One-time route to migrate data from text file to database"""
    if not os.path.exists('ravenshop.txt'):
        return jsonify({"message": "No data file to migrate"})
        
    with open('ravenshop.txt', 'r') as f:
        lines = [line.strip() for line in f if line.strip()]
    
    migrated_count = 0
    for line in lines:
        parts = line.split('|')
        if len(parts) < 4:
            continue
            
        user_id = parts[0].replace("UserID:", "").strip()
        time_str = parts[1].strip()
        stars = int(parts[2].replace("Stars:", "").strip())
        msg = parts[3].replace("Message:", "").strip().strip('"')
        
        timestamp = datetime.datetime.strptime(time_str, "%Y-%m-%d %H:%M:%S")
        
        # Check if this vouch already exists to avoid duplicates
        existing = Vouch.query.filter_by(
            user_id=user_id,
            timestamp=timestamp,
            stars=stars
        ).first()
        
        if not existing:
            new_vouch = Vouch(
                user_id=user_id,
                timestamp=timestamp,
                stars=stars,
                message=msg
            )
            db.session.add(new_vouch)
            migrated_count += 1
    
    db.session.commit()
    return jsonify({"success": True, "migrated_count": migrated_count})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
