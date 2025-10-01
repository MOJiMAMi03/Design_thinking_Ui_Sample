# app.py - Main Flask Application (Complete Revised Version)
from flask import Flask, render_template, request, jsonify, redirect, url_for
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
import os
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.config['SECRET_KEY'] = 'your-secret-key-here'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///campus_club.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['UPLOAD_FOLDER'] = 'static/uploads'
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max file size

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
    title = db.Column(db.String(200))  # Add title field
    content = db.Column(db.Text, nullable=False)
    media_url = db.Column(db.String(200))
    media_type = db.Column(db.String(20))  # 'image' or 'video'
    likes = db.Column(db.Integer, default=0)
    views = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Tags for categorization
    event_type = db.Column(db.String(50))  # 'meeting', 'party', 'workshop', etc.
    event_date = db.Column(db.DateTime)

class Subscription(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.String(100), nullable=False)  # In production, this would be a User model
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
            'title': post.title,  # Add title to response
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
    
    # In production, get club_id from authenticated user
    club_id = data.get('club_id', 1)  # Default to first club for demo
    
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
        
        # Determine media type
        media_type = 'image' if filename.lower().endswith(('.png', '.jpg', '.jpeg', '.gif')) else 'video'
        
        return jsonify({
            'success': True,
            'media_url': f'/static/uploads/{filename}',
            'media_type': media_type
        })

@app.route('/api/like/<int:post_id>', methods=['POST'])
def toggle_like(post_id):
    user_id = request.get_json().get('user_id', 'demo_user')  # In production, get from auth
    
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
    user_id = request.get_json().get('user_id', 'demo_user')  # In production, get from auth
    
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

# Initialize database and create sample data
def init_database():
    with app.app_context():
        db.create_all()
        
        # Create sample clubs if none exist
        if Club.query.count() == 0:
            sample_clubs = [
                Club(name='政大電競社', username='@nccu_esports', bio='🎮 熊讚電競列車，帶你進入電競世界！', subscribers=2345),
                Club(name='藝文中心', username='@nccu_arts', bio='🎬 影展x藝術x文化，豐富你的大學生活', subscribers=3456),
                Club(name='商學院學生會', username='@nccu_commerce', bio='💼 連結產學，開拓職涯新視野', subscribers=4567),
                Club(name='永續發展辦公室', username='@nccu_sdgs', bio='🌱 打造永續校園，從你我開始', subscribers=1890),
                Club(name='國際事務處', username='@nccu_global', bio='🌏 拓展國際視野，連結全球脈動', subscribers=2678)
            ]
            
            for club in sample_clubs:
                db.session.add(club)
            
            db.session.commit()
            
            # Create sample posts with real NCCU events
            sample_posts = [
                Post(
                    club_id=1,
                    content="""2025熊讚電競列車 校園講座 政大場
🎮🚂 熊讚電競列車 校園講座 開跑！ 🚂🎮

想知道電競幕後的真實樣貌？想近距離與選手、實況主面對面交流？這次絕對不能錯過！

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

本片由香港導演王家衛監製，為配樂大師顏尼歐莫利克奈（Ennio Morricone）的完整肖像。他是二十世紀最多產、並且最受歡迎的音樂家，曾獲兩座奧斯卡獎、創作出500多首令人難忘的電影配樂。本片透過《新天堂樂園》導演朱賽貝托納多雷對顏尼歐長時間的採訪，以及貝托魯奇、貝洛奇奧、阿基多、奧立佛史東、昆汀塔倫提諾等導演的訪談，佐以許多珍貴錄像、音樂與故地重遊的場景，交織出顏尼歐一生的全貌。

【導演介紹】

朱賽貝·托納多雷 Giuseppe Tornatore

義大利電影導演，生於義大利西西里，1988年的《新天堂樂園》獲坎城影展評審團大獎和奧斯卡最佳外語片獎。1995年39歲時編導的《新天堂星探》，榮獲義大利大衛獎最佳導演獎及威尼斯影展評審團特別獎；1998年編導的史詩巨作《海上鋼琴師》，獲得義大利大衛獎最佳導演獎；2000年44歲編導了《西西里島的美麗傳說》。其中《新天堂樂園》、《海上鋼琴師》和《西西里島的美麗傳說》被合稱為托納多雷的「三部曲」。

濃郁的浪漫主義風格是托納多雷作品的一大特點。托納多雷的影片數量並不多，影片的背景往往是他的故鄉西西里島，題材亦常偏好於少年的夢想或老年的回憶，幾乎每部都是精心錘鍊的作品。 ※導演介紹節錄自維基百科""",
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
🔸2025/09/30 (二)

🔸時間：12:10-13:40

🔸地點：商學院六樓義育廳


講者： 謝富旭 存股助理電子報總編輯

🔸講座內容：

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
                ),
                Post(
                    club_id=4,
                    content="""走進空軍三重一村，見證時藝多媒體的活化再造魔力
文化與產業，如何碰撞出專案價值？

如何保存文化、注入新元素，讓傳統眷村重新活起來呢？

時藝多媒體傳播帶你探索新打卡聖地

✨ 空軍三重一村 ✨

✨ 文化導覽體驗｜理解設計與藝術融合魅力

✨ 實務經驗分享｜第一手跨界行銷專案案例

✨ 職涯啟發交流｜與產業專家面對面對話

你將…

✅ 了解文化保存與空間共創，打造獨特價值

✅ 從跨界行銷實務中，汲取職涯發展的靈感

✅ 建立對「文化與產業趨勢」的前瞻視野

✅ 透過與專業人士交流，找到未來的可能性

👉 把握機會，讓參訪成為一次啟發職涯與思維的全新旅程！

▍活動資訊

👤 講師：林宜標 Bill Lin

📅 日期：9/30 (二)

⏰ 時間：14:00-16:00

📍 地點：新北市三重區正義南路86巷9號

👉 手刀報名 https://pse.is/84mrr2

▍限時加碼

🚕 單趟去程計程車交通補助

🎫 大都會博物館名作展門票＊3抽獎機會

—————————

主辦單位｜國立政治大學學務處職涯發展中心

執行單位｜政大政植涯學生團隊""",
                    media_url='/static/uploads/club_id4.png',
                    media_type='image',
                    event_type='other',
                    event_date=datetime(2025, 9, 30, 14, 0),
                    likes=178,
                    views=650
                ),
                Post(
                    club_id=5,
                    content="""在自我批判與國家意識形態之間：「知乎」網民如何討論中國半導體產業

🌟演講簡介

半導體是中國最受關注的戰略產業之一，近年話題度持續升高。在中國大陸內部，關於半導體的公共討論是什麼樣態？這些討論又透露了哪些社會氛圍與觀點脈絡？


「知乎」作為中國大陸的知識社群平台，提供我們觀察其內部公共討論與意識形態的窗口。本場國關Talk邀請到來自德國的Kristin Shi-Kupfer博士，以「知乎」上的相關討論為案例，分享她的研究與分析。


👩‍🏫 講者介紹

Shi-Kupfer 博士現任德國特里爾大學漢學系教授，並兼任德國智庫 MERICS 資深研究員，研究領域涵蓋中國的數位政治、媒體政策、公民社會與人權議題。她曾在北京從事媒體與研究工作多年，累積深厚田野經驗，中文亦相當流利。此次來臺以外交部臺獎學人身份駐點於政大創新與創造力研究中心，持續推展相關研究。


🪄趕快來報名吧！👉 https://forms.gle/ZzDxFbt26cTErBNf7


⏰ 時間｜2025/10/1（三）12:20–13:50

📍 地點｜國立政治大學 國際關係研究中心 蓄養樓1F 第一會議室

👨‍🏫 講者｜Kristin Shi-Kupfer 博士（德國特里爾大學漢學系教授）

🧑‍💼 主持｜王信賢 主任（政大國關中心）

🗣 語言｜中文主講，Q&A 中英文皆可

🏢主辦單位｜國立政治大學 國際關係研究中心 x 創新與創造力研究中心

✉️聯絡方式｜iirtalk2025@gmail.com 李小姐

 Shi-Kupfer博士中文演講，探討中國內部公共討論與意識形態。📍蓄養樓1F第一會議室""",
                    media_url='/static/uploads/club_id5.png',
                    media_type='image',
                    event_type='workshop',
                    event_date=datetime(2025, 10, 1, 12, 20),
                    likes=92,
                    views=430
                ),
                Post(
                    club_id=1,
                    content="""原青創業工作坊II：全球視野下的合作事業角色
想要創業嗎？有沒有聽過一種創業模式叫「合作事業」。

合作社不僅是一種經濟組織，更是一種以民主治理與平等承擔為核心的社會互動結構。從生產、消費到居住，合作社展現出有別於傳統企業的韌性與包容性。隨著全球化帶來的挑戰與機會，現今更成為實踐永續發展目標（SDGs）、縮減貧窮與不平等的重要途徑。本場工作坊將從全球視野切入，分析各類型合作社的各國在地實踐經驗，為台灣邁進社會團結經濟提供一條啟發與借鏡的光影。

【講座資訊】

時間｜10/1（三） 19:00-21:00

地點｜綜院105教室

講師｜洪敬舒


【講師介紹】

洪敬舒老師為現任台灣勞工陣線協會研究部主任，曾任媒體記者、國會助理、NPO研究&倡議專員，主要關注貧窮勞動、經濟不平等議題。近年更致力於Employee Stock Ownership、Worker Cooperative等企業創新結構。

【承辦人聯絡資訊】

承辦人員｜專任助理 古先生

聯絡電話｜(02)2939-3091#67013

電子信箱｜walisku@nccu.edu.tw

#合作社 #創業 #政大原資中心

#原住民 #青年

#SDGs #ESG""",
                    media_url='/static/uploads/club_id6.png',
                    media_type='image',
                    event_type='workshop',
                    event_date=datetime(2025, 10, 1, 19, 0),
                    likes=156,
                    views=580
                ),
                Post(
                    club_id=2,
                    content="""2025玉山銀行校園商業競賽 校園說明會【政治大學場】

日期：2025年10月2日(四)

時間：12:00-14:00

地點：商學院 玉山廳


玉山銀行致力於透過提供多元、便利的數位金融服務及平台，解決顧客於金融上遇到的大小事，隨時隨地提供如水電般便利的金融服務，同時也希望不斷發覺隱性需求，永遠比顧客多想一步，提供客製化的解決方案滿足顧客所有需求、提升黏著度，更希望藉由校園競賽協助國內外大專院校學生不只是停留在理論層面，而是思考如何將金融科技的應用，落實到實際的場景中，解決客戶的痛點，累積寶貴的實戰經驗。


校園說明會除說明賽制外，將介紹基本提案架構、產品服務介紹以及特色主題說明，以及現場QA。

歡迎各位同學踴躍參加！""",
                    media_url='/static/uploads/club_id7.png',
                    media_type='image',
                    event_type='competition',
                    event_date=datetime(2025, 10, 2, 12, 0),
                    likes=523,
                    views=2800
                ),
                Post(
                    club_id=3,
                    content="""敘利亞難民桌遊工作坊 feat. 國際特赦組織台灣分會
當戰爭爆發，你是一家之主，必須帶領 24 名家族成員逃離家鄉，在穿越邊界之後，面對接踵而至的各種難關，你會如何選擇？

「穿越邊界 Borderlines」是一款全球少數的敘利亞難民主題桌遊，由一名曾在希臘難民營服務三個月的香港志工設計，內容以敘利亞難民的處境為背景，建基於真實數據與經驗。本次工作坊期望參與者透過遊戲中每個關卡與事件，同理難民面臨的各種艱難抉擇，感受到戰爭裡難以預測的突發事件。

難民議題看似離我們很遙遠，但面對如今戰火紛擾的世界，你我都有可能面臨如此的危機。捍衛難民權利不僅是對人性尊嚴的重視，也是對自身安全的保障。就邀請您一起來工作坊體驗及感受吧！

關於講者｜國際特赦組織台灣分會🕯️

國際特赦組織是一個全球的倡議運動，起源於1961年英國律師Peter Benenson聲援葡萄牙兩名「良心犯」。其旨在依循〈世界人權宣言〉與其他聯合國人權公約，藉由獨立的調查研究與積極的倡議行動，試圖阻止並終結任何的人權迫害。

在台灣，早在白色恐怖時期，國際特赦組織就已呼籲國際社會關注台灣的人權狀況。到解嚴後，1994年5月「國際特赦組織台灣分會」正式立案登記。

📅活動時間｜10/02（四）19:00 – 21:00

📍活動地點｜達賢圖書館8F 814討論室""",
                    media_url='/static/uploads/club_id8.png',
                    media_type='image',
                    event_type='workshop',
                    event_date=datetime(2025, 10, 2, 19, 0),
                    likes=267,
                    views=1150
                ),
                Post(
                    club_id=4,
                    content="""社會公義影展《日泰小食》
時間：10/2 (四) 19:10-21:40

地點：藝文中心三樓 視聽館

導演：冼澔楊

*映後座談：主持人 導演 蔡崇隆、導演 冼澔楊

*影片放映結束將舉辦社會公義影展頒獎典禮，《大風之歌》許雅婷導演也將蒞臨。頒獎結束進行演映後座談，特邀蔡崇隆導演擔任主持人與《日泰小食》影片冼澔楊導演對談。


【影片介紹】

​2024 韓國釜山影展 超廣角(Wide Angle) 競賽獲亞洲最佳紀錄片獎BIFF Mecanat Award
2024 台北金馬影展 – 華語首映單元
2025 法國Jean Rouch 民族誌影展 – 主競賽入圍
2025 台北電影獎 – 最佳紀錄片入圍

長洲的日泰小食這個小吃攤，反映了香港多元化的演變。面對 COVID-19 和店主阿丈健康狀況的下滑，這家受人喜愛的小店正面臨關閉，象徵著城市中傳統與現代挑戰之間的掙扎。這間作為當地社群的另一個家的小吃攤，能否在社會變遷之中依然保持日日安泰？

【導演暨導賞人介紹】

冼澔楊 Frankie SIN

1989 年生於香港長洲，畢業於臺灣藝術大學美術研究所。作品關注性別與認同歸屬等議題，《日泰小食》為其首部紀錄長片，入選2024 釜山影展。目前製作中的紀錄片尚有探討同志身分認同的《男孩有點騷》，以及從家族故事出發的《彼岸之島》。


【座談主持人】

蔡崇隆 TSAI, Tsung-Lung

政治大學法律學士，輔仁大學大眾傳播碩士，英國東安格利亞大學（UEA）電影研究。曾任平面媒體記者，商業電視專題記者、公共電視紀錄片製作人及董事。現為中正大學傳播系副教授，獨立紀錄片導演，長期關注人權、環境、多元文化發展等社會議題。

主要導演作品《島國殺人紀事》獲2001年金穗獎最佳紀錄片獎。《奇蹟背後》獲2002年卓越新聞獎最佳專題報導獎。《我的強娜威》入選2004年世界公共電視INPUT影展。《油症─與毒共存》獲2008年南方影展首獎。2015年共同導演的《再見 可愛陌生人》獲桃園電影節桃園市民獎。

近年來亦擔任多部紀錄片製片工作，《失婚記》入圍2012年台北電影節、南方影展及台灣紀錄片雙年展等多項影展。《太陽 不遠》入選2015年日本山形國際影展亞洲新力單元。《徐自強的練習題》獲2016年台北電影節觀眾票選獎及南方影展首獎，並入圍金馬獎最佳紀錄片。最近作品《九槍》獲2022年金馬獎最佳紀錄片。

""",
                    media_url='/static/uploads/club_id9.png',
                    media_type='image',
                    event_type='performance',
                    event_date=datetime(2025, 10, 2, 19, 10),
                    likes=198,
                    views=890
                ),
                Post(
                    club_id=5,
                    content="""人人亞博：舊金山亞洲藝術博物館的歷史、收藏、展覽和教育
🗓️講座時間：2025/10/07(二) 14:00-16:00

📍講座地點：綜院南棟五樓國際會議廳

👨‍🏫講者簡介：許傑博士為美國歷史上首位出任大型藝術博物館館長的華裔人士，致力於增進全球民眾對亞洲藝術與文化的瞭解與欣賞，發揮藝術博物館作為文化交流、文化外交平臺的作用。

🏛️精彩內容：舊金山亞洲藝術博物館是全球著名的亞洲藝術專業博物館，收藏內容廣泛、精彩紛呈，尤以中華文物為主。 這是一座獨特的文化橋樑，在北美地區傳播自古迄今、豐富多彩的亞洲文明，引導觀眾探索和理解亞洲的過去、現在與未來，提升亞洲文化在世界的地位。本講座為大家介紹亞洲藝術博物館的歷史、收藏、展覽和教育專案，並重點講述該館的國際展覽合作及其策展理念。""",
                    media_url='/static/uploads/club_id10.png',
                    media_type='image',
                    event_type='workshop',
                    event_date=datetime(2025, 10, 7, 14, 0),
                    likes=145,
                    views=620
                ),
                Post(
                    club_id=1,
                    content="""藝中影展《櫻桃號》
時間：12/02 (二) 19:10-21:30

地點：藝文中心三樓 視聽館

導演：趙德胤

映後座談主持人：鍾適芳副教授


【影片介紹】

2021年緬甸軍事政變後，拍攝成為敏感動作，趙德胤的長期家鄉拍攝計畫被迫中斷。後續內戰爆發，正值疫情等國際大事發生，外界關注劇降，形同一場閉門殺戮。在內戰一觸即發之時，長年在外的導演，再次回到曾為申請來台護照而待了近半年的仰光小港，望著渡輪往返、乘客來去，此刻焦慮與無望更勝當年，他想起自己首部長片《歸來的人》，跟拍讓他想起兒時的叫賣女孩。家園未來難料，作為離開的人，眼前這片貌似平靜的土地，是他心知回不了的鄉，瀰漫著放不下的愁。

【導演介紹】

 趙德胤 Midi Z

生於緬甸。作品橫跨劇情及紀錄片，曾以《冰毒》、《再見瓦城》、《灼人秘密》提名金馬獎最佳導演，後者亦入選坎城影展一種注目單元，另以《翡翠之城》入選柏林影展，並獲山形紀錄片影展亞洲千波萬波特別獎。近作尚有《十四顆蘋果》、《診所》等。

趙德胤紀錄片新作，少見地親自入鏡旁白傾訴心境，拍片對他已成老僧修行，無須長篇累牘、聲嘶力竭，信手捻來都成內心風景，虛實邊界亦悄然消融，飽含引人玩味的鄉愁餘韻。當歸與離無從自主，命定漂泊的人，視野隨舟浮沉遠近，唯有手中攝影機是岸。

【座談主持人】

鍾適芳 CHUNG Shefong

政大傳播學院副教授、泰國朱拉隆功大學國際策展學程客席講師兼課程顧問。
離散、身份認同為其長期關注的議題，亦是創作與策展的核心。透過國際展演計畫，積極串連國際音樂家、藝術家、導演及學界。

""",
                    media_url='/static/uploads/club_id11.png',
                    media_type='image',
                    event_type='performance',
                    event_date=datetime(2025, 12, 2, 19, 10),
                    likes=312,
                    views=1420
                ),
                Post(
                    club_id=2,
                    content="""2025 經濟黑客松跨國競賽｜報名開跑
💭 想聽聽國外同學們的經濟觀點嗎？

💭 想將所學知識推向國際舞台、在國際競賽中一展長才嗎？

那你絕對要把握這次難得的機會！

🔥 Borderless Hackonomics 2025 報名開跑啦 🔥

本競賽是由政治大學與英國、澳洲共四所大學聯合主辦的經濟議題競賽，提供同學們跨國交流經濟觀點的機會 🙌

本次參賽學校包含：

🔹 National Chengchi University, Taiwan

🔹 University of Queensland, Australia

🔹 King's College London, United Kingdom

🔹 University of Exeter, United Kingdom

參加競賽你將可以：

🔹 精進團隊合作、議題分析與溝通表達能力

🔹 拓展視野、聆聽國外同學的經濟觀點

🔹 獲得國際競賽經驗，讓履歷脫穎而出

🔹 結識同樣對經濟議題充滿熱忱的朋友

📌 競賽獎項

台灣初賽：

🥇 第一名｜10,000 元及獎狀

🥈 第二名｜6,000 元及獎狀

🥉 第三名｜4,000 元及獎狀

全球決賽：冠軍獎品及獎狀

📌 報名資格

🔹 政治大學在學學生

🔹 已修習或正在修習經濟學課程者

📌 重要資訊

👉🏻 每隊二至四人，歡迎同學們踴躍組隊參加！

👉🏻 競賽主題：經濟學相關議題，將於開幕大會公布

⏰ 重要時程

報名期間：9/19（五）至 10/3（五）23:59

線上開幕大會：10/10（五）18:00

台灣初賽：10/10（五）至10/12（日）

初賽前三名公布：10/13（一）

線上全球決賽大會：10/15（三）18:00

還在等甚麼，馬上點擊連結報名，豐富你的履歷和大學生活吧！

🔎 官方網頁（內有競賽詳細資訊）

https://niurl.cc/Nhr1rz""",
                    media_url='/static/uploads/club_id12.png',
                    media_type='image',
                    event_type='competition',
                    event_date=datetime(2025, 10, 10, 18, 0),
                    likes=678,
                    views=3200
                ),
                Post(
                    club_id=3,
                    content="""校園餐盒減廢徵案競賽
每天的外食與外帶，正讓校園累積大量一次性餐盒垃圾。雖然政大持續推動永續發展，但校園內仍缺乏完善的循環餐盒機制，減廢行動亟需更多創新解方。

為了集結師生的創意與行動力，永續發展辦公室舉辦 「政大校園餐盒減廢徵案競賽」，徵求具創意、可行性高、並能落地執行的減廢方案。優勝隊伍除了獲得獎金，更有機會讓點子在校園中實際實現，為政大打造更綠色的飲食環境。

參賽對象

政大全體教職員工與在學生
可自由組隊（建議 2–5 人，可跨院系所單位）
徵案主題

目前政大校內推動校內一次性餐盒減廢遇到以下困境：

校園部分餐飲業者因寒暑假來客量不穩，營運成本較高，未能設置內用容器清洗設備與人力，多以免洗餐具供應。
與外部循環餐盒廠商合作：
市面上有許多提供循環餐盒的外送業者，惟本校位處交通銜接不易之區段，加上廠商設有最低外送量限制，許多小型會議或活動難以達到外送門檻，降低使用彈性。
現行循環餐盒租借費用，可能導致便當價格超出可接受預算。
本次餐盒減廢徵案競賽徵求協助克服上述困境，並有機會實質輔助減廢之創新方案，包括但不限於提高減廢誘因的消費者行為改變計畫、校園周遭小區域的循環餐盒租借機制、推廣媒合循環餐盒資訊…或者其他校園餐飲減廢上可以著力的地方等，都歡迎提出創新的解決方案。

競賽流程

報名與提案繳交：即日起至 11/10(一) 17:00
書面審查結果公告：11/14(五)，於永續政大官網公告
決賽簡報評選：11/20(四)
得獎名單公告：另行通知
獎勵辦法

第一名｜獎金 10,000 元
第二名｜獎金 8,000 元
第三名｜獎金 6,000 元
優選 ｜獎金 4,000 元
 獲選方案有機會在校園中試行與推廣！
聯絡窗口

政治大學永續發展辦公室
簡婉庭 (02)2939-3091 #66048""",
                    media_url='/static/uploads/club_id13.png',
                    media_type='image',
                    event_type='competition',
                    event_date=datetime(2025, 11, 20, 14, 0),
                    likes=234,
                    views=980
                )
            ]
            
            for post in sample_posts:
                db.session.add(post)
            
            db.session.commit()
            print("Database initialized with sample data!")

if __name__ == '__main__':
    init_database()  # Initialize the database before running
    app.run(debug=True)