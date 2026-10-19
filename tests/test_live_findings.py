import copy
import unittest
import test_workbench
import product
import server
import workbench
from unittest.mock import patch


class LiveFindingTests(unittest.TestCase):
    def setUp(self):test_workbench.WorkbenchTests.setUp(self)
    def tearDown(self):test_workbench.WorkbenchTests.tearDown(self)
    chat=test_workbench.WorkbenchTests.chat
    make_walk_plan=test_workbench.WorkbenchTests.make_walk_plan

    def test_habit_is_profile_not_sleep_even_with_truncated_model_evidence(self):
        self.output['record_events']=[{'type':'sleep','value':{'hours':8},'evidence':'23点睡7点起'}]
        self.chat('我通常23点睡7点起')
        snap=product.snapshot(server)
        self.assertFalse(any(r['type']=='sleep' for r in snap['records']))
        self.assertIn('23点睡7点起',snap['profile']['sleep_schedule'])
        self.output['record_events']=[]
        self.chat('昨晚睡了7小时')
        self.assertEqual([r['value']['hours'] for r in server.records() if r['type']=='sleep'],[7])

    def test_exact_task_completion_persists_even_if_model_omits_action(self):
        _,task=self.make_walk_plan()
        self.output.update(plan=None,reply='已记录完成',decision={'action':'none','reason':'反馈'},feedback=[])
        self.chat(task['title']+'完成了。')
        self.assertEqual(product.snapshot(server)['tasks'][0]['status'],'done')

    def test_false_completion_prose_is_replaced_and_occupation_not_polluted(self):
        self.output.update(reply='好的，已记录您完成了今天的工作日饮水提醒。',
            profile_changes=[{'field':'occupation','value':'工作日饮水提醒完成了','evidence':'工作日饮水提醒完成了'}])
        answer=self.chat('工作日饮水提醒完成了。')
        snap=product.snapshot(server)
        self.assertNotIn('occupation',snap['profile']);self.assertEqual(snap['pending'],[])
        self.assertIn('没有保存完成打卡',answer['reply'])

    def test_old_photo_does_not_override_weight_or_new_meal(self):
        self.chat('这份还没吃',media_id='food-1')
        self.output['reply']='收到体重和睡眠记录。'
        answer=self.chat('今天体重82.1公斤，昨晚睡了7小时')
        self.assertNotIn('food_error',answer)
        self.assertEqual(self.prompt[1]['content'].count('"linked_images": []'),1)
        self.output['record_events']=[{'type':'meal','evidence':'晚饭我吃了米饭','value':{'description':'米饭','nutrition':{'kcal':180}}}]
        self.chat('晚饭我吃了米饭')
        meal=next(r for r in server.records() if r['type']=='meal')
        self.assertNotIn('media_id',meal)
        self.assertEqual(meal['value']['nutrition']['kcal'],[180,180])
        self.assertEqual(product.snapshot(server)['food_summary']['totals']['kcal']['range'],[180,180])

    def test_half_portion_with_pronoun_and_legacy_scalar_nutrition(self):
        media=server.load_json(server.MEDIA,[])
        media[0]['review']['record_candidates']=[{'type':'meal','value':{'nutrition':{'kcal':600,'protein_g':[20,20]}}}]
        server.save_json(server.MEDIA,media)
        self.chat('刚才那份我吃了一半，请记录。',media_id='food-1')
        self.assertEqual(server.records()[0]['value']['nutrition']['kcal'],[300,300])
        self.assertEqual(server.records()[0]['value']['nutrition']['protein_g'],[10,10])
        for value in (True,-1,float('nan'),float('inf')):
            with self.subTest(value=value),self.assertRaises(ValueError):workbench.nutrition_ranges({'kcal':value})

    def test_negative_or_question_completion_never_local_checkin(self):
        _,task=self.make_walk_plan();self.output.update(plan=None,feedback=[],reply='好的')
        for text in [task['title']+'还没完成',task['title']+'完成了吗？','如果'+task['title']+'完成了']:
            self.chat(text)
            self.assertEqual(product.snapshot(server)['tasks'][0]['status'],'unreported')

    def test_explicit_meal_persists_when_model_omits_event_but_claims_success(self):
        self.output.update(reply='已记录今天的早餐',record_events=[],page_changes=[{'page':'invalid'}])
        self.chat('今天早餐我吃了一个鸡蛋、一片全麦面包，喝了一杯无糖豆浆，请记录。')
        meals=[r for r in server.records() if r['type']=='meal']
        self.assertEqual(len(meals),1)
        self.assertIsNone(meals[0]['value']['nutrition']['kcal'])

    def test_meal_claim_cannot_hide_behind_failed_page_receipt(self):
        self.output.update(reply='已记录今天的早餐',record_events=[],page_changes=[{'page':'invalid'}])
        answer=self.chat('这只是询问早餐搭配，不是实际摄入')
        self.assertEqual(server.records(),[])
        self.assertIn('没有保存新的餐食',answer['reply'])

    def test_failed_request_retry_persists_and_does_not_duplicate_weight(self):
        with patch.object(server,'call_ai',return_value=None),patch.object(server,'ai_meta',return_value={'ai_error':'AI_TIMEOUT','ai_status':'fallback'}):
            product.chat(server,{'text':'今天体重82公斤，请生成今天开始的计划','conversation_id':'test-conversation','client_message_id':'timeout-message-1'})
        job=next(j for j in product.snapshot(server)['evaluation_jobs'] if j.get('kind')=='chat')
        self.assertEqual(len(server.records()),1)
        self.output.update(plan={'title':'日常活动','goal':'规律作息','items':[{'title':'散步','when':'每天'}]},
            record_events=[{'type':'weight','value':{'kg':82},'evidence':'体重82公斤'}])
        with patch.object(server,'ai_meta',return_value={'ai_error':None,'ai_status':'connected'}):
            self.chat('继续',retry_chat=job['id'])
        self.assertEqual(len(server.records()),1)
        self.assertEqual(next(j for j in product.snapshot(server)['evaluation_jobs'] if j['id']==job['id'])['status'],'resolved')
        self.assertEqual(len(product.snapshot(server)['plans']),1)
        with self.assertRaises(product.ProductError):self.chat('再次继续',retry_chat=job['id'])

    def test_retry_rejects_cross_day_request(self):
        w=product.workspace(server);w['evaluation_jobs']=[{'id':'job-old','kind':'chat','status':'failed','conversation_id':'test-conversation','request_date':'2000-01-01','request':{'text':'今天体重80公斤'}}]
        server.save_json(server.DATA/'workspace.json',w)
        with self.assertRaises(product.ProductError):self.chat('继续',retry_chat='job-old')

    def test_page_aliases_and_saved_draft_do_not_create_health_facts(self):
        module={'id':'food-note','page':'看板','type':'text','title':'餐食说明','body':'根据已记录的餐食查看','reason':'查看记录'}
        self.output['page_changes']=[module]
        self.chat('查看记录说明')
        self.assertEqual(product.snapshot(server)['modules'][0]['page'],'dashboard')
        module['page']='unrecognized';self.chat('再补充说明')
        job=next(j for j in product.snapshot(server)['evaluation_jobs'] if j.get('draft'))
        self.assertEqual(job['draft'][0]['page'],'unrecognized')

    def test_no_replan_request_suppresses_model_plan(self):
        self.output.update(plan={'title':'新计划','goal':'目标','items':[{'title':'散步'}]},decision={'action':'generate_plan','reason':'误判'})
        answer=self.chat('今天体重82.1公斤，请记录，不用重新制定计划。')
        self.assertEqual(product.snapshot(server)['plans'],[])
        self.assertNotIn('尚未生成',answer['reply'])

    def test_recipe_placeholders_are_not_real_instructions(self):
        options=product.normalize_meal_options({'cook':{'dish':'不适用，外卖','ingredients':'无','steps':'不适用'},'takeout':{'dish':'鸡肉饭','search':'鸡肉饭 蔬菜'}})
        self.assertNotIn('cook',options)
        self.assertEqual(options['takeout']['dish'],'鸡肉饭')

    def test_explicit_available_time_is_saved_without_model_field(self):
        self.chat('更正，每天可用时间现在是午休20分钟，晚上加班到21点30分。')
        self.assertEqual(product.snapshot(server)['profile']['available_time'],'每天可用时间现在是午休20分钟')

    def test_retry_does_not_duplicate_local_feedback_saved_during_timeout(self):
        _,task=self.make_walk_plan()
        with patch.object(server,'call_ai',return_value=None),patch.object(server,'ai_meta',return_value={'ai_error':'AI_TIMEOUT','ai_status':'fallback'}):
            product.chat(server,{'text':task['title']+'完成了','conversation_id':'test-conversation','client_message_id':'feedback-timeout-original'})
        snap=product.snapshot(server);job=next(j for j in snap['evaluation_jobs'] if j.get('kind')=='chat')
        before=copy.deepcopy(snap['feedback'])
        self.output.update(plan=None,feedback=[{'task_id':task['task_id'],'status':'done','evidence':task['title']+'完成了'}])
        with patch.object(server,'ai_meta',return_value={'ai_error':None,'ai_status':'connected'}):self.chat('继续',retry_chat=job['id'])
        self.assertEqual(product.snapshot(server)['feedback'],before)
