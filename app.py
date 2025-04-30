
from flask import Flask, render_template, request, jsonify
import os
import datetime

app = Flask(__name__)

VOUCH_FILE = 'ravenshop.txt'

@app.route('/')
def home():
    if not os.path.exists(VOUCH_FILE):
        return render_template('index.html', stats={}, vouches=[])

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
        stars_total += stars
        user_counts[user_id] = user_counts.get(user_id, 0) + 1
        vouches.append({
            'user_id': user_id,
            'timestamp': time,
            'stars': stars,
            'message': msg,
            'user_name': 'Anonymous',
            'user_avatar': None
        })

    avg_rating = round(stars_total / len(lines), 2) if lines else 0
    top_user = max(user_counts, key=user_counts.get) if user_counts else "N/A"

    stats = {
        'total_vouches': len(lines),
        'average_rating': avg_rating,
        'top_user': top_user
    }

    return render_template('index.html', recent_vouches=vouches, top_vouchers=[])

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
    app.run(host='0.0.0.0', port=5000)
