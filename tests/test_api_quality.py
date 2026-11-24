"""HTTP interface tests for defects, quality summary and conversations (no LLM calls)."""
from __future__ import annotations

import pytest
from sqlalchemy import func, select

from app.models import ChatMessage


# --------------------------------------------------------------------------- #
# /api/defects + /api/quality-summary
# --------------------------------------------------------------------------- #
def create_defect(client, **overrides):
    payload = {'title': '缺陷标题', 'steps': '1. 打开行程页 2. 点击保存',
               'expected': '保存成功', 'actual': '页面无响应', 'severity': 'major'}
    payload.update(overrides)
    return client.post('/api/defects', json=payload)


def test_create_defect_returns_201_and_open_status(client):
    response = create_defect(client)

    assert response.status_code == 201
    body = response.json()
    assert isinstance(body['id'], int)
    assert body['status'] == 'open'
    assert body['severity'] == 'major'
    assert body['created_at'].endswith('+00:00')


@pytest.mark.parametrize('overrides', [
    {'severity': 'blocker'},
    {'title': 'x'},
    {'steps': ''},
    {'expected': ''},
    {'unexpected': 1},
])
def test_create_defect_rejects_invalid_payload(client, overrides):
    assert create_defect(client, **overrides).status_code == 422


def test_patch_defect_status(client):
    defect_id = create_defect(client).json()['id']

    response = client.patch(f'/api/defects/{defect_id}', json={'status': 'fixed'})

    assert response.status_code == 200
    assert response.json()['status'] == 'fixed'
    assert client.get('/api/defects').json()['defects'][0]['status'] == 'fixed'


def test_patch_defect_rejects_invalid_status(client):
    defect_id = create_defect(client).json()['id']

    assert client.patch(f'/api/defects/{defect_id}', json={'status': 'done'}).status_code == 422


def test_patch_missing_defect_returns_404(client):
    assert client.patch('/api/defects/999999', json={'status': 'fixed'}).status_code == 404


def test_quality_summary_counts_match_defects(client):
    first = create_defect(client, title='缺陷一', severity='major').json()
    second = create_defect(client, title='缺陷二', severity='minor').json()
    assert client.patch(f'/api/defects/{second["id"]}', json={'status': 'fixed'}).status_code == 200

    summary = client.get('/api/quality-summary').json()

    assert summary['total_defects'] == 2
    assert summary['by_status'] == {'open': 1, 'fixed': 1, 'verified': 0, 'wontfix': 0}
    assert summary['by_severity'] == {'critical': 0, 'major': 1, 'minor': 1, 'suggestion': 0}
    assert first['status'] == 'open'
    assert summary['warning']


# --------------------------------------------------------------------------- #
# /api/conversations
# --------------------------------------------------------------------------- #
def test_create_conversation_uses_configured_default_model(client):
    default_model = client.get('/api/models').json()['default']

    response = client.post('/api/conversations', json={})

    assert response.status_code == 201
    body = response.json()
    assert body['model'] == default_model
    assert body['title'] == '新对话'
    assert body['created_at'].endswith('+00:00')


def test_create_conversation_accepts_allowed_model(client):
    allowed = client.get('/api/models').json()['models'][-1]['id']

    response = client.post('/api/conversations', json={'title': '指定模型', 'model': allowed})

    assert response.status_code == 201
    assert response.json()['model'] == allowed


def test_create_conversation_rejects_unknown_model(client):
    response = client.post('/api/conversations', json={'model': 'gpt-4o'})

    assert response.status_code == 422
    assert '模型只支持' in response.json()['detail']


def test_create_conversation_rejects_extra_fields(client):
    """回归：CreateConversation 使用 extra='forbid'，多余字段必须 422。"""
    response = client.post('/api/conversations', json={'title': 'x', 'unexpected': 1})

    assert response.status_code == 422
    detail = response.json()['detail']
    assert detail[0]['type'] == 'extra_forbidden'
    assert detail[0]['loc'] == ['body', 'unexpected']


def test_conversation_timestamps_are_utc_in_post_and_list(client):
    """回归：POST 与 GET 列表里的 created_at 都应带 +00:00 且一致。"""
    created = client.post('/api/conversations', json={'title': '时间戳'}).json()
    assert created['created_at'].endswith('+00:00')

    listed = client.get('/api/conversations').json()['conversations']
    matched = [row for row in listed if row['id'] == created['id']]

    assert len(matched) == 1
    assert matched[0]['created_at'] == created['created_at']
    assert matched[0]['created_at'].endswith('+00:00')


def test_get_conversation_returns_empty_message_list(client):
    conversation_id = client.post('/api/conversations', json={'title': '空对话'}).json()['id']

    response = client.get(f'/api/conversations/{conversation_id}')

    assert response.status_code == 200
    assert response.json()['messages'] == []


def test_get_missing_conversation_returns_404(client):
    assert client.get('/api/conversations/does-not-exist').status_code == 404


def test_delete_conversation_returns_200_and_then_404(client):
    conversation_id = client.post('/api/conversations', json={'title': '待删除'}).json()['id']

    response = client.delete(f'/api/conversations/{conversation_id}')

    assert response.status_code == 200
    assert response.json() == {'deleted': True}
    assert client.get(f'/api/conversations/{conversation_id}').status_code == 404


def test_delete_missing_conversation_returns_404(client):
    assert client.delete('/api/conversations/does-not-exist').status_code == 404


def test_delete_conversation_cascades_to_messages(client, session_factory):
    conversation_id = client.post('/api/conversations', json={'title': '级联删除'}).json()['id']
    with session_factory.begin() as db:
        db.add_all([
            ChatMessage(id='msg-1', conversation_id=conversation_id, role='user',
                        content='你好', meta_json='{}'),
            ChatMessage(id='msg-2', conversation_id=conversation_id, role='assistant',
                        content='您好', meta_json='{}'),
        ])
    with session_factory() as db:
        assert db.scalar(select(func.count(ChatMessage.id))) == 2

    assert client.delete(f'/api/conversations/{conversation_id}').status_code == 200

    with session_factory() as db:
        assert db.scalar(select(func.count(ChatMessage.id))) == 0
