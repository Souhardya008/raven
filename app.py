from flask import Flask, render_template, request, jsonify
import os
import datetime
import requests
import logging

app = Flask(__name__)
logging.basicConfig(level=logging.DEBUG)

VOUCH_FILE = 'ravenshop.txt'
DISCORD_API_BASE = "https://discord.com/api/v10"
DISCORD_BOT_TOKEN = os.getenv("DISCORD_TOKEN")  # Get from environment (matches the bot token name)

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
    if not os.path.exists(VOUCH_FILE):
        return render_template('index.html', stats={}, recent_vouches=[], top_vouchers=[])

    with open(VOUCH_FILE, 'r') as f:
        lines = [line.strip() for line in f if line.strip()]

    vouches = []
    stars_total = 0
    user_counts = {}

    for line in lines:
        parts = line.split('|')
        if len(parts) < 4:
            continue
        
        user_id = parts[0].replace("UserID:", "").strip()
        time = parts[1].strip()
        stars = int(parts[2].replace("Stars:", "").strip())
        msg = parts[3].replace("Message:", "").strip().strip('"')
        
        # Get user data from Discord API or cache
        user_data = get_discord_user(user_id)
        
        stars_total += stars
        user_counts[user_id] = user_counts.get(user_id, 0) + 1
        
        vouches.append({
            'user_id': user_id,
            'timestamp': time,  # Keep original format for sorting
            'display_time': datetime.datetime.strptime(time, "%Y-%m-%d %H:%M:%S").strftime("%b %d, %Y %I:%M %p"),
            'stars': stars,
            'message': msg,
            'user_name': user_data['username'],
            'user_avatar': get_avatar_url(user_data)
        })

    avg_rating = round(stars_total / len(lines), 2) if lines else 0

    stats = {
        'total_vouches': len(lines),
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

    timestamp = datetime.datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
    vouch_entry = f"UserID:{user_id} | {timestamp} | Stars:{stars} | Message:\"{msg}\"\n"

    with open(VOUCH_FILE, 'a') as f:
        f.write(vouch_entry)

    return jsonify({"success": True}), 201

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
