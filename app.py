from flask import Flask, render_template, request, redirect, url_for, flash
from flask_login import LoginManager, login_user, login_required, logout_user, current_user
from models import db, Itinerary, User
from datetime import datetime, date, timedelta
import requests
from openai import OpenAI

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///app.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SECRET_KEY'] = 'asdhjaslfhalsdkdhf_fajskfasf231854'  # 建议生产时换强密钥

db.init_app(app)

# 货币列表
CURRENCIES = [
    ('USD', '美元 (USD)'),
    ('EUR', '欧元 (EUR)'),
    ('CNY', '人民币 (CNY)'),
    ('JPY', '日元 (JPY)'),
    ('GBP', '英镑 (GBP)'),
    ('AUD', '澳元 (AUD)'),
    ('CAD', '加元 (CAD)'),
    ('CHF', '瑞士法郎 (CHF)'),
    ('HKD', '港元 (HKD)'),
    ('SGD', '新加坡元 (SGD)'),
]

# Flask-Login
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

with app.app_context():
    db.create_all()

# 货币 API
API_KEY = '1f6dc4a20ec2a5298027c9cc'
API_URL = f'https://v6.exchangerate-api.com/v6/{API_KEY}/latest/{{}}'

# SiliconFlow API
client = OpenAI(
    api_key='sk-jtrrmyodktxnyjsvcgzoxeqsboopchrtorehuqxvhgnznvmm',
    base_url='https://api.siliconflow.cn/v1'
)

@app.route('/')
@login_required
def index():
    itineraries = Itinerary.query.filter_by(user_id=current_user.id).all()
    UNSPLASH_ACCESS_KEY = '2xfBrrlSfHtIKwwCeibEvGS55gzNQIE1DKb1mcwtrGA'  # 您的 key
    for itinerary in itineraries:
        if not hasattr(itinerary, 'cover_image') or not itinerary.cover_image:
            query = f"{itinerary.destination} travel landmark"
            url = f"https://api.unsplash.com/search/photos?query={query}&per_page=1&client_id={UNSPLASH_ACCESS_KEY}"
            try:
                resp = requests.get(url, timeout=5).json()
                if resp.get('results'):
                    itinerary.cover_image = resp['results'][0]['urls']['regular']
                else:
                    itinerary.cover_image = None
            except:
                itinerary.cover_image = None
    return render_template('index.html', itineraries=itineraries)

@app.route('/create', methods=['GET', 'POST'])
@login_required
def create():
    if request.method == 'POST':
        title = request.form['title']
        destination = request.form['destination']
        start_date = datetime.strptime(request.form['start_date'], '%Y-%m-%d')
        end_date = datetime.strptime(request.form['end_date'], '%Y-%m-%d')
        notes = request.form['notes']

        new_itinerary = Itinerary(
            title=title, destination=destination,
            start_date=start_date, end_date=end_date,
            notes=notes, user_id=current_user.id
        )
        db.session.add(new_itinerary)
        db.session.commit()
        flash('行程创建成功！', 'success')
        return redirect(url_for('index'))
    return render_template('create.html')

@app.route('/edit/<int:id>', methods=['GET', 'POST'])
@login_required
def edit(id):
    itinerary = Itinerary.query.get_or_404(id)
    if itinerary.user_id != current_user.id:
        flash('无权限访问', 'error')
        return redirect(url_for('index'))

    if request.method == 'POST':
        title = request.form.get('title')
        destination = request.form.get('destination')
        start_date_str = request.form.get('start_date')
        end_date_str = request.form.get('end_date')
        notes = request.form.get('notes', '')

        if not all([title, destination, start_date_str, end_date_str]):
            flash('请填写所有必填字段', 'error')
            return render_template('edit.html', itinerary=itinerary)

        try:
            start_date = datetime.strptime(start_date_str, '%Y-%m-%d')
            end_date = datetime.strptime(end_date_str, '%Y-%m-%d')
            if start_date > end_date:
                flash('开始日期不能晚于结束日期', 'error')
                return render_template('edit.html', itinerary=itinerary)
        except ValueError:
            flash('日期格式错误', 'error')
            return render_template('edit.html', itinerary=itinerary)

        itinerary.title = title.strip()
        itinerary.destination = destination.strip()
        itinerary.start_date = start_date
        itinerary.end_date = end_date
        itinerary.notes = notes.strip() or None

        db.session.commit()
        flash('行程更新成功！', 'success')
        return redirect(url_for('index'))

    return render_template('edit.html', itinerary=itinerary)

@app.route('/delete/<int:id>')
@login_required
def delete(id):
    itinerary = Itinerary.query.get_or_404(id)
    if itinerary.user_id != current_user.id:
        flash('无权限访问', 'error')
        return redirect(url_for('index'))
    db.session.delete(itinerary)
    db.session.commit()
    flash('行程已删除', 'success')
    return redirect(url_for('index'))

@app.route('/detail/<int:id>')
@login_required
def detail(id):
    itinerary = Itinerary.query.get_or_404(id)
    if itinerary.user_id != current_user.id:
        flash('无权限访问', 'error')
        return redirect(url_for('index'))

    guide = "<p style='color: blue;'>🤖 AI 正在生成旅行指南，请稍等 5-20 秒...</p>"

    try:
        prompt = f"""
你是一个专业的旅行规划师，为目的地 "{itinerary.destination}" 生成一份简洁实用的旅行指南。

用户行程日期：{itinerary.start_date} 到 {itinerary.end_date}
用户个人笔记：{itinerary.notes or '无'}

请用中文、Markdown 格式输出，内容精炼，只包含：
- 🏛️ 必去景点（5-8个，附简短理由）
- 🍜 特色美食推荐
- 🚇 交通建议
- 🏨 住宿推荐
- ⚠️ 注意事项
- 📅 行程建议（结合日期和笔记）

重点参考用户笔记，使建议个性化。
"""

        response = client.chat.completions.create(
            model="deepseek-ai/DeepSeek-V3",  # 2025年12月当前可用主力模型
            messages=[{"role": "user", "content": prompt.strip()}],
            timeout=60
        )
        guide = response.choices[0].message.content
    except Exception as e:
        guide = f"<p style='color:red;'>⚠️ AI 生成失败：{str(e)}</p>"

    return render_template('detail.html', itinerary=itinerary, guide=guide)

@app.route('/currency', methods=['GET', 'POST'])
def currency():
    result = None
    chart_data = None
    
    if request.method == 'POST':
        from_currency = request.form['from_currency']
        to_currency = request.form['to_currency']
        amount = float(request.form.get('amount', 1))

        # 当前汇率
        response = requests.get(API_URL.format(from_currency))
        data = response.json()
        if data.get('result') == 'success':
            rate = data['conversion_rates'].get(to_currency)
            if rate:
                result = round(amount * rate, 2)

        # 历史趋势（免费 exchangerate.host）
        end_date = date.today()
        start_date = end_date - timedelta(days=30)
        history_url = f"https://api.exchangerate.host/timeseries?start_date={start_date}&end_date={end_date}&base={from_currency}&symbols={to_currency}&access_key=5fd91e687dc75913f66f04dca9634caa"
        history = requests.get(history_url).json()
        print("History API response:", history)
        if history.get('success'):
            dates = []
            rates = []
            for d, r_dict in sorted(history['rates'].items()):
                dates.append(d)
                rates.append(r_dict[to_currency])
            chart_data = {'dates': dates, 'rates': rates}
            print("Chart data:", chart_data)

    return render_template('currency.html', currencies=CURRENCIES, result=result, chart_data=chart_data)

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        if User.query.filter_by(username=username).first():
            flash('用户名已存在')
            return redirect(url_for('register'))
        user = User(username=username)
        user.set_password(password)
        db.session.add(user)
        db.session.commit()
        flash('注册成功，请登录')
        return redirect(url_for('login'))
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        user = User.query.filter_by(username=username).first()
        if user and user.check_password(password):
            login_user(user)
            return redirect(url_for('index'))
        flash('用户名或密码错误')
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))

if __name__ == '__main__':
    app.run(debug=True)