import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import server
import product
import storage

class ProductTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name);self.data=self.root/'.data';self.data.mkdir()
        values={'ROOT':self.root,'DATA':self.data,'MEDIA_DIR':self.data/'media'}
        values.update({k:self.data/v for k,v in {'PROFILE':'profile.json','RECORDS':'records.json','CONVERSATIONS':'conversations.json','MEDIA':'media.json','METADATA':'metadata.json'}.items()})
        self.patches=[patch.object(server,k,v) for k,v in values.items()]
        for p in self.patches:p.start()
        storage.initialize(self.data)
        from intake_fixture import skipped_interview
        skipped_interview('conversation-1234')
        self.model=patch.object(server,'call_ai',return_value=json.dumps({'reply':'已整理计划','plan':{'title':'一周作息计划','goal':'改善作息','duration_days':7,'items':[{'title':'睡前复盘','detail':'记录今天的状态','when':'睡前'}]}}));self.model.start()
    def tearDown(self):
        self.model.stop()
        for p in reversed(self.patches):p.stop()
        self.temp.cleanup()
    def chat(self,text,mid='message-1234',**kw):return product.chat(server,{'text':text,'client_message_id':mid,'conversation_id':'conversation-1234',**kw})
    def test_form_continue_plan_archive_idempotence(self):
        first=self.chat('帮我制定改善睡眠的计划',show_form=True)
        self.assertIn('sleep_schedule',[f['key'] for f in first['form']['fields']])
        second=self.chat('请继续原来的计划','message-5678',intake_values={'age':'39','sleep_schedule':'23点睡7点起'})
        self.assertIsNotNone(second['plan']);self.assertEqual(product.snapshot(server)['profile']['age'],39)
        self.chat('请继续原来的计划','message-5678',intake_values={'age':'39','sleep_schedule':'23点睡7点起'})
        self.assertEqual(len(product.snapshot(server)['plans']),1)
    def test_direct_plan_feedback_and_restore(self):
        answer=self.chat('我39岁，身高171厘米，今天100公斤，帮我制定从今天开始执行的计划')
        snap=product.snapshot(server);self.assertEqual(len(snap['tasks']),1);self.assertEqual(len(snap['records']),1)
        product.action(server,{'action':'feedback','task_id':snap['tasks'][0]['task_id'],'status':'done'})
        raw,_=server.build_backup();server.restore_backup(raw)
        self.assertEqual(product.snapshot(server)['tasks'][0]['status'],'done')
        self.assertEqual(product.snapshot(server)['profile']['height_cm'],171)

    def test_feedback_can_defer_one_task_to_a_new_date(self):
        self.chat('我39岁，身高171厘米，帮我制定从今天开始执行的计划')
        task=product.snapshot(server)['tasks'][0];original=product.datetime.fromisoformat(task['date']).date()
        target=(original+product.timedelta(days=1)).isoformat()
        product.action(server,{'action':'feedback','task_id':task['task_id'],'status':'deferred','deferred_to':target})
        self.assertEqual(product.snapshot(server)['tasks'][0]['status'],'deferred')
        moved=product.tasks_for(product.workspace(server),target)
        self.assertEqual(len(moved),1);self.assertEqual(moved[0]['deferred_from'],task['date'])
        self.assertEqual(moved[0]['status'],'unreported')
        product.action(server,{'action':'feedback','task_id':moved[0]['task_id'],'status':'done'})
        self.assertEqual(product.tasks_for(product.workspace(server),target)[0]['status'],'done')

    def test_feedback_rejects_invalid_deferred_date(self):
        self.chat('我39岁，身高171厘米，帮我制定从今天开始执行的计划')
        task=product.snapshot(server)['tasks'][0];original=product.datetime.fromisoformat(task['date']).date()
        for target in (original.isoformat(),(original+product.timedelta(days=31)).isoformat(),'not-a-date'):
            with self.subTest(target=target),self.assertRaises(product.ProductError):
                product.action(server,{'action':'feedback','task_id':task['task_id'],'status':'deferred','deferred_to':target})
    def test_transaction_rollback(self):
        with self.assertRaises(RuntimeError):
            with storage.transaction(self.data):
                server.save_json(server.PROFILE,{'age':50});raise RuntimeError('fail')
        self.assertEqual(server.load_json(server.PROFILE,{}),{})
    def test_hypothetical_not_saved(self):
        self.chat('如果我今年39岁，体重80公斤呢')
        self.assertEqual(product.snapshot(server)['records'],[])
        self.assertEqual(product.snapshot(server)['profile'],{})
    def test_undo(self):
        self.chat('我39岁')
        product.action(server,{'action':'undo','id':'message-1234'})
        self.assertEqual(product.snapshot(server)['profile'],{})
    def test_weight_goal_alone_does_not_generate_personal_plan(self):
        result=self.chat('我体重200斤，怎么减肥')
        self.assertIsNone(result['plan'])
        self.assertEqual(len(product.snapshot(server)['plans']),0)
        self.assertEqual(product.snapshot(server)['records'][0]['value']['kg'],100)

    def test_common_plan_phrases_are_recognized(self):
        phrases=[
            '结合我刚才说的情况给我一个能长期坚持、适合上班族的一周减肥安排',
            '我想瘦下来',
            '给点减肥建议',
            '能不能帮我规划一下接下来一周怎么吃怎么练',
            '把刚才的建议保存到看板',
        ]
        for text in phrases:
            with self.subTest(text=text):self.assertTrue(product.wants_plan(text))

    def test_adjusts_suggested_plan_and_preserves_suggested_state(self):
        original=json.dumps({'reply':'已整理计划','plan':{'title':'一周作息计划','goal':'改善作息','duration_days':7,
            'items':[{'title':'睡前复盘','detail':'记录今天的状态','when':'每天'}]}})
        adjusted=json.dumps({'reply':'已调整计划','plan':{'title':'一周作息计划','goal':'改善作息','duration_days':7,
            'items':[{'title':'睡前复盘','detail':'记录今天的状态','when':'每周三次'}]}})
        with patch.object(server,'call_ai',side_effect=[original,adjusted]):
            self.chat('我39岁，身高171厘米，帮我制定改善作息计划')
            result=self.chat('把计划改成每周三次','message-5678')
        snap=product.snapshot(server)
        self.assertEqual(result['plan']['version'],2)
        self.assertEqual([x['status'] for x in snap['plans']],['replaced','suggested'])
        self.assertTrue(result['plan']['changes'])
        self.assertTrue(any(item['label'].endswith('时间/频率') for item in result['plan']['changes']))

    def test_plan_change_summary_does_not_invent_changes(self):
        plan={'title':'一周计划','goal':'规律行动','start_date':'2026-09-08','end_date':'2026-09-14',
              'review_date':'2026-09-15','items':[{'title':'步行','detail':'舒适步行','when':'每天',
              'minimum':'10分钟','dates':['2026-09-08']}]}
        self.assertEqual(product.plan_change_summary(plan,plan),[])

    def test_weekly_frequency_becomes_concrete_dates(self):
        start=product.datetime(2026,9,8).date()
        dates=product.schedule_dates('每周三次',start,7)
        self.assertEqual(dates,['2026-09-08','2026-09-11','2026-09-14'])
        self.assertEqual(product.schedule_dates('周一、三、五',start,7),
                         ['2026-09-09','2026-09-11','2026-09-14'])

    def test_complex_schedule_phrases_and_explicit_plan_start(self):
        start=product.datetime(2026,9,8).date()
        self.assertEqual(product.schedule_dates('周一到周五',start,7),
                         ['2026-09-08','2026-09-09','2026-09-10','2026-09-11','2026-09-14'])
        self.assertEqual(product.schedule_dates('每3天一次',start,8),
                         ['2026-09-08','2026-09-11','2026-09-14'])
        self.assertEqual(product.schedule_dates('每周一三五',start,7),
                         ['2026-09-09','2026-09-11','2026-09-14'])
        self.assertEqual(product.schedule_dates('下周三',start,14),['2026-09-16'])
        self.assertEqual(product.plan_start_date('9月15日开始',start),product.datetime(2026,9,15).date())
        self.assertEqual(product.plan_start_date('下周一开始',start),product.datetime(2026,9,14).date())
        previous={'start_date':'2026-09-10'}
        self.assertEqual(product.plan_start_date('计划延期3天',start,previous),product.datetime(2026,9,13).date())
        with self.assertRaises(product.ProductError):product.plan_start_date('2026年2月30日开始',start)
        raw={'title':'计划','goal':'规律行动','duration_days':7,'items':[{'title':'步行','detail':'舒适步行','when':'每天'}]}
        with self.assertRaises(product.ProductError):product.normalize_plan(raw,'2025年1月1日开始',{'plans':[]},{})

    def test_invalid_model_plan_keeps_validated_user_fact(self):
        malformed=json.dumps({'reply':'已经安排好了','plan':{'title':'缺少事项','goal':'减脂','items':[]}})
        with patch.object(server,'call_ai',return_value=malformed):
            result=self.chat('我体重200斤，帮我制定减肥计划')
        snap=product.snapshot(server)
        self.assertIsNone(result['plan'])
        self.assertEqual(result['ai_error'],'AI_INVALID_PLAN')
        self.assertEqual(snap['records'][0]['value']['kg'],100)
        self.assertEqual(snap['plans'],[])
        self.assertIn('尚未生成可保存的计划',result['reply'])

    def test_high_risk_plan_is_blocked_but_user_fact_is_kept(self):
        unsafe=json.dumps({'reply':'照此执行','plan':{'title':'激进减重','goal':'一周减五公斤','duration_days':7,
            'items':[{'title':'极低热量','detail':'每天总热量控制在500千卡','when':'每天','minimum':'只喝水'}]}})
        with patch.object(server,'call_ai',return_value=unsafe):
            result=self.chat('我体重200斤，帮我制定减肥计划')
        snap=product.snapshot(server)
        self.assertEqual(result['ai_error'],'AI_UNSAFE_PLAN')
        self.assertIsNone(result['plan']);self.assertEqual(snap['plans'],[])
        self.assertEqual(snap['records'][0]['value']['kg'],100)
        self.assertIn('已阻止保存',result['reply'])

    def test_plan_safety_rules_cover_medication_and_danger_signs(self):
        base={'title':'计划','goal':'改善习惯','items':[]}
        cases={
            'medication_change':'自行停用降压药并开始跑步',
            'extreme_fasting':'连续三天只喝水',
            'rapid_weight_loss':'每周减3公斤',
            'exercise_through_danger_signs':'出现胸痛也要坚持跑步',
        }
        for code,detail in cases.items():
            with self.subTest(code=code):
                raw={**base,'items':[{'title':'事项','detail':detail}]}
                self.assertIn(code,product.plan_safety_findings(raw))
        safe={**base,'items':[{'title':'步行','detail':'舒适速度步行，胸痛或呼吸困难时立即停止并就医'}]}
        self.assertEqual(product.plan_safety_findings(safe),[])
        safe_warnings={**base,'items':[{'title':'安全边界','detail':'不要自行停用药物；不要绝食；每天总热量不得低于700千卡；不要在胸痛时坚持运动'}]}
        self.assertEqual(product.plan_safety_findings(safe_warnings),[])

    def test_food_slices_and_separate_fields_are_not_medication_changes(self):
        for detail in ('早餐改用全麦面包片搭配鸡蛋','把油炸食品换掉，改用蒸鱼片','午餐肉片减量，增加蔬菜'):
            self.assertEqual(product.plan_safety_findings({'items':[{'detail':detail}]}),[])
        self.assertEqual(product.plan_safety_findings({'items':[{'detail':'按医嘱服药','minimum':'面条减量'}]}),[])
        self.assertIn('medication_change',product.plan_safety_findings({'items':[{'detail':'降压药减量'}]}))

    def test_energy_deficit_is_not_mistaken_for_total_daily_intake(self):
        for text in ('每天热量缺口约300千卡','每日热量减少500千卡'):
            self.assertNotIn('very_low_calorie',product.plan_safety_findings({'items':[{'detail':text}]}))
        self.assertIn('very_low_calorie',product.plan_safety_findings({'items':[{'detail':'每天总热量控制在500千卡'}]}))

    def test_unsafe_reply_without_new_records_preserves_reason_and_retry_context(self):
        unsafe=json.dumps({'reply':'执行计划','plan':{'title':'计划','goal':'改善','items':[{'title':'运动','detail':'出现胸痛也要坚持跑步'}]}})
        with patch.object(server,'call_ai',return_value=unsafe):
            r=self.chat('请生成明天开始的初步计划')
        self.assertIn('危险症状下继续运动',r['reply'])
        self.assertNotIn('本轮未保存新的记录或变更',r['reply'])
        job=next(j for j in product.snapshot(server)['evaluation_jobs'] if j.get('kind')=='chat')
        self.assertIn('exercise_through_danger_signs',job['safety_findings'])
        with patch.object(server,'call_ai',return_value=json.dumps({'reply':'先问清楚','decision':{'action':'clarify'},'plan':None})) as call:
            self.chat('继续','retry-safety-1234',retry_chat=job['id'])
        self.assertIn('exercise_through_danger_signs',call.call_args[0][0][0]['content'])

    def test_snapshot_marks_deleted_or_memory_disabled_plan_basis(self):
        self.chat('我39岁，今天100公斤，帮我制定从今天开始执行的计划')
        snap=product.snapshot(server);record_id=snap['records'][0]['id']
        # Explicitly link evidence. Recent context is no longer automatically
        # claimed as a plan's supporting evidence.
        w=product.workspace(server);w['plans'][0]['basis_record_ids']=[record_id]
        server.save_json(server.DATA/'workspace.json',w)
        self.assertEqual(snap['plans'][0]['basis_unavailable'],[])
        records=server.records();records[0]['memory_enabled']=False;server.save_json(server.RECORDS,records)
        self.assertEqual(product.snapshot(server)['plans'][0]['basis_unavailable'],
                         [{'id':record_id,'reason':'memory_disabled'}])
        server.save_json(server.RECORDS,[])
        self.assertEqual(product.snapshot(server)['plans'][0]['basis_unavailable'],
                         [{'id':record_id,'reason':'deleted'}])

if __name__=='__main__':unittest.main()
