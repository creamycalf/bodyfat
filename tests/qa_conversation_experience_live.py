"""Live conversational acceptance with fictional facts and temporary storage.

The caller supplies the existing model environment. This script never reads a
key, exports configuration, or opens the application's real health storage.
"""
import argparse
import json
import os
from pathlib import Path
import re
import sys
import tempfile
import time


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT/'tmp/conversation-experience-live-0.4.29.json'
FICTIONAL_STATE = ROOT/'tmp/conversation-experience-live-0.4.29-fictional-state.json'
CONVERSATION_ID = 'conversation-experience-fictional'
TURNS = [
    '我想减肥，但白天总忍着，下班就控制不住吃。',
    '中午十二点只吃一点饭，晚上九点才吃特别饿，经常一大盒外卖炒面。',
    '还是得点外卖，没时间做饭。',
    '你别像填表一样一直问年龄体重，先说我这件事能怎么试。',
    '继续。',
]


def main():
    global OUTPUT, FICTIONAL_STATE
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--artifact-version', default='0.4.29')
    parser.add_argument('--turn-limit', type=int, choices=range(1, len(TURNS)+1),
                        default=len(TURNS), help='Run only the first N turns.')
    parser.add_argument('--resume-fictional', action='store_true',
                        help='Restore only this script\'s fictional fixture and retry its last failed turn.')
    parser.add_argument('--continue-on-error', action='store_true',
                        help='Continue later turns after a failed check; exit nonzero if any turn failed.')
    args = parser.parse_args()
    if not re.fullmatch(r'\d+\.\d+\.\d+', args.artifact_version):
        parser.error('Expected a numeric version label')
    OUTPUT=ROOT/f'tmp/conversation-experience-live-{args.artifact_version}.json'
    FICTIONAL_STATE=ROOT/f'tmp/conversation-experience-live-{args.artifact_version}-fictional-state.json'
    sys.path.insert(0, str(ROOT))
    results = []
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory(prefix='zhiheng-conversation-experience-') as folder:
        # Set this before importing server: no real application .data is opened.
        os.environ['ZHIHENG_DATA_DIR'] = folder
        import consultation
        import product
        import server
        import storage

        assert server.DATA.resolve() == Path(folder).resolve()
        server.CONFIG = json.loads((ROOT/'config.json').read_text(encoding='utf-8'))
        storage.initialize(server.DATA)
        resume_turn = 1
        retry_job = None
        if args.resume_fictional:
            fixture = json.loads(FICTIONAL_STATE.read_text(encoding='utf-8'))
            assert isinstance(fixture, dict) and set(fixture) == set(storage.NAMES), \
                'Only the complete fictional storage fixture is eligible for restore'
            assert all(isinstance(value, type(storage.NAMES[name])) for name, value in fixture.items()), \
                'Invalid fictional fixture document types'
            assert all(item.get('id') == CONVERSATION_ID for item in fixture['conversations.json']), \
                'Fixture contains an unrelated conversation'
            results = json.loads(OUTPUT.read_text(encoding='utf-8'))
            assert isinstance(results, list) and all(
                isinstance(row, dict) and isinstance(row.get('turn'), int)
                and 1 <= row['turn'] <= len(TURNS)
                and row.get('user') == TURNS[row['turn']-1] for row in results), \
                'Only this script\'s fictional result history is eligible for restore'
            with storage.transaction(server.DATA):
                for name, value in fixture.items():
                    storage.write(server.DATA, name, value)
            failed_row = next((row for row in reversed(results)
                               if row.get('error') or row.get('check_failures')), None)
            resume_turn = failed_row['turn'] if failed_row else max(
                (row['turn'] for row in results), default=0)+1
            retry_job = next((job for job in reversed(product.workspace(server).get('evaluation_jobs', []))
                              if job.get('kind') == 'chat' and job.get('status') == 'failed'
                              and job.get('conversation_id') == CONVERSATION_ID
                              and resume_turn <= len(TURNS)
                              and job.get('request', {}).get('text') == TURNS[resume_turn-1]), None)
        actual_call = server.call_ai
        captured_replies = []
        failures = []

        def capture_model_reply(*call_args, **call_kwargs):
            raw = actual_call(*call_args, **call_kwargs)
            parsed = server.parse_json(raw)
            if isinstance(parsed, dict) and isinstance(parsed.get('reply'), str):
                captured_replies.append(parsed['reply'])
            return raw

        server.call_ai = capture_model_reply
        try:
            for number, user_text in enumerate(TURNS[:args.turn_limit], 1):
                if number < resume_turn:
                    continue
                captured_replies.clear()
                started = time.monotonic()
                request = {
                    'text':user_text,
                    'conversation_id':CONVERSATION_ID,
                    'client_message_id':f'conversation-experience-fictional-{number}-{time.time_ns()}',
                }
                if args.resume_fictional and number == resume_turn and retry_job:
                    request['retry_chat'] = retry_job['id']
                answer = product.chat(server, request)
                session = product.workspace(server)['sessions'][CONVERSATION_ID]
                raw_reply = captured_replies[-1] if captured_replies else None
                row = {
                    'turn':number,
                    'user':user_text,
                    'reply':answer['reply'],
                    'model_reply':raw_reply,
                    'model_replies':list(captured_replies),
                    'same_as_model_reply':answer['reply'] == raw_reply if raw_reply is not None else None,
                    'reply_adjustments':answer.get('reply_adjustments', []),
                    'mode':session.get('dialogue_mode'),
                    'error':answer.get('ai_error'),
                    'elapsed_ms':round((time.monotonic()-started)*1000),
                    'has_plan':bool(answer.get('plan')),
                    'retried_failed_request':bool(request.get('retry_chat')),
                }
                checks = []
                if row['error']:
                    checks.append(f'Model error: {row["error"]}')
                if row['has_plan'] or product.workspace(server)['plans']:
                    checks.append('A formal plan was generated or persisted prematurely')
                if number == 3 and not row['error'] and not re.search(
                        r'外卖|点餐|点单|下单|平台|现成|菜单', row['reply']):
                    checks.append('Reply did not acknowledge the takeout constraint')
                if number >= 4:
                    if row['mode'] != 'chat':
                        checks.append('Explicit pacing preference did not persist')
                    question = consultation.displayed_question_text(row['reply'], answer.get('decision'))
                    if re.search(r'年龄|多大|几岁|身高|体重|性别', question):
                        checks.append('Basic profile collection resumed after the user asked to discuss the difficulty')
                row['check_failures'] = checks
                failures.extend(f'Turn {number}: {message}' for message in checks)
                results.append(row)
                # Only fictional user messages and model reply strings are exported.
                # Transport arguments, request headers, and configuration stay private.
                print(json.dumps(row, ensure_ascii=False), flush=True)
                OUTPUT.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding='utf-8')
                if checks and not args.continue_on_error:
                    break
        finally:
            server.call_ai = actual_call
            OUTPUT.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding='utf-8')
            FICTIONAL_STATE.write_text(json.dumps(storage.snapshot(server.DATA), ensure_ascii=False,
                                                 indent=2), encoding='utf-8')
        print(json.dumps({'run_status':'failed' if failures else 'completed', 'failures':failures,
                          'historical_failed_attempts':sum(bool(row.get('error') or row.get('check_failures'))
                                                           for row in results)}, ensure_ascii=False), flush=True)
        return 1 if failures else 0


if __name__ == '__main__':
    raise SystemExit(main())
