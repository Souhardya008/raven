from flask import Flask, render_template
import os

app = Flask(__name__)

VOUCH_FILE = 'ravenshop.txt'

@app.route('/')
def index():
    if not os.path.exists(VOUCH_FILE):
        return render_template('index.html', stats={}, vouches=[])

    with open(VOUCH_FILE, 'r') as f:
        lines = [line.strip() for line in f if line.strip()]

    vouches = []
    stars_total = 0
    user_counts = {}

    for line in lines:
        parts = line.split('|')
        if len(parts) < 4: continue
        user_id = parts[0].replace("UserID:", "").strip()
        time = parts[1].strip()
        stars = int(parts[2].replace("Stars:", "").strip())
        msg = parts[3].replace("Message:", "").strip().strip('"')
        stars_total += stars
        user_counts[user_id] = user_counts.get(user_id, 0) + 1
        vouches.append({'user_id': user_id, 'time': time, 'stars': stars, 'msg': msg})

    vouches = vouches[-5:][::-1]
    avg_rating = round(stars_total / len(lines), 2) if lines else 0
    top_user = max(user_counts, key=user_counts.get) if user_counts else "N/A"

    stats = {
        'total_vouches': len(lines),
        'average_rating': avg_rating,
        'top_user': top_user
    }

    return render_template('index.html', stats=stats, vouches=vouches)

# Start the app here
if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))  # Get the port from the environment variable
    app.run(host='0.0.0.0', port=port, debug=True)


