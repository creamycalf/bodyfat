"""Real-model summary/plan journey with fictional facts and disposable storage."""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import product
import server
from test_consultation_phase1 import ConsultationPhaseOneTests


fixture = ConsultationPhaseOneTests()
fixture.setUp()
try:
    fixture.complete_profile()
    server.save_json(server.DATA / 'workspace.json', {})
    server.CONFIG['ai']['base_url'] = 'http://47.110.38.211:8080/v1'

    def chat(text, cid, mid):
        result = product.chat(server, {'text': text, 'conversation_id': cid,
                                      'client_message_id': mid})
        state = product.workspace(server)['assessment_state']['summary_confirmation']
        print(json.dumps({'turn': mid, 'status': result.get('ai_status'),
                          'error': result.get('ai_error'), 'summary_status': state['status'],
                          'plan_saved': bool(result.get('plan')),
                          'plan_item_count': len((result.get('plan') or {}).get('items', [])),
                          'reply': result['reply']},
                         ensure_ascii=False), flush=True)
        assert result.get('ai_status') == ('local' if mid == 'unrelated-yes' else 'connected') and not result.get('ai_error')
        return result

    first = chat('请根据已知资料制定从明天开始的一周减重方案，只安排一项记录饥饿感的行动。',
                 'fictional-summary', 'summary-request')
    assert first['plan'] is None and '请核对我理解的情况' in first['reply']
    chat('可以', 'fictional-other', 'unrelated-yes')
    assert product.workspace(server)['assessment_state']['summary_confirmation']['status'] == 'pending'
    final = chat('确认', 'fictional-summary', 'summary-yes')
    assert final['plan'] is not None
    assert product.workspace(server)['assessment_state']['summary_confirmation']['status'] == 'confirmed'
    assert len(product.snapshot(server)['plans']) == 1
    print('PASS: summary remained pending in another conversation; return and confirm saved one plan.', flush=True)
finally:
    fixture.tearDown()
