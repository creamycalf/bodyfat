"""Conversation dates and identities must survive extraction and retries."""
import json
import unittest
from datetime import datetime,timedelta
from unittest.mock import patch

import consultation
import intake
import product
import server
import test_workbench


class RecordDatesFixTests(unittest.TestCase):
    setUp=test_workbench.WorkbenchTests.setUp
    tearDown=test_workbench.WorkbenchTests.tearDown
    chat=test_workbench.WorkbenchTests.chat

    def weights(self):return [r for r in server.records() if r.get('type')=='weight']

    def test_month_history_and_today_save_separate_dates(self):
        self.output['record_events']=[
            {'type':'weight','value':{'kg':85},'evidence':'9月体重85公斤','created_at':'2099-01-01'},
            {'type':'weight','value':{'kg':82},'evidence':'今天82公斤'}]
        self.chat('9月体重85公斤，今天82公斤，先聊聊变化。')
        records=self.weights()
        self.assertEqual(len(records),2)
        old=next(r for r in records if r['value']['kg']==85)
        recent=next(r for r in records if r['value']['kg']==82)
        self.assertIsNone(old['occurred_at'])
        self.assertEqual(old['date_precision'],'month')
        self.assertTrue(old['date_text'].endswith('-09'))
        self.assertTrue(recent['occurred_at'].startswith(product.today()))
        self.assertEqual(intake.current_weight_records(records)[-1]['value']['kg'],82)

    def test_exact_and_relative_dates_come_from_source_evidence(self):
        reference=datetime(2026,10,17,16,30)
        for text,expected in [('2026年9月3日体重85公斤','2026-09-03'),
                              ('2026-09-03体重85公斤','2026-09-03'),
                              ('9月3号体重85公斤','2026-09-03'),
                              ('去年9月3号体重85公斤','2025-09-03'),
                              ('昨天体重85公斤','2026-10-16'),
                              ('前天体重85公斤','2026-10-15'),
                              ('上周一体重85公斤','2026-10-05'),
                              ('上星期日体重85公斤','2026-10-11')]:
            with self.subTest(text=text):
                event={'type':'weight','value':{'kg':85},'evidence':'体重85公斤','occurred_at':'2099-01-01'}
                self.assertTrue(product.event_time(event,text,reference)['stamp'].startswith(expected))

    def test_same_value_on_different_days_is_preserved(self):
        self.chat('昨天体重65公斤，今天体重65公斤。')
        records=self.weights()
        self.assertEqual(len(records),2)
        self.assertEqual(len({r['occurred_at'][:10] for r in records}),2)

    def test_multiple_sleep_records_keep_separate_days(self):
        self.chat('前晚睡了6小时，昨晚睡了7小时。')
        records=[r for r in server.records() if r.get('type')=='sleep']
        self.assertEqual(len(records),2)
        self.assertEqual({r['value']['hours'] for r in records},{6,7})
        self.assertEqual(len({r['occurred_at'][:10] for r in records}),2)

    def test_naked_weight_is_saved_once_despite_three_extractors(self):
        self.output['record_events']=[{'type':'weight','value':{'kg':65},'evidence':'裸体重65kg','created_at':'2099-01-01'}]
        self.chat('今天裸体重65kg，先聊聊。')
        self.assertEqual(len(self.weights()),1)
        self.assertTrue(self.weights()[0]['occurred_at'].startswith(product.today()))

    def test_future_invalid_or_vague_history_cannot_become_current(self):
        for text in ('以前体重85公斤','2026年2月30日体重85公斤','2099年1月1日体重85公斤'):
            with self.subTest(text=text):
                self.chat(text+'，先聊聊。')
        records=self.weights()
        self.assertEqual(len(records),3)
        self.assertTrue(all(r['occurred_at'] is None for r in records))
        self.assertFalse(intake.current_weight_records(records))
        self.assertIn('weight_kg',intake.missing({},records))
        self.assertFalse(consultation._known_any({},records,('weight_kg',)))

    def test_current_weight_uses_observation_order_and_freshness(self):
        now=datetime.now()
        records=[{'type':'weight','value':{'kg':82},'observed_at':now.isoformat()},
                 {'type':'weight','value':{'kg':85},'observed_at':(now-timedelta(days=5)).isoformat()},
                 {'type':'weight','value':{'kg':90},'observed_at':(now-timedelta(days=50)).isoformat()}]
        self.assertEqual(intake.current_weight_records(records)[-1]['value']['kg'],82)
        self.assertIn('82',consultation.summary_text({},records,()))
        form=product.form_for('weight',{},records)
        self.assertEqual(next(f for f in form['fields'] if f['key']=='weight_kg')['value'],82)
        self.assertFalse(intake.current_weight_records(records[-1:]))

    def test_exact_history_and_today_survive_model_failure_and_retry(self):
        text='2026年9月3日体重85公斤，今天82公斤，先聊聊变化。'
        with patch.object(server,'call_ai',side_effect=TimeoutError('timeout')):
            first=product.chat(server,{'text':text,'conversation_id':'test-conversation','client_message_id':'date-first-attempt'})
        self.assertEqual(len(self.weights()),2)
        job=next(j for j in product.snapshot(server)['evaluation_jobs'] if j.get('kind')=='chat')
        self.output['record_events']=[{'type':'weight','value':{'kg':85},'evidence':'2026年9月3日体重85公斤'},
                                      {'type':'weight','value':{'kg':82},'evidence':'今天82公斤'}]
        self.chat('继续',retry_chat=job['id'])
        self.assertEqual(len(self.weights()),2)

    def test_model_numeric_value_must_exist_in_evidence(self):
        self.output['record_events']=[{'type':'weight','value':{'kg':92},'evidence':'今天体重82公斤'}]
        self.chat('今天体重82公斤，先聊聊。')
        self.assertEqual([r['value']['kg'] for r in self.weights()],[82])

    def test_food_weight_is_not_a_body_weight_event(self):
        _,events=product.explicit_facts(server,'今天我吃了1公斤西瓜。')
        self.assertFalse(any(event.get('type')=='weight' for event in events))

    def test_other_persons_date_is_not_inherited_after_self_reset(self):
        event={'type':'weight','value':{'kg':82},'evidence':'而我体重82公斤'}
        clean=product.prepared_event(server,event,'我朋友前天体重85公斤，而我体重82公斤',{},'date-owner')
        self.assertTrue(clean['occurred_at'].startswith(product.today()))

    def test_dashboard_uses_measurement_date_and_ignores_imprecise_history(self):
        today=product.now();yesterday=(datetime.now()-timedelta(days=1)).isoformat()
        server.save_json(server.RECORDS,[
            {'id':'current','type':'weight','value':{'kg':82},'observed_at':today,'created_at':yesterday},
            {'id':'old','type':'weight','value':{'kg':85},'observed_at':'2026-01-01','created_at':today},
            {'id':'unknown','type':'weight','value':{'kg':90},'date_precision':'month','date_text':'2026-09','created_at':today},
            {'id':'sleep-old','type':'sleep','value':{'hours':3},'date_precision':'unknown','recorded_at':today,'created_at':today}])
        board=server.dashboard()
        self.assertEqual(board['latest_weight_kg'],82)
        self.assertEqual([r['id'] for r in board['weight_series']],['current'])
        self.assertNotIn('最近确认睡眠',str(board['recommendation']))


if __name__=='__main__':unittest.main()
