"""Optional sanity filter. Off unless the config says so AND the API key is set.

The filter can veto a paper trade. It cannot approve one the model did not
already propose, and it never places an order. A transport failure vetoes that
attempt only (fail closed for the run) and does not stick, so the next run retries.
A real veto sticks on the trade row.
"""
import json
import os
import urllib.request

from .http_json import UA


class Decision:
    def __init__(self, veto, reason, definitive, enabled=True):
        self.veto = bool(veto)
        self.reason = reason
        self.definitive = bool(definitive)
        self.enabled = bool(enabled)

    def as_dict(self):
        return {'enabled': self.enabled, 'veto': self.veto, 'reason': self.reason, 'definitive': self.definitive}


OFF = Decision(False, 'filter off', False, enabled=False)


class LlmFilter:
    def __init__(self, cfg, env=None, post=None):
        block = cfg.get('llm_filter') or {}
        self.enabled_flag = bool(block.get('enabled'))
        self.env_key = block.get('env_key') or 'PAPER_BOT_LLM_API_KEY'
        env = env if env is not None else os.environ
        self.api_key = (env.get(self.env_key) or '').strip()
        self.url = block.get('url') or 'https://api.openai.com/v1/chat/completions'
        self.model = block.get('model') or 'gpt-4o-mini'
        self.max_calls = int(block.get('max_calls') or 20)
        self.calls = 0
        self.post = post  # test hook: post(url, headers, body) -> parsed json
        self.active = self.enabled_flag and bool(self.api_key)

    def status_note(self):
        if not self.enabled_flag:
            return 'llm filter off'
        if not self.api_key:
            return f'llm filter enabled in config but {self.env_key} is unset; trades are vetoed until a key is set'
        return f'llm filter on ({self.model})'

    def review(self, proposal):
        if not self.enabled_flag:
            return Decision(False, 'filter off', False, enabled=False)
        if not self.api_key:
            return Decision(True, f'filter is on but {self.env_key} is unset', True)
        if self.calls >= self.max_calls:
            return Decision(True, 'llm call cap for this run', False)
        self.calls += 1
        try:
            raw = self._call(proposal)
            return self._parse(raw)
        except Exception as e:
            return Decision(True, 'filter error: ' + str(e)[:300], False)

    def _call(self, proposal):
        body = _request_body(self.url, self.model, proposal)
        if self.post:
            return self.post(self.url, self.api_key, body)
        data = json.dumps(body).encode('utf-8')
        headers = dict(UA)
        headers['Content-Type'] = 'application/json'
        if 'anthropic.com' in self.url:
            headers['x-api-key'] = self.api_key
            headers['anthropic-version'] = '2023-06-01'
        else:
            headers['Authorization'] = 'Bearer ' + self.api_key
        req = urllib.request.Request(self.url, data=data, headers=headers, method='POST')
        with urllib.request.urlopen(req, timeout=20) as r:
            return json.loads(r.read().decode('utf-8'))

    def _parse(self, raw):
        text = _message_text(raw)
        parsed = _json_object(text)
        if not isinstance(parsed, dict) or not isinstance(parsed.get('veto'), bool):
            return Decision(True, 'filter returned an unreadable answer', False)
        reason = str(parsed.get('reason') or '').strip()[:500] or ('veto' if parsed['veto'] else 'allow')
        return Decision(parsed['veto'], reason, True)


def _request_body(url, model, proposal):
    prompt = (
        'You are a sanity check on a paper trade, not the source of the edge. '
        'Veto only for a concrete reason: a reported injury or lineup change, a news item '
        'the price is unlikely to reflect yet, a line that is stale against the widely reported number, '
        'or this market not being the game it looks like. Otherwise allow it. '
        'Reply with JSON only: {"veto": true or false, "reason": "one sentence"}.\n\n'
        + json.dumps({
            'source': proposal.get('source'),
            'game': proposal.get('game'),
            'title': proposal.get('title'),
            'side': proposal.get('side'),
            'strike': proposal.get('strike'),
            'model_prob': proposal.get('model_prob'),
            'ask': proposal.get('price'),
            'edge': proposal.get('edge'),
            'detail': proposal.get('detail'),
        }, default=str)
    )
    if 'anthropic.com' in url:
        return {'model': model, 'max_tokens': 200, 'messages': [{'role': 'user', 'content': prompt}]}
    return {'model': model, 'temperature': 0, 'messages': [{'role': 'user', 'content': prompt}]}


def _message_text(raw):
    if not isinstance(raw, dict):
        return str(raw)
    if isinstance(raw.get('content'), list):
        return ''.join(part.get('text', '') for part in raw['content'] if isinstance(part, dict))
    choices = raw.get('choices') or []
    if choices:
        return ((choices[0].get('message') or {}).get('content')) or ''
    return ''


def _json_object(text):
    s = (text or '').strip()
    if s.startswith('```'):
        s = s.strip('`')
        s = s.split('\n', 1)[-1]
        if s.endswith('```'):
            s = s[:-3]
    start, end = s.find('{'), s.rfind('}')
    if start < 0 or end <= start:
        return None
    try:
        return json.loads(s[start:end + 1])
    except json.JSONDecodeError:
        return None
