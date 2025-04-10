from flask import Flask, request, jsonify
from dotenv import load_dotenv
import os
from controllers.images import generate_images
import time

# 加载环境变量
load_dotenv()

app = Flask(__name__)

@app.route('/v1/images/generations', methods=['POST'])
def generate_image():
    try:
        # 获取请求数据
        data = request.get_json()
        
        # 获取sessionid
        auth_header = request.headers.get('Authorization')
        if not auth_header or not auth_header.startswith('Bearer '):
            return jsonify({'error': 'Missing or invalid Authorization header'}), 401
            
        sessionid = auth_header.split(' ')[1]
        
        # 调用生成函数
        result = generate_images(
            model=data.get('model', 'jimeng-3.0'),
            prompt=data.get('prompt'),
            width=data.get('width', 1024),
            height=data.get('height', 1024),
            sample_strength=data.get('sample_strength', 0.5),
            negative_prompt=data.get('negativePrompt', ''),
            refresh_token=sessionid
        )
        
        return jsonify({
            'created': int(time.time()),
            'data': [{'url': url} for url in result]
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8000, debug=True) 