# app.py - Flask Application configured for designthinkinginfinitescroll.free.nf
from flask import Flask, render_template, request, jsonify, redirect, url_for
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
import os
from werkzeug.utils import secure_filename

app = Flask(__name__)

# Production configuration
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'your-secret-key-here-change-in-production')
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL', 'sqlite:///campus_club.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['UPLOAD_FOLDER'] = 'static/uploads'
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max file size

# Production settings
app.config['SERVER_NAME'] = None  # Let Flask detect from request
app.config['PREFERRED_URL_SCHEME'] = 'https'  # Force HTTPS

db = SQLAlchemy(app)

# Create upload directory if it doesn't exist
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

# Database Models
class Club(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    username = db.Column(db.String(50), unique=True, nullable=False)
    bio = db.Column(db.String(200))
    avatar = db.Column(db.String(200), default='/static/default-avatar.png')
    subscribers = db.Column(db.Integer, default=0)
    posts = db.relationship('Post', backref='club', lazy=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class Post(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    club_id = db.Column(db.Integer, db.ForeignKey('club.id'), nullable=False)
    title = db.Column(db.String(200))
    content = db.Column(db.Text, nullable=False)
    media_url = db.Column(db.String(200))
    media_type = db.Column(db.String(20))
    likes = db.Column(db.Integer, default=0)
    views = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    event_type = db.Column(db.String(50))
    event_date = db.Column(db.DateTime)

class Subscription(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.String(100), nullable=False)
    club_id = db.Column(db.Integer, db.ForeignKey('club.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class Like(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.String(100), nullable=False)
    post_id = db.Column(db.Integer, db.ForeignKey('post.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

# Routes
@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/feed')
def get_feed():
    page = request.args.get('page', 1, type=int)
    per_page = 10
    
    posts = Post.query.order_by(Post.created_at.desc()).paginate(
        page=page, per_page=per_page, error_out=False
    )
    
    feed_data = []
    for post in posts.items:
        feed_data.append({
            'id': post.id,
            'title': post.title,
            'content': post.content,
            'media_url': post.media_url,
            'media_type': post.media_type,
            'likes': post.likes,
            'views': post.views,
            'created_at': post.created_at.strftime('%Y-%m-%d %H:%M'),
            'club': {
                'id': post.club.id,
                'name': post.club.name,
                'username': post.club.username,
                'avatar': post.club.avatar,
                'subscribers': post.club.subscribers
            },
            'event_type': post.event_type,
            'event_date': post.event_date.strftime('%Y-%m-%d %H:%M') if post.event_date else None
        })
    
    return jsonify({
        'posts': feed_data,
        'has_next': posts.has_next,
        'total': posts.total
    })

@app.route('/api/post', methods=['POST'])
def create_post():
    data = request.get_json()
    club_id = data.get('club_id', 1)
    
    new_post = Post(
        club_id=club_id,
        content=data.get('content', ''),
        media_url=data.get('media_url'),
        media_type=data.get('media_type'),
        event_type=data.get('event_type'),
        event_date=datetime.strptime(data['event_date'], '%Y-%m-%d %H:%M') if data.get('event_date') else None
    )
    
    db.session.add(new_post)
    db.session.commit()
    
    return jsonify({'success': True, 'post_id': new_post.id})

@app.route('/api/upload', methods=['POST'])
def upload_file():
    if 'file' not in request.files:
        return jsonify({'error': 'No file provided'}), 400
    
    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': 'No file selected'}), 400
    
    if file:
        filename = secure_filename(file.filename)
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f"{timestamp}_{filename}"
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(filepath)
        
        media_type = 'image' if filename.lower().endswith(('.png', '.jpg', '.jpeg', '.gif')) else 'video'
        
        return jsonify({
            'success': True,
            'media_url': f'/static/uploads/{filename}',
            'media_type': media_type
        })

@app.route('/api/like/<int:post_id>', methods=['POST'])
def toggle_like(post_id):
    user_id = request.get_json().get('user_id', 'demo_user')
    
    post = Post.query.get_or_404(post_id)
    existing_like = Like.query.filter_by(user_id=user_id, post_id=post_id).first()
    
    if existing_like:
        db.session.delete(existing_like)
        post.likes -= 1
        liked = False
    else:
        new_like = Like(user_id=user_id, post_id=post_id)
        db.session.add(new_like)
        post.likes += 1
        liked = True
    
    db.session.commit()
    
    return jsonify({
        'success': True,
        'liked': liked,
        'likes': post.likes
    })

@app.route('/api/subscribe/<int:club_id>', methods=['POST'])
def toggle_subscribe(club_id):
    user_id = request.get_json().get('user_id', 'demo_user')
    
    club = Club.query.get_or_404(club_id)
    existing_sub = Subscription.query.filter_by(user_id=user_id, club_id=club_id).first()
    
    if existing_sub:
        db.session.delete(existing_sub)
        club.subscribers -= 1
        subscribed = False
    else:
        new_sub = Subscription(user_id=user_id, club_id=club_id)
        db.session.add(new_sub)
        club.subscribers += 1
        subscribed = True
    
    db.session.commit()
    
    return jsonify({
        'success': True,
        'subscribed': subscribed,
        'subscribers': club.subscribers
    })

@app.route('/api/clubs')
def get_clubs():
    clubs = Club.query.all()
    return jsonify([{
        'id': c.id,
        'name': c.name,
        'username': c.username,
        'bio': c.bio,
        'avatar': c.avatar,
        'subscribers': c.subscribers
    } for c in clubs])

@app.route('/health')
def health_check():
    return jsonify({'status': 'healthy', 'domain': 'designthinkinginfinitescroll.free.nf'})

def init_database():
    with app.app_context():
        db.create_all()
        
        if Club.query.count() == 0:
            sample_clubs = [
                Club(name='政大電競社', username='@nccu_esports', bio='🎮 熊讚電競列車，帶你進入電競世界！', subscribers=2345),
                Club(name='藝文中心', username='@nccu_arts', bio='🎬 影展x藝術x文化，豐富你的大學生活', subscribers=3456),
                Club(name='商學院學生會', username='@nccu_commerce', bio='💼 連結產學，開拓職涯新視野', subscribers=4567),
                Club(name='永續發展辦公室', username='@nccu_sdgs', bio='🌱 打造永續校園，從你我開始', subscribers=1890),
                Club(name='國際事務處', username='@nccu_global', bio='🌍 拓展國際視野，連結全球脈動', subscribers=2678)
            ]
            
            for club in sample_clubs:
                db.session.add(club)
            
            db.session.commit()
            
            sample_posts = [
                Post(
                    club_id=1,
                    content="""2025熊讚電競列車 校園講座 政大場
🎮🚂 熊讚電競列車 校園講座 開跑！ 🚂🎮

想知道電競幕後的真實樣貌？想近距離與選手、實況主面對交流？這次絕對不能錯過！

📍 地點：綜合院館北棟 270401 教室
🗓 時間：2025/9/25 19:00～21:00

🔥 出席講者陣容：

Valorant 知名實況主 乖兒子 —— 與你分享遊戲與直播的心路歷程
現役台北熊讚戰隊快打旋風超新星 HOPE —— 從選手角度談談格鬥電競的世界
台北熊讚戰隊經理 阿祥 —— 帶你看見電競隊伍的營運與管理
📢 無論你是電競愛好者、資深遊戲玩家，或只是單純想認識遊戲產業，這趟「熊讚電競列車」都將帶給你滿滿收穫！

💡 免費入場，名額有限，快上車！""",
                    media_url='/static/uploads/club_id1.png',
                    media_type='image',
                    event_type='workshop',
                    event_date=datetime(2025, 9, 25, 19, 0),
                    likes=342,
                    views=1580
                ),
                Post(
                    club_id=2,
                    content="""藝中影展《配樂大師顏尼歐》Ennio: The Maestro
時間：9/26 (五) 14:00-16:40

地點：藝文中心三樓 視聽館

導演：朱賽貝·托納多雷

【影片介紹】

​義大利奧斯卡大衛獎最佳紀錄片、最佳剪輯、最佳音效三項大獎

本片由香港導演王家衛監製，為配樂大師顏尼歐莫利克奈（Ennio Morricone）的完整肖像。他是二十世紀最多產、並且最受歡迎的音樂家，曾獲兩座奧斯卡獎、創作出500多首令人難忘的電影配樂。本片透過《新天堂樂園》導演朱賽貝托納多雷對顏尼歐長時間的採訪，以及貝托魯奇、貝洛奇奧、阿基多、奧立佛史東、昆汀塔倫提諾等導演的訪談，佐以許多珍貴錄像、音樂與故地重遊的場景，交織出顏尼歐一生的全貌。""",
                    media_url='/static/uploads/club_id2.png',
                    media_type='image',
                    event_type='performance',
                    event_date=datetime(2025, 9, 26, 14, 0),
                    likes=256,
                    views=920
                ),
                Post(
                    club_id=3,
                    content="""【商學院職涯講座】金融素養從你開始
📸2025/09/30 (二)

📸時間：12:10-13:40

📸地點：商學院六樓義育廳


講者： 謝富旭 存股助理電子報總編輯

📸講座內容：

金融素養 × 青年視角

經貿政策如何牽動台灣產業趨勢發展

從存錢到投資：打造你的人生第一桶金

大學生也會遇到的金融陷阱與詐騙風險

存款保險 × 展現自我

年輕人必懂的存款保險制度

從你開始：用創作參與金融教育行動

現場Q&A小禮抽獎""",
                    media_url='/static/uploads/club_id3.png',
                    media_type='image',
                    event_type='workshop',
                    event_date=datetime(2025, 9, 30, 12, 10),
                    likes=489,
                    views=2100
                )
            ]
            
            for post in sample_posts:
                db.session.add(post)
            
            db.session.commit()
            print("Database initialized with sample data!")

if __name__ == '__main__':
    init_database()
    # Use environment variables for production
    port = int(os.environ.get('PORT', 4000))
    debug = os.environ.get('FLASK_ENV') != 'production'
    app.run(host='0.0.0.0', port=port, debug=debug)