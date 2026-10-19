import copy
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import product
import server
import storage
import workbench


class WorkbenchTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.data=Path(self.temp.name)/'.data';self.data.mkdir()
        self.paths={'DATA':self.data,'MEDIA_DIR':self.data/'media'}
        self.paths.update({k:self.data/v for k,v in {'PROFILE':'profile.json','RECORDS':'records.json','CONVERSATIONS':'conversations.json','MEDIA':'media.json','METADATA':'metadata.json'}.items()})
        self.patches=[patch.object(server,k,v) for k,v in self.paths.items()]
        for p in self.patches:p.start()
        storage.initialize(self.data)
        from intake_fixture import skipped_interview
        skipped_interview('test-conversation')
        server.save_json(server.MEDIA,[{'id':'food-1','type':'food','review':{'summary':'一份米饭和蔬菜'},'confirmed':False}])
        self.output={'reply':'我们继续了解','decision':{'action':'none','reason':'目前安排无需变化'},'plan':None}
        self.count=0

    def tearDown(self):
        for p in reversed(self.patches):p.stop()
        self.temp.cleanup()

    def chat(self,text,**kw):
        self.count+=1
        with patch.object(server,'call_ai',return_value=json.dumps(self.output,ensure_ascii=False)) as mock:
            result=product.chat(server,{'text':text,'conversation_id':'test-conversation','client_message_id':f'test-message-{self.count}',**kw})
            self.prompt=mock.call_args[0][0] if mock.called else []
            return result

    def module(self,**kw):
        return dict(id='diet-explanation',page='plan',type='text',title='适合你的饮食选择',body='结合通勤安排选择方便的晚餐',items=[],reason='用户反馈时间变化',**kw)

    def food(self,status,evidence,**kw):
        return dict(media_id='food-1',status=status,evidence=evidence,description='半份米饭和蔬菜',nutrition={'kcal':[250,400],'protein_g':[8,12]},**kw)

    def test_conversation_default_does_not_force_form(self):
        self.output['decision']['action']='clarify'
        result=self.chat('我想减肥，请先了解我的整体状况')
        self.assertIsNone(result['form']);self.assertIsNone(result['plan'])
        self.assertNotIn('尚未生成可保存的计划',result['reply'])
        self.assertIn('plan_readiness',self.prompt[1]['content'])
        self.assertIn('当前不是生成计划的轮次',self.prompt[0]['content'])

    def test_friend_correction_removes_intake_even_when_model_omits_decision(self):
        self.output['food_decisions']=[self.food('consumed','这份我吃完了')]
        self.chat('这份我吃完了',media_id='food-1')
        self.assertEqual(len(product.snapshot(server)['records']),1)
        self.output['food_decisions']=[]
        self.chat('更正，刚才那份是朋友吃的，我没吃')
        self.assertEqual(product.snapshot(server)['records'],[])
        self.assertEqual(product.snapshot(server)['media'][0]['food_decision']['status'],'reference')

    def test_short_positive_food_evidence_cannot_override_whole_sentence(self):
        self.output['food_decisions']=[self.food('consumed','吃完了')]
        self.chat('刚才那份我没吃，之前说吃完了是说错了',media_id='food-1')
        self.assertEqual(product.snapshot(server)['records'],[])

    def test_hypothetical_correction_does_not_remove_existing_meal(self):
        self.output['food_decisions']=[self.food('consumed','这份我吃完了')]
        self.chat('这份我吃完了',media_id='food-1')
        self.output['food_decisions']=[self.food('reference','我没吃')]
        self.chat('如果我说刚才那份是朋友吃的，我没吃，会怎样？')
        self.assertEqual(len(product.snapshot(server)['records']),1)

    def make_walk_plan(self):
        plan={'title':'散步安排','goal':'规律活动','items':[{'title':'午休散步','when':'每天','detail':'舒适步行'}]}
        self.output.update(decision={'action':'update','reason':'建立计划'},plan=copy.deepcopy(plan))
        self.chat('从今天开始执行计划')
        return plan,product.snapshot(server)['tasks'][0]

    def test_short_positive_feedback_does_not_override_correction(self):
        _,task=self.make_walk_plan()
        product.action(server,{'action':'feedback','task_id':task['task_id'],'status':'done'})
        self.output.update(plan=None,decision={'action':'none','reason':'反馈'},
                           feedback=[{'task_id':task['task_id'],'status':'done','evidence':'午休散步完成了'}])
        self.chat('我没完成，刚才说午休散步完成了是说错了')
        self.assertEqual(product.snapshot(server)['tasks'][0]['status'],'unreported')

    def test_revision_inherits_only_unchanged_today_task_and_preserves_history(self):
        plan,task=self.make_walk_plan()
        product.action(server,{'action':'feedback','task_id':task['task_id'],'status':'done'})
        plan['goal']='保持规律活动';self.output['plan']=plan
        self.chat('调整计划目标为保持规律活动，散步事项不变')
        snap=product.snapshot(server)
        self.assertEqual(snap['tasks'][0]['status'],'done')
        self.assertEqual(snap['feedback'][-1]['inherited_from'],task['task_id'])
        self.assertEqual(snap['feedback'][0]['task_id'],task['task_id'])
        new_task=snap['tasks'][0]
        product.action(server,{'action':'feedback','task_id':new_task['task_id'],'status':'unreported'})
        self.assertEqual(product.snapshot(server)['feedback'][0]['status'],'done')
        product.action(server,{'action':'feedback','task_id':new_task['task_id'],'status':'done'})
        plan['items'][0]['detail']='快走三十分钟';self.output['plan']=plan
        self.chat('调整散步强度')
        self.assertEqual(product.snapshot(server)['tasks'][0]['status'],'unreported')

    def test_conflicting_profile_holds_plan_and_page_changes(self):
        _,task=self.make_walk_plan()
        server.save_json(server.PROFILE,{'available_time':'晚上'})
        before=product.snapshot(server)['plans']
        self.output.update(profile_changes=[{'field':'available_time','value':'午休','evidence':'只有午休有时间'}],
                           page_changes=[self.module()])
        answer=self.chat('最近只有午休有时间，调整计划')
        snap=product.snapshot(server)
        self.assertEqual(snap['profile']['available_time'],'晚上')
        self.assertEqual(snap['plans'],before)
        self.assertEqual(snap['modules'],[])
        self.assertTrue(any(x.get('field')=='available_time' for x in snap['pending']))
        self.assertIsNone(answer['plan'])
        self.assertIn('需要先核实',answer['reply'])
        pending=next(x for x in snap['pending'] if x.get('field')=='available_time')
        product.action(server,{'action':'pending','id':pending['id'],'accept':True})
        self.output['profile_changes']=[]
        answer=self.chat('按确认后的时间调整计划')
        self.assertIsNotNone(answer['plan'])
        self.assertEqual(product.snapshot(server)['profile']['available_time'],'午休')

    def test_not_finished_food_keeps_existing_intake_for_review(self):
        self.output['food_decisions']=[self.food('consumed','这份我吃完了')]
        self.chat('这份我吃完了',media_id='food-1')
        before=copy.deepcopy(server.records())
        self.output['food_decisions']=[self.food('reference','没吃完')]
        result=self.chat('刚才那份没吃完')
        self.assertEqual(server.records(),before)
        self.assertEqual(result['food_error'],'FOOD_REVIEW_REQUIRED')

    def test_mixed_meals_and_times_never_retract_linked_intake(self):
        self.output['food_decisions']=[self.food('consumed','这份我吃完了')]
        self.chat('这份我吃完了',media_id='food-1')
        before_records=copy.deepcopy(server.records())
        before_media=copy.deepcopy(server.load_json(server.MEDIA,[]))
        cases=[
            '刚才那份午饭我吃完了，晚饭还没吃',
            '这份我吃完了，明天准备吃清淡点',
            '晚饭还没吃，刚才那份午饭我吃完了',
            '明天准备吃清淡点，这份我吃完了',
            '刚才那份午饭我吃完了晚饭还没吃',
            '这份昨天没吃，今天吃完了',
            '我早餐没吃，这份午饭吃完了',
        ]
        for text in cases:
            for status in (None,'reference','planned','consumed','unknown','not_eaten','do_not_record'):
                with self.subTest(text=text,status=status):
                    self.output['food_decisions']=[] if status is None else [self.food(status,text)]
                    result=self.chat(text)
                    self.assertEqual(server.records(),before_records)
                    self.assertEqual(server.load_json(server.MEDIA,[]),before_media)
                    self.assertEqual(result['food_error'],'FOOD_REVIEW_REQUIRED')
                    self.assertIn('没有自动修改',result['reply'])
        # After clarification the same record is correctly retracted, not duplicated.
        self.output['food_decisions']=[]
        self.chat('更正，刚才那份我没吃')
        self.assertEqual(server.records(),[])

    def test_unrelated_named_meal_does_not_retract_previous_photo(self):
        self.output['food_decisions']=[self.food('consumed','这份我吃完了')]
        self.chat('这份我吃完了',media_id='food-1')
        before=copy.deepcopy(server.records())
        self.output['food_decisions']=[self.food('reference','晚饭没吃')]
        result=self.chat('晚饭没吃')
        self.assertEqual(server.records(),before)
        self.assertEqual(result['food_error'],'FOOD_REVIEW_REQUIRED')

    def test_model_cannot_remove_record_without_nonconsumption_evidence(self):
        self.output['food_decisions']=[self.food('consumed','这份我吃完了')]
        self.chat('这份我吃完了',media_id='food-1')
        before=copy.deepcopy(server.records())
        self.output['food_decisions']=[self.food('reference','这份味道不错')]
        result=self.chat('这份味道不错')
        self.assertEqual(server.records(),before)
        self.assertEqual(result['food_error'],'FOOD_REVIEW_REQUIRED')

    def test_mixed_food_turn_does_not_create_phantom_meal_without_existing_record(self):
        for status in (None,'reference','consumed','not_eaten'):
            with self.subTest(status=status):
                self.output['food_decisions']=[] if status is None else [self.food(status,'吃完了')]
                result=self.chat('这份午饭吃完了，晚饭还没吃',media_id='food-1')
                self.assertEqual(server.records(),[])
                self.assertEqual(result['food_error'],'FOOD_REVIEW_REQUIRED')

    def test_explicitly_attached_single_meal_correction_still_works(self):
        self.output['food_decisions']=[self.food('consumed','这份我吃完了')]
        self.chat('这份我吃完了',media_id='food-1')
        self.output['food_decisions']=[self.food('reference','午饭没吃')]
        self.chat('午饭没吃',media_id='food-1')
        self.assertEqual(server.records(),[])

    def test_revision_does_not_copy_feedback_to_ambiguous_or_future_items(self):
        for mode in ('duplicate','future'):
            with self.subTest(mode=mode):
                plan,task=self.make_walk_plan()
                product.action(server,{'action':'feedback','task_id':task['task_id'],'status':'done'})
                if mode=='duplicate':plan['items'].append(copy.deepcopy(plan['items'][0]))
                self.output['plan']=plan
                self.chat('调整计划，明天开始' if mode=='future' else '调整计划，添加同名事项')
                snap=product.snapshot(server)
                latest=snap['plans'][-1]
                prefix=f"{latest['id']}:{latest['version']}:"
                self.assertFalse(any(x['task_id'].startswith(prefix) for x in snap['feedback']))

    def test_meal_options_persist_and_help_cannot_write_facts(self):
        self.output.update(decision={'action':'update','reason':'初步计划'},plan={
            'title':'饮食与散步','goal':'规律安排','items':[{'title':'午餐搭配','when':'每天','detail':'主食搭配蔬菜',
            'meal_options':{'cook':{'dish':'番茄炒蛋','ingredients':['番茄','鸡蛋'],'steps':['切块','炒熟']},
                            'takeout':{'dish':'鸡肉饭','search':'鸡肉饭 蔬菜','ordering':'酱汁分装'}}}]})
        self.chat('请从今天开始执行计划')
        before=product.snapshot(server);p=before['plans'][0];task=before['tasks'][0]
        self.assertEqual(p['items'][0]['meal_options']['cook']['steps'],'切块\n炒熟')
        self.output.update(reply='先准备食材，再炒熟。',profile_changes=[{'field':'age','value':60,'evidence':'我60岁'}],
                           feedback=[{'task_id':task['task_id'],'status':'done','evidence':'我吃完了'}],
                           record_events=[{'type':'weight','value':{'kg':70},'evidence':'体重70公斤'}])
        result=self.chat('我60岁，体重70公斤，我吃完了。这里只查看做法。',plan_help={'id':p['id'],'version':p['version'],'item_id':p['items'][0]['id'],'mode':'cook'})
        after=product.snapshot(server)
        for key in ['profile','records','plans','feedback']:self.assertEqual(before[key],after[key],key)
        self.assertIsNone(result['plan']);self.assertIn('selected_plan_item',str(self.prompt))

    def test_dialogue_and_manual_checkin_share_one_task(self):
        self.output.update(decision={'action':'update','reason':'建立计划'},plan={'title':'散步安排','goal':'规律活动','items':[{'title':'午休散步','when':'每天','detail':'舒适步行'}]})
        self.chat('从今天开始执行计划')
        task=product.snapshot(server)['tasks'][0]
        self.output.update(plan=None,decision={'action':'none','reason':'只反馈'},feedback=[{'task_id':task['task_id'],'status':'done','evidence':'午休散步完成了'}])
        self.chat('午休散步完成了')
        self.assertEqual(product.snapshot(server)['tasks'][0]['status'],'done')
        product.action(server,{'action':'feedback','task_id':task['task_id'],'status':'unreported'})
        self.assertEqual(product.snapshot(server)['tasks'][0]['status'],'unreported')
        self.assertEqual(len(product.snapshot(server)['plans']),1)

    def test_unfinished_task_is_not_accepted_as_done(self):
        self.output.update(decision={'action':'update','reason':'建立计划'},plan={'title':'散步安排','goal':'规律活动','items':[{'title':'午休散步','when':'每天','detail':'舒适步行'}]})
        self.chat('从今天开始执行计划')
        task=product.snapshot(server)['tasks'][0]
        self.output.update(plan=None,reply='这次没完成可以先看看是什么挡住了，身体疲劳时可降低难度。',decision={'action':'none','reason':'反馈'},feedback=[{'task_id':task['task_id'],'status':'done','evidence':'午休散步还没完成'}])
        result=self.chat('午休散步还没完成')
        self.assertEqual(product.snapshot(server)['tasks'][0]['status'],'unreported')
        self.assertIn('是什么挡住了',result['reply'])

    def test_semantic_page_change_without_change_keyword(self):
        self.output['page_changes']=[self.module()]
        result=self.chat('最近总是加班到九点，之前的安排做不到')
        self.assertEqual(len(result['page_updates']),1)
        self.assertEqual(product.snapshot(server)['modules'][0]['title'],'适合你的饮食选择')
        self.assertEqual(product.snapshot(server)['plans'],[])
        self.chat('最近总是加班到九点，之前的安排做不到')
        self.assertEqual(product.snapshot(server)['modules'][0]['version'],1)

    def test_module_revision_and_undo(self):
        self.output['page_changes']=[self.module()];self.chat('晚饭比较晚')
        self.output['page_changes'][0]['body']='换成适合周末的说明';r=self.chat('周末不一样')
        self.assertEqual(product.snapshot(server)['modules'][0]['version'],2)
        product.action(server,{'action':'undo','id':r['client_message_id']})
        self.assertEqual(product.snapshot(server)['modules'][0]['version'],1)

    def test_model_module_alias_and_object_items_are_plain_text(self):
        m=self.module();m.update(id='diet-v1',type='module',items=[{'title':'晚餐','detail':'正常吃饭'}])
        self.output['page_changes']=[m];self.chat('今天晚归')
        saved=product.snapshot(server)['modules'][0]
        self.assertEqual(saved['id'],'diet');self.assertEqual(saved['type'],'text')
        self.assertEqual(saved['items'],['晚餐：正常吃饭'])

    def test_modules_all_or_nothing(self):
        self.output['page_changes']=[self.module(),{'id':'bad','page':'plan','type':'script'}]
        result=self.chat('下班晚了')
        self.assertEqual(result['page_error'],'INVALID_PAGE_CHANGE');self.assertEqual(product.snapshot(server)['modules'],[])

    def test_unsafe_page_content_rejected(self):
        module=self.module();module['body']='每天总热量控制在500千卡'
        self.output['page_changes']=[module];self.chat('我想先看看说明')
        self.assertEqual(product.snapshot(server)['modules'],[])

    def test_photo_alone_not_consumption(self):
        self.output['food_decisions']=[self.food('unknown','')]
        self.chat('看看照片',media_id='food-1')
        self.assertEqual(server.records(),[])
        self.assertEqual(server.load_json(server.MEDIA,[])[0]['food_decision']['status'],'unknown')

    def test_empty_model_food_placeholder_does_not_block_explicit_fact(self):
        media=server.load_json(server.MEDIA,[]);media[0]['review']['record_candidates']=[{'type':'meal','value':{'description':'测试午饭','nutrition':{'kcal':[600,600]}}}];server.save_json(server.MEDIA,media)
        self.output['food_decisions']=[{'media_id':None,'status':None}]
        self.chat('这份还没吃',media_id='food-1');self.assertEqual(server.records(),[])
        self.chat('刚才那个吃了一半')
        self.assertEqual(len(server.records()),1);self.assertEqual(server.records()[0]['value']['nutrition']['kcal'],[300,300])

    def test_planned_then_consumed_then_correction(self):
        self.output['food_decisions']=[self.food('planned','准备吃这个')];self.chat('准备吃这个',media_id='food-1')
        self.assertEqual(server.records(),[])
        self.output['food_decisions']=[self.food('consumed','刚才那个吃了一半')];self.chat('刚才那个吃了一半')
        self.assertEqual(len(server.records()),1);record_id=server.records()[0]['id']
        self.output['food_decisions']=[self.food('consumed','刚才说错了，其实吃完了')];self.chat('刚才说错了，其实吃完了')
        self.assertEqual(len(server.records()),1);self.assertEqual(server.records()[0]['id'],record_id)
        self.output['food_decisions']=[self.food('reference','没吃，是给别人拍的')];self.chat('没吃，是给别人拍的')
        self.assertEqual(server.records(),[]);self.assertEqual(product.snapshot(server)['food_summary']['record_count'],0)

    def test_no_eating_model_contradiction_rejected(self):
        self.output['food_decisions']=[self.food('consumed','没有吃')]
        result=self.chat('没有吃',media_id='food-1')
        self.assertEqual(result['food_error'],'FOOD_REVIEW_REQUIRED');self.assertEqual(server.records(),[])

    def test_model_cannot_reference_other_photo_or_invent_evidence(self):
        self.output['food_decisions']=[self.food('consumed','吃完了')]
        self.chat('仅供参考',media_id='food-1');self.assertEqual(server.records(),[])
        self.chat('吃完了');self.assertEqual(len(server.records()),1)
        self.output['food_decisions'][0]['media_id']='foreign-photo'
        result=self.chat('吃完了');self.assertEqual(result['food_error'],'FOOD_REVIEW_REQUIRED')

    def test_confirm_each_respected(self):
        product.action(server,{'action':'settings','confirm_each':True})
        self.output['food_decisions']=[self.food('consumed','这是刚吃完的午餐')]
        self.chat('这是刚吃完的午餐',media_id='food-1');self.assertEqual(server.records(),[])
        product.action(server,{'action':'food_confirm','id':'food-1'})
        self.assertEqual(len(server.records()),1)
        with self.assertRaises(product.ProductError):product.action(server,{'action':'food_confirm','id':'food-1'})

    def test_nutrition_sum_partial_records(self):
        media=server.load_json(server.MEDIA,[])
        media[0]['review']['record_candidates']=[{'type':'meal','label':'测试午餐',
            'value':{'description':'测试午餐','nutrition':{'kcal':[250,400]}}}]
        server.save_json(server.MEDIA,media)
        self.output['food_decisions']=[self.food('consumed','刚吃完午餐')];self.chat('刚吃完午餐',media_id='food-1')
        rs=server.records();rs.append(server.prepare_record({'type':'beverage','value':{'description':'一杯水'}}))
        summary=workbench.food_summary(rs,product.today())
        self.assertEqual(summary['totals']['kcal']['range'],[250,400]);self.assertEqual(summary['totals']['kcal']['unknown_count'],1)

    def test_invalid_nutrition_rolls_back_food_change(self):
        raw=self.food('consumed','午饭吃了');raw['nutrition']={'kcal':[500,100]}
        self.output['food_decisions']=[raw];self.chat('午饭吃了',media_id='food-1')
        self.assertEqual(server.records(),[]);self.assertNotIn('food_decision',server.load_json(server.MEDIA,[])[0])

    def test_removed_memory_hides_derived_module(self):
        self.output['page_changes']=[self.module()];self.chat('今天体重80公斤')
        self.assertEqual(len(product.snapshot(server)['modules']),1)
        server.save_json(server.RECORDS,[]);self.assertEqual(product.snapshot(server)['modules'],[])

    def test_backup_restore_includes_page_modules(self):
        server.save_json(server.MEDIA,[])
        self.output['page_changes']=[self.module()];self.chat('晚饭比较晚')
        raw,_=server.build_backup()
        w=product.workspace(server);w['modules']=[];server.save_json(server.DATA/'workspace.json',w)
        with patch.object(server,'ROOT',self.data.parent):server.restore_backup(raw)
        self.assertEqual(product.snapshot(server)['modules'][0]['id'],'diet-explanation')
        self.assertEqual(len(product.snapshot(server)['page_history']),1)

    def test_same_message_retry_no_duplicate(self):
        self.output['page_changes']=[self.module()]
        self.output['food_decisions']=[self.food('consumed','午饭吃了')]
        result=self.chat('午饭吃了',media_id='food-1')
        repeated=product.chat(server,{'text':'午饭吃了','media_id':'food-1','conversation_id':'test-conversation','client_message_id':result['client_message_id']})
        self.assertEqual(result,repeated);self.assertEqual(len(server.records()),1)
        self.assertEqual(len(product.snapshot(server)['page_history']),1)

    def test_semantic_plan_revision_no_trigger_word(self):
        plan={'title':'一周安排','goal':'改善习惯','duration_days':7,'items':[{'title':'散步','detail':'舒适速度步行','when':'每天'}]}
        self.output.update(plan=plan,decision={'action':'update','reason':'创建初步方案'})
        self.chat('我35岁，请生成从今天开始执行的计划')
        self.output['plan']=copy.deepcopy(plan);self.output['plan']['items'][0]['detail']='午休时轻松步行'
        self.output['decision']['reason']='晚间没空，利用午休'
        self.chat('晚上一直工作到很晚，午休比较自由')
        plans=product.snapshot(server)['plans'];self.assertEqual(len(plans),2);self.assertEqual(plans[-1]['version'],2)

    def test_repair_does_not_reextract_facts_and_resolves_failure(self):
        self.output['page_changes']=[{**self.module(),'type':'script'}]
        self.chat('我35岁')
        before=product.snapshot(server)
        self.output.update(page_changes=[{**self.module(),'page':'方案','type':'markdown'}],
                           decision={'action':'update','reason':'修复说明'},
                           profile_changes=[{'field':'age','value':60,'evidence':'我60岁'}],
                           record_events=[{'type':'weight','value':{'kg':70},'evidence':'体重70公斤'}])
        result=self.chat('我60岁，体重70公斤',retry_evaluation=True)
        after=product.snapshot(server)
        self.assertEqual(before['profile'],after['profile'])
        self.assertEqual(before['records'],after['records'])
        self.assertEqual(before['plans'],after['plans'])
        self.assertEqual(after['evaluation_jobs'][0]['status'],'resolved')
        self.assertEqual(len(result['page_updates']),1)

    def test_unknown_presentation_with_prose_becomes_text(self):
        self.output['page_changes']=[{**self.module(),'type':'overview_panel'}]
        result=self.chat('看看当前说明')
        self.assertNotIn('page_error',result)
        self.assertEqual(product.snapshot(server)['modules'][0]['type'],'text')

    def test_repair_uses_saved_facts_without_model(self):
        self.output['page_changes']=[{**self.module(),'type':'script'}]
        self.chat('我35岁')
        with patch.object(server,'call_ai',side_effect=AssertionError('repair must be local')):
            result=product.chat(server,{'text':'恢复补充说明','retry_evaluation':True,
                                       'conversation_id':'test-conversation','client_message_id':'local-repair-001'})
        self.assertNotIn('page_error',result)
        self.assertEqual(product.snapshot(server)['evaluation_jobs'][0]['status'],'resolved')

    def test_progress_is_ordered_and_result_is_saved(self):
        stages=[]
        with patch.object(server,'call_ai',return_value=json.dumps(self.output)):
            result=product.chat(server,{'text':'你好','conversation_id':'test-conversation','client_message_id':'stream-message'},stages.append)
        self.assertEqual(stages,['reading','thinking','validating','saving'])
        self.assertEqual(product.workspace(server)['receipts']['stream-message']['result'],result)

    def test_assessment_progress_is_user_level_and_skips_persist(self):
        first=product.snapshot(server)['assessment']
        self.assertEqual(first['stage'],'尚未开始')
        product.action(server,{'action':'assessment_skip','topic':'健康背景'})
        self.output['decision']={'action':'clarify','reason':'继续了解'}
        self.output['reply']='你平时什么时候睡觉？'
        self.chat('我35岁')
        state=product.snapshot(server)['assessment']
        self.assertEqual(state['stage'],'逐步了解')
        self.assertIn('健康背景',state['skipped_topics'])
        self.assertEqual(state['next_question'],'你平时什么时候睡觉？')
        self.assertEqual(next(x for x in state['topics'] if x['title']=='健康背景')['status'],'skipped')

    def test_missing_decision_is_incomplete_not_a_failed_page_write(self):
        self.output.pop('decision')
        result=self.chat('记一下我今天很忙')
        jobs=product.snapshot(server)['evaluation_jobs']
        self.assertEqual(result['workflow_warning'],'MODEL_MISSING_WORKBENCH_DECISION')
        self.assertEqual(len(jobs),1)
        self.assertEqual(jobs[0]['status'],'incomplete')
        self.assertNotIn('已保留本次更新失败状态，可从对话重试',result['receipts'])
        self.assertEqual(jobs[0]['trigger_message_id'],result['client_message_id'])


if __name__=='__main__':unittest.main()
