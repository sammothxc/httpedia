from flask import Flask, request
import subprocess
import hmac
import hashlib
import os

app = Flask(__name__)

WEBHOOK_SECRET = os.environ.get('WEBHOOK_SECRET', 'change-me')
REPO_PATH = './'
SERVICE_NAME = 'httpedia'

@app.route('/webhook', methods=['POST'])
def webhook():
    signature = request.headers.get('X-Hub-Signature-256')
    if not signature:
        return 'No signature', 403

    payload = request.get_data()
    expected = 'sha256=' + hmac.new(
        WEBHOOK_SECRET.encode(),
        payload,
        hashlib.sha256
    ).hexdigest()

    if not hmac.compare_digest(signature, expected):
        return 'Invalid signature', 403

    subprocess.run(['git', 'fetch', 'origin', 'main'], cwd=REPO_PATH)
    result = subprocess.run(
        ['git', 'reset', '--hard', 'origin/main'],
        cwd=REPO_PATH,
        capture_output=True,
        text=True
    )

    if result.returncode != 0:
        return f'Git reset failed: {result.stderr}', 500

    pip_result = subprocess.run(
        ['pip', 'install', '-r', 'requirements.txt', '--break-system-packages'],
        cwd=REPO_PATH,
        capture_output=True,
        text=True
    )

    if pip_result.returncode != 0:
        return f'Pip install failed: {pip_result.stderr}', 500


    subprocess.run(['systemctl', 'restart', SERVICE_NAME])
    return 'OK', 200

@app.route('/health')
def health():
    return 'OK', 200

if __name__ == '__main__':
    port = int(os.environ.get('WEBHOOK_PORT', 'change-me'))
    app.run(host='0.0.0.0', port=port)