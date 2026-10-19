"""Paired model probes on identical fictional prompts, plus application rewrites.

Only synthetic cases are supported. No production records, config or keys are
written to the report. Candidate replies do not alter the baseline history.
"""
import argparse
import copy
import json
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import product
import server
import storage

TURNS = [
    '我现在88公斤，想瘦一点，但以前一做计划就坚持不下来，先聊聊行吗？',
    '我38岁，172厘米。其实最烦的是晚上九点下班，到家很饿，只能叫外卖。',
    '性别暂时不想说，能先聊聊晚上饿这件事吗？',
    '不是，我是九点下班，十点才到家。午餐十二点吃，下午没吃东西。',
    '那是不是晚上干脆不吃就好了？',
    '别急着安排，我就想知道为什么这么饿。',
    '明白了。不过午餐那个饭是我同事吃的，不是我，我自己吃的面。',
    '好，那继续吧，别再问刚才不想说的了。',
]

PACING_TURNS = [
    '我想减点体重，但上次天天称重搞得我很焦虑，先随便聊聊吧。',
    '主要是周末陪家人吃饭，吃完就觉得自己又失败了。',
    '年龄和性别先不说，也先别给我安排饮食。',
    '我想先知道，为什么一顿饭没按原来的想法吃就觉得失败？',
    '更正一下，我说的是周六聚餐，不是每个周末都聚餐。只回应这个更正就好。',
    '嗯，接着解释刚才那个想法，先不要给办法。',
    '换个话题，食品包装上每份和每100克有什么区别？',
    '明白了，现在给我一个聚餐后不那么自责的小建议，不要做计划。',
]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', required=True)
    parser.add_argument('--candidate', default='claude-opus-5')
    parser.add_argument('--baseline', default=None)
    parser.add_argument('--scenario', choices=('original','pacing'), default='original')
    parser.add_argument('--check', action='store_true', help='Assert routing/memory boundaries, not conversational quality')
    args = parser.parse_args()
    report = {'scope': 'fictional-only; paired identical prompts; candidate does not change history', 'turns': []}
    destination = Path(args.output)
    destination.parent.mkdir(parents=True, exist_ok=True)
    base_config = copy.deepcopy(server.CONFIG)
    base_config['ai']['base_url'] = 'http://47.110.38.211:8080/v1'
    if args.baseline:
        base_config['ai']['model'] = args.baseline
    report['baseline'] = base_config['ai']['model']
    report['candidate'] = args.candidate
    real_call = server.call_ai
    with tempfile.TemporaryDirectory(prefix='zhiheng-attribution-') as folder:
        data = Path(folder)
        paths = {'DATA': data, 'MEDIA_DIR': data / 'media'}
        paths.update({k: data / (k.lower()+'.json') for k in ('PROFILE','RECORDS','CONVERSATIONS','MEDIA','METADATA')})
        with patch.multiple(server, **paths), patch.object(server, 'CONFIG', base_config):
            storage.initialize(data)
            for index, utterance in enumerate(PACING_TURNS if args.scenario=='pacing' else TURNS, 1):
                calls = []
                def inspect(messages, *pos, **kw):
                    raw = real_call(messages, *pos, **kw)
                    baseline_meta = copy.deepcopy(server.ai_meta())
                    entry = {'baseline_raw': raw, 'baseline_meta': baseline_meta,
                             'conversation_mode': '正在与用户自然交谈' in messages[0]['content'],
                             'reply_focus': json.loads(messages[1]['content']).get('reply_focus')}
                    if args.candidate != 'none':
                        candidate_config = copy.deepcopy(base_config)
                        candidate_config['ai']['model'] = args.candidate
                        with patch.object(server, 'CONFIG', candidate_config):
                            entry['candidate_raw'] = real_call(copy.deepcopy(messages), *pos, **kw)
                            entry['candidate_meta'] = copy.deepcopy(server.ai_meta())
                        server.AI_STATE.meta = baseline_meta
                        server.AI_STATE.error = baseline_meta.get('ai_error') or ''
                    calls.append(entry)
                    return raw
                with patch.object(server, 'call_ai', inspect):
                    result = product.chat(server, {'text': utterance, 'conversation_id': 'fictional-attribution',
                                                  'client_message_id': f'attribution-{index}'})
                row = {'turn': index, 'user': utterance, 'calls': calls, 'final': result,
                       'profile': server.load_json(server.PROFILE, {}),
                       'skipped': product.workspace(server).get('interview', {}).get('skipped', [])}
                report['turns'].append(row)
                destination.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
                print(json.dumps({'turn': index, 'status': result.get('ai_status'), 'error': result.get('ai_error'),
                                  'reply': result['reply'], 'calls': len(calls)}, ensure_ascii=False), flush=True)
            if args.check:
                turns=report['turns']
                if args.scenario=='original':
                    assert turns[0]['final']['request_kind']=='personal_weight_plan'
                assert all(not t['final'].get('plan') for t in turns)
                assert 'sex' in turns[2]['skipped']
                assert all('sex' not in t['profile'] for t in turns)
                for t in turns:
                    for field in ('breakfast_habit','lunch_habit','dinner_habit','conditions','medications'):
                        assert not any(phrase in str(t['profile'].get(field,'')) for phrase in ('那继续吧','别再问','想知道为什么','别急着安排'))
                report['boundary_checks']='passed; does not certify medical accuracy or naturalness'
                destination.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    print('Report: '+str(destination), flush=True)


if __name__ == '__main__':
    main()
