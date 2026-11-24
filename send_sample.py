"""Submit one explicit local smoke-test event; anomaly may send a real e-mail."""
import argparse
from datetime import datetime, timezone
import os
from uuid import uuid4

from dotenv import load_dotenv
import requests

from utils import vibration


def main():
    parser = argparse.ArgumentParser(description='로컬 수신 API에 샘플 1건 전송 (기본: 정상)')
    parser.add_argument('--anomaly', action='store_true', help='이상 샘플을 전송해 실제 이메일을 유발할 수 있습니다.')
    args = parser.parse_args()
    load_dotenv(vibration.MODEL.parents[1] / '.env', override=False)
    token = os.getenv('PIPEGUARD_API_TOKEN', '').strip()
    if len(token) < 24:
        parser.exit(1, 'PIPEGUARD_API_TOKEN을 설정하세요.\n')
    event = dict(event_id='smoke-' + uuid4().hex, sensor_id='SMOKE-TEST',
                 measured_at=datetime.now(timezone.utc).isoformat(), scale='linear',
                 features=list(vibration.demo_rows())[2 if args.anomaly else 0])
    try:
        reply = requests.post('http://127.0.0.1:8000/v1/events', json=event,
                              headers={'Authorization': 'Bearer ' + token}, timeout=10,
                              allow_redirects=False)
        print(reply.text)
        reply.raise_for_status()
    except requests.RequestException as exc:
        parser.exit(1, f'로컬 API 응답 실패: {type(exc).__name__}\n')


if __name__ == '__main__':
    main()
