"""Authenticated feature ingestion with a persistent, separate e-mail outbox."""
import asyncio
from contextlib import asynccontextmanager
from datetime import timezone
import json
import logging
import os
from secrets import compare_digest
import sqlite3
from typing import Annotated, Literal
from urllib.parse import urlsplit

import requests
from dotenv import load_dotenv
from fastapi import FastAPI, Header, HTTPException, Request
from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, ValidationError

from utils import live_store, vibration

load_dotenv(vibration.MODEL.parents[1] / '.env', override=False)


class Event(BaseModel):
    model_config = ConfigDict(extra='forbid')
    event_id: Annotated[str, Field(pattern=r'^[A-Za-z0-9_.:-]{1,96}$')]
    sensor_id: Annotated[str, Field(pattern=r'^[A-Za-z0-9_.:-]{1,64}$')]
    measured_at: AwareDatetime
    scale: Literal['linear', 'log10']
    features: dict[str, float]


def delivery_settings():
    url, token = os.getenv('N8N_WEBHOOK_URL', '').strip(), os.getenv('N8N_WEBHOOK_TOKEN', '').strip()
    if not (url or token):
        return None
    parts = urlsplit(url)
    local = parts.hostname in ('localhost', '127.0.0.1', '::1')
    if (len(token) < 24 or not parts.hostname or parts.username or parts.password or parts.fragment
            or (parts.scheme != 'https' and not (local and parts.scheme == 'http'))
            or '/webhook/' not in parts.path):
        raise RuntimeError('n8n 운영 웹훅 URL과 24자 이상의 인증 토큰 설정을 확인하세요.')
    return url, token


def dispatch(settings):
    event = live_store.claim()
    if not event:
        return False
    event_id = event['event_id']
    body = {key: event[key] for key in ('event_id', 'sensor_id', 'measured_at', 'received_at',
                                       'score', 'threshold', 'anomaly', 'anomaly_type',
                                       'type_probability', 'model_version')}
    body['replay'] = event_id.startswith('mat-replay-') and event['sensor_id'].startswith('REPLAY-')
    try:
        url, token = settings
        res = requests.post(url, json=body, headers={'X-Pipeguard-Token': token},
                            timeout=(3, 20), allow_redirects=False)
        if not 200 <= res.status_code < 300:
            state, detail = 'failed', f'HTTP {res.status_code} · n8n 실행 이력을 확인하세요.'
        else:
            ack = res.json()
            if isinstance(ack, dict) and ack.get('sent') is True and ack.get('event_id') == event_id:
                state, detail = 'sent', ''
            else:
                state, detail = 'uncertain', '일치하는 SMTP 발송 응답이 없습니다.'
    except requests.RequestException:
        state, detail = 'uncertain', '연결 오류, 응답 지연 또는 잘못된 응답 · n8n 로그를 확인하세요.'
    except ValueError:
        state, detail = 'uncertain', '응답 형식이 올바르지 않습니다.'
    live_store.finish(event_id, state, detail)
    return True


async def worker(settings, stop):
    while not stop.is_set():
        try:
            handled = await asyncio.to_thread(dispatch, settings)
        except sqlite3.Error:
            logging.getLogger(__name__).warning('알림 큐 데이터베이스에 접근하지 못했습니다.')
            handled = False
        if not handled:
            try:
                await asyncio.wait_for(stop.wait(), timeout=1)
            except TimeoutError:
                pass


@asynccontextmanager
async def lifespan(app):
    app.state.token = os.getenv('PIPEGUARD_API_TOKEN', '').strip()
    if len(app.state.token) < 24:
        raise RuntimeError('PIPEGUARD_API_TOKEN을 24자 이상으로 설정하세요.')
    app.state.delivery = delivery_settings()
    app.state.cooldown = int(os.getenv('PIPEGUARD_COOLDOWN_SECONDS', '300'))
    if not 0 <= app.state.cooldown <= 86400:
        raise RuntimeError('알림 재전송 제한은 0~86400초 사이여야 합니다.')
    vibration.load()
    live_store.setup()
    with live_store.db() as con:
        con.execute("UPDATE events SET delivery='uncertain', detail='발송 중 서버 재시작' WHERE delivery='sending'")
    stop = asyncio.Event()
    task = asyncio.create_task(worker(app.state.delivery, stop)) if app.state.delivery else None
    try:
        yield
    finally:
        stop.set()
        if task:
            await task


app = FastAPI(title='PIPEGUARD Live', lifespan=lifespan)


@app.get('/health')
def health():
    return {'model': vibration.load()['version'], 'email_enabled': bool(app.state.delivery)}


@app.post('/v1/events')
async def ingest(request: Request, authorization: Annotated[str | None, Header()] = None):
    target = ('Bearer ' + app.state.token).encode()
    if not authorization or not compare_digest(authorization.encode(), target):
        raise HTTPException(401, '센서 인증 토큰을 확인하세요.')
    data = bytearray()
    async for chunk in request.stream():
        if len(data) + len(chunk) > 16_384:
            raise HTTPException(413, '요청은 16KB까지 허용합니다.')
        data.extend(chunk)
    try:
        raw = json.loads(data)
        if (not isinstance(raw, dict) or not isinstance(raw.get('features'), dict)
                or any(type(v) not in (float, int) for v in raw['features'].values())
                or not isinstance(raw.get('measured_at'), str)):
            raise ValueError('측정 시각은 시간대가 있는 문자열, 특징은 JSON 숫자로 보내 주세요.')
        event = Event.model_validate(raw)
        payload = event.model_dump(mode='json')
        payload['measured_at'] = event.measured_at.astimezone(timezone.utc).isoformat()
        return await asyncio.to_thread(process, payload)
    except FileExistsError as exc:
        raise HTTPException(409, str(exc)) from None
    except (ValidationError, json.JSONDecodeError, UnicodeError, OverflowError):
        raise HTTPException(422, '요청 형식과 유한한 숫자 여부를 확인하세요.') from None
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from None


def process(payload):
    result = vibration.infer(payload['features'], payload['scale'])
    saved, duplicate = live_store.store(payload, result, bool(app.state.delivery), app.state.cooldown)
    return {**saved, 'duplicate': duplicate}
