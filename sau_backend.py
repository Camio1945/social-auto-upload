"""WebUI 后端入口：注册各业务接口并托管前端静态资源。"""
import os

from flask import Flask, send_from_directory
from flask_cors import CORS

from myUtils.account_api import account_bp
from myUtils.comment_api import comment_bp
from myUtils.keepalive import start_scheduler
from myUtils.keepalive_api import keepalive_bp
from myUtils.material_api import material_bp
from myUtils.publish_api import publish_bp
from myUtils.user_name_api import user_name_bp

app = Flask(__name__)

# 允许所有来源跨域访问
CORS(app)

# 限制上传文件大小为160MB
app.config['MAX_CONTENT_LENGTH'] = 160 * 1024 * 1024

# 名称管理、素材、账号、发布/登录、评论接口
app.register_blueprint(user_name_bp)
app.register_blueprint(material_bp)
app.register_blueprint(account_bp)
app.register_blueprint(publish_bp)
app.register_blueprint(comment_bp)
app.register_blueprint(keepalive_bp)

# 视频号登录态保活调度（后台线程，按配置的间隔执行）
start_scheduler()

# 获取当前目录（假设 index.html 和 assets 在这里）
current_dir = os.path.dirname(os.path.abspath(__file__))


# 处理所有静态资源请求（未来打包用）
@app.route('/assets/<filename>')
def custom_static(filename):
    return send_from_directory(os.path.join(current_dir, 'assets'), filename)


# 处理 favicon.ico 静态资源（未来打包用）
@app.route('/favicon.ico')
def favicon():
    return send_from_directory(os.path.join(current_dir, 'assets'), 'vite.svg')


@app.route('/vite.svg')
def vite_svg():
    return send_from_directory(os.path.join(current_dir, 'assets'), 'vite.svg')


# （未来打包用）
@app.route('/')
def index():
    return send_from_directory(current_dir, 'index.html')


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5409)
