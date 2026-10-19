import unittest
import test_workbench
import product
import server
import intake
import workbench
import consultation

class IntakeTests(unittest.TestCase):
    tearDown=test_workbench.WorkbenchTests.tearDown
    chat=test_workbench.WorkbenchTests.chat
    def setUp(self):
        test_workbench.WorkbenchTests.setUp(self)
        server.save_json(server.DATA/'workspace.json',{})
        self.output.update(reply='计划已生成',decision={'action':'update','reason':'模型尝试直接出方案'},
            plan={'title':'习惯计划','goal':'规律生活','items':[{'title':'早餐','when':'每天 07:00','detail':'按偏好正常进餐'}]})

    def test_short_answers_and_model_cannot_override_them(self):
        self.assertIsNone(self.chat('先完善档案，再帮我制定减脂计划')['plan'])
        self.output['profile_changes']=[{'field':'age','value':80,'evidence':'35'}]
        self.chat('35');self.output['profile_changes']=[]
        self.chat('男');self.chat('175');self.chat('160斤')
        snap=product.snapshot(server)
        self.assertEqual(snap['profile']['age'],35)
        self.assertEqual(snap['profile']['sex'],'男')
        self.assertEqual(snap['profile']['height_cm'],175)
        self.assertEqual(snap['records'][0]['value']['kg'],80)
        self.assertEqual(snap['plans'],[])
        self.assertIn('确诊疾病',product.workspace(server)['assessment_state']['next_question']['text'])

    def test_explicit_medication_is_separate_from_health_history(self):
        self.assertEqual(intake.explicit_medication('目前就吃优甲乐')['medications'],['优甲乐'])
        self.assertEqual(intake.explicit_medication('正在服用降压药')['medications'],['降压药'])
        for text in ('没有服用降压药','如果服用降压药会怎样？','朋友服用降压药','早上吃大饼鸡排'):
            self.assertEqual(intake.explicit_medication(text),{})
        self.output.update(reply='以前或目前有确诊疾病、近期不适吗？',decision={'action':'clarify'},plan=None)
        self.chat('我想减重，请先了解我')
        self.chat('有膝盖旧伤，正在服用降压药。')
        self.assertEqual(product.snapshot(server)['profile']['medications'],['降压药'])

    def complete(self):
        profile={k:'已明确描述的实际情况' for k in intake.QUESTIONS if k!='weight_kg'}
        profile.update(breakfast_habit='两个鸡蛋一杯牛奶',lunch_habit='一碗米饭配鸡肉蔬菜',dinner_habit='一碗面条配青菜')
        profile.update(age=35,sex='男',height_cm=175,conditions=['没有'],medications=['没有'],allergies=['没有'],surgeries=['没有'],sleep_schedule='凌晨2点睡，10点起',work_schedule='12点上班20点下班',meal_schedule='起床吃早餐，16点午餐，下班晚餐')
        server.save_json(server.PROFILE,profile)
        record=server.prepare_record({'type':'weight','value':{'kg':80}})
        record.update(created_at=product.now(),occurred_at=product.now())
        server.save_json(server.RECORDS,[record])

    def test_default_today_checks_remaining_meals_and_relative_time(self):
        self.complete();first=self.chat('请生成减脂计划')
        self.assertIsNone(first['plan']);self.assertIn('核对',first['reply'])
        asked=self.chat('确认',mid='confirmed-default-start')
        self.assertIsNone(asked['plan']);self.assertIn('下一餐',asked['reply'])
        r=self.chat('早餐已经吃过，下一餐是午餐')
        self.assertEqual(r['plan']['start_date'],product.today())
        self.assertEqual(r['plan']['items'][0]['excluded_dates'],[product.today()])
        self.assertNotIn('07:00',r['plan']['items'][0]['when'])
        self.assertIn('12点',r['plan']['routine_basis']['work_schedule'])

    def test_today_requires_intake_and_does_not_repeat_eaten_meal(self):
        self.complete()
        first=self.chat('请生成今天开始执行的计划')
        self.assertIsNone(first['plan']);self.assertIn('已经吃过',first['reply'])
        self.assertNotIn('请重试',first['reply'])
        second=self.chat('早餐已吃过面包，接下来还有午餐和晚餐，凌晨2点睡')
        self.assertIsNotNone(second['plan'])
        self.assertEqual(product.snapshot(server)['tasks'],[])
        self.assertEqual(second['plan']['items'][0]['excluded_dates'],[product.today()])

    def test_no_opportunity_today_does_not_schedule_catchup(self):
        self.complete();self.chat('请制定今天开始的计划')
        r=self.chat('今天没有合适机会执行，已经吃过今天的餐了')
        self.assertIsNotNone(r['plan'])
        self.assertEqual(r['plan']['items'][0]['excluded_dates'],[product.today()])
        self.assertIsNone(r['plan']['start_guide'])
        self.assertIn('今天没有合适的执行时段',r['reply'])

    def test_user_can_move_first_action_to_tomorrow_after_today_question(self):
        self.complete();self.chat('请制定今天开始的计划')
        r=self.chat('今天没有合适机会执行，明天再按计划做')
        self.assertIsNotNone(r['plan'])
        self.assertEqual(r['plan']['start_date'],(product.datetime.now().date()+product.timedelta(days=1)).isoformat())

    def test_unknowns_skip_and_new_conversation_do_not_guess(self):
        self.chat('先完善档案，再制定计划');self.chat('不知道')
        self.assertNotIn('age',product.snapshot(server)['profile'])
        self.chat('跳过');self.assertIn('age',product.workspace(server)['interview']['skipped'])
        self.assertEqual(intake.short_answer('age','如果35岁呢？'),{})
        self.assertEqual(intake.short_answer(None,'35'),{})
        self.assertEqual(intake.short_answer('conditions','好的'),{})

    def test_unrequested_plan_is_not_created(self):
        self.complete();r=self.chat('今天感觉挺好')
        self.assertIsNone(r['plan']);self.assertEqual(product.snapshot(server)['plans'],[])

    def test_ordinary_record_does_not_start_interview_and_opt_out_stops_it(self):
        self.chat('今天体重80公斤，请记录，不要制定计划')
        self.assertNotIn('asked_field',product.workspace(server)['sessions']['test-conversation'])
        self.chat('帮我制定减脂计划')
        self.chat('暂停建档，今天只记录体重81公斤，不要制定计划')
        session=product.workspace(server)['sessions']['test-conversation']
        self.assertNotIn('asked_field',session);self.assertNotIn('interview_request',session)

    def test_confirmed_absence_is_known_and_legacy_plan_not_complete(self):
        a=workbench.assessment({'conditions':['没有'],'medications':['没有'],'allergies':['没有'],'surgeries':['没有']},[],[{}])
        self.assertEqual(next(t for t in a['topics'] if t['title']=='健康背景')['status'],'known')
        self.assertNotEqual(a['stage'],'持续跟进')

    def test_explicit_preliminary_plan_has_unknowns(self):
        r=self.chat('资料还没齐，请先给初步计划')
        self.assertIsNone(r['plan']);self.assertIn('下一餐',r['reply'])
        r=self.chat('今天早餐已吃，下一餐午餐')
        self.assertIsNotNone(r['plan']);self.assertIn('年龄',r['plan']['unknowns'])

    def test_existing_plan_does_not_prevent_repairing_missing_profile(self):
        w=product.workspace(server)
        w['plans']=[product.normalize_plan(self.output['plan'],'今天',w,None)]
        server.save_json(server.DATA/'workspace.json',w)
        r=self.chat('我想继续完善档案，请先了解我的情况')
        self.assertIsNone(r['plan']);self.assertIn('年龄',r['reply'])
        self.chat('35');self.assertEqual(product.snapshot(server)['profile']['age'],35)
        self.assertEqual(len(product.snapshot(server)['plans']),1)

    def test_undo_restores_question_so_corrected_short_answer_is_not_misfiled(self):
        self.chat('先完善档案，再生成减脂计划');r=self.chat('35')
        product.action(server,{'action':'undo','id':r['client_message_id']})
        self.assertEqual(product.workspace(server)['sessions']['test-conversation']['asked_field'],'age')
        self.chat('36');self.assertEqual(product.snapshot(server)['profile']['age'],36)

    def test_answer_does_not_rewrite_another_field_or_create_spurious_conflict(self):
        self.complete();profile=server.load_json(server.PROFILE,{})
        profile.pop('activity_baseline');server.save_json(server.PROFILE,profile)
        self.chat('先完善档案，再生成计划')
        self.output['profile_changes']=[{'field':'occupation','value':'久坐','evidence':'久坐'}]
        self.chat('主要久坐，每周散步一次20分钟')
        snap=product.snapshot(server)
        self.assertEqual(snap['profile']['occupation'],profile['occupation'])
        self.assertIn('久坐',snap['profile']['activity_baseline'])
        self.assertFalse(snap['pending'])

    def test_partial_first_day_skips_past_slots_and_no_broken_time_ranges(self):
        self.assertTrue(intake.already_passed_today({'title':'每周称重','when':'每周一上午'},'',21))
        self.assertTrue(intake.already_passed_today({'title':'每日饮水','when':'全天分散'},'',21))
        self.assertFalse(intake.already_passed_today({'title':'轻松散步','when':'下班后'},'',21))
        self.assertTrue(intake.already_passed_today({'title':'早餐','when':'起床后'},'今天已吃过早餐，下一餐是午餐',21))
        self.assertTrue(intake.already_passed_today({'title':'午餐','when':'午餐时'},'今天已吃两餐，下一餐是晚餐',21))
        self.assertEqual(intake.relative_when('下班到家后22:00-22:30','散步'),'下班到家后')
        self.assertNotIn('14-',intake.relative_when('每天下午14-16点之间','加餐'))
        self.assertIn('exercise_despite_discomfort',product.plan_safety_findings({'items':[{'title':'散步','minimum':'身体不适可减量但不停止'}]}))
        self.assertEqual(product.plan_safety_findings({'items':[{'title':'散步','minimum':'身体不适时不要继续运动'}]}),[])

    def test_legacy_numbered_answers_save_age_without_model_extraction(self):
        server.save_json(server.CONVERSATIONS,[{'id':'test-conversation','messages':[{'role':'assistant','text':'1. 年龄多大？\n2. 做过什么手术？\n3. 早餐一般吃什么？'}]}])
        self.chat('1 38 2 18年胆囊切除，现在吃油腻胃不舒服 3 一碗面条')
        snap=product.snapshot(server)
        self.assertEqual(snap['profile']['age'],38)
        self.assertIn('胆囊',str(snap['profile']['surgeries']))
        self.assertIn('面条',snap['profile']['breakfast_habit'])
        self.assertNotIn('lunch_habit',snap['profile'])

    def test_legacy_single_question_bare_age_and_refresh(self):
        server.save_json(server.CONVERSATIONS,[{'id':'test-conversation','messages':[{'role':'assistant','text':'你今年多大？'}]}])
        self.chat('38');self.assertEqual(product.snapshot(server)['profile']['age'],38)
        self.assertEqual(server.load_json(server.PROFILE,{})['age'],38)

    def test_meal_example_requires_portion_and_elaboration_is_saved(self):
        self.complete();profile=server.load_json(server.PROFILE,{})
        profile.pop('breakfast_habit');server.save_json(server.PROFILE,profile)
        self.chat('先完善档案，再制定计划');r=self.chat('面条')
        self.assertIsNone(r['plan']);self.assertIn('多少',r['reply'])
        r=self.chat('一碗，配一个鸡蛋，不喝饮料')
        self.assertIsNone(r['plan']);self.assertIn('下一餐',r['reply'])
        r=self.chat('今天早餐已吃，下一餐午餐')
        self.assertIsNotNone(r['plan'])
        self.assertIn('面条',product.snapshot(server)['profile']['breakfast_habit'])
        self.assertIn('一碗',product.snapshot(server)['profile']['breakfast_habit'])
        self.assertFalse(product.snapshot(server)['pending'])

    def test_ambiguous_surgery_and_bare_number_not_guessed(self):
        self.assertFalse(intake.known({'surgeries':'18年切除的，现在吃油腻不舒服'},'surgeries'))
        self.assertEqual(intake.contextual_answers('你的年龄和身高是多少？','38'),{})

    def test_history_recovery_proposes_missing_basics_without_overwriting(self):
        server.save_json(server.CONVERSATIONS,[{'id':'old-conversation','messages':[{'role':'assistant','text':'你今年多大？'},{'id':'old-user-msg','role':'user','text':'38'}]}])
        product.action(server,{'action':'recover_profile'})
        snap=product.snapshot(server);self.assertNotIn('age',snap['profile'])
        pending=next(x for x in snap['pending'] if x['field']=='age')
        self.assertEqual(pending['value'],38)
        product.action(server,{'action':'pending','id':pending['id'],'accept':True})
        self.assertEqual(product.snapshot(server)['profile']['age'],38)

    def test_plan_keeps_natural_reply_and_optional_feedback(self):
        self.complete();self.chat('请制定减脂计划')
        self.chat('确认',mid='confirmed-start-guide')
        self.output['reply']='可以从你现在能做到的一小步开始，执行后再看饥饿感。'
        r=self.chat('今天早餐吃过，下一餐午餐')
        self.assertIn('可以从你现在能做到的一小步开始',r['reply'])
        self.assertIn('已保存',r['reply'])
        self.assertNotIn('起床后先告诉我',r['reply'])
        self.assertEqual(r['plan']['start_guide'],None)

    def test_explicit_tomorrow_keeps_date_and_guide_uses_plan_action(self):
        self.complete();self.chat('请制定明天开始的减脂计划')
        r=self.chat('确认')
        self.assertEqual(r['plan']['start_date'],(product.datetime.now().date()+product.timedelta(days=1)).isoformat())
        self.assertEqual(r['plan']['start_guide']['kind'],'adaptive')
        self.assertIn('早餐',r['plan']['start_guide']['steps'][0])
        self.assertNotIn('早餐前告诉我',str(r['plan']['start_guide']))

    def test_start_guide_uses_action_due_on_start_date(self):
        start=product.today()
        plan={'start_date':start,'items':[
            {'title':'周末散步','minimum':'短暂走动','dates':['2099-01-01']},
            {'title':'下一餐观察','minimum':'记下饥饿感','dates':[]},
        ]}
        self.assertIn('下一餐观察',product.optional_start_guide(plan)['steps'][0])
        plan['items'][1]['excluded_dates']=[start]
        self.assertIsNone(product.optional_start_guide(plan))

    def test_meal_question_rejects_unverified_menu_and_portions(self):
        self.output.update(plan=None,reply='晚上九点建议选300克清蒸鱼。按评分和月销量找附近能送达的店。'+'多看几家。'*50)
        r=self.chat('我上夜班，凌晨一点下班，想点外卖，不想做鱼，手头没有菜单。现在吃什么？')
        self.assertIsNone(r['plan'])
        self.assertIn('凌晨下班',r['reply'])
        self.assertIn('避开鱼',r['reply'])
        self.assertIn('没有真实菜单',r['reply'])
        self.assertNotIn('300克',r['reply'])
        self.assertNotIn('评分',r['reply'])

    def test_short_takeout_dish_without_menu_is_not_presented_as_available(self):
        self.output.update(plan=None,reply='附近有清蒸鲤鱼，直接点这家。')
        r=self.chat('现在想点外卖晚餐，没有菜单，吃什么？')
        self.assertIn('没有真实菜单',r['reply'])
        self.assertNotIn('附近有',r['reply'])
        self.assertNotIn('鲤鱼',r['reply'])

    def test_plan_takeout_without_menu_is_downgraded_to_search_direction(self):
        w=product.workspace(server)
        plan=product.normalize_plan({'title':'晚餐试行','goal':'按实际可得餐食选择','items':[{
            'title':'晚餐外卖','detail':'按实际菜单选择','meal_options':{
                'takeout':{'dish':'附近清蒸鲤鱼','search':'清蒸鲤鱼','ordering':'直接点这家。'}}}]},
            '今天想点外卖，没有菜单',w,None)
        option=plan['items'][0]['meal_options']['takeout']
        self.assertEqual(option['availability'],'unverified')
        self.assertEqual(option['dish'],'待核对的外卖类别')
        self.assertNotIn('鲤鱼',option['search'])

    def test_plan_day_three_routes_as_review(self):
        self.assertEqual(consultation.decision_kind('计划已经到第三天了，昨晚加班没散步，今天晚餐只能点外卖',has_plan=True),'review')

    def test_weight_goal_long_questionnaire_becomes_one_useful_question(self):
        self.output.update(plan=None,reply='请先回答：\n- 年龄？\n- 性别？\n- 身高？\n- 三餐吃什么？\n- 作息怎样？')
        r=self.chat('我目前体重200斤，想减肥减到150斤。请先了解我，再制定方案。')
        self.assertIsNone(r['plan'])
        self.assertIn('长期目标',r['reply'])
        self.assertIn('长期目标',r['reply'])
        self.assertIn('年龄',r['reply'])
        self.assertEqual(r['reply'].count('？'),1)

    def test_weight_followup_does_not_approve_goal_or_repeat_questionnaire(self):
        self.output.update(plan=None,reply='请先说身高？')
        self.chat('我目前体重200斤，想减肥减到150斤。请先了解我，再制定方案。')
        self.output['reply']='172cm、100kg，减到75kg属于合理范围。你今年多大？性别是？'
        r=self.chat('172厘米')
        self.assertIn('年龄',r['reply'])
        self.assertNotIn('属于合理范围',r['reply'])
        self.assertEqual(r['reply'].count('？'),1)

    def test_weight_assessment_resumes_after_failed_first_response(self):
        workspace=product.workspace(server)
        workspace['sessions']['test-conversation']={
            'interview_request':True,
            'request':'我目前体重200斤，想减肥减到150斤。你先告诉我现在应该怎么开始。',
        }
        server.save_json(server.DATA/'workspace.json',workspace)
        self.output.update(plan=None,reply='每天快走45分钟，六个月可以达到目标。请说年龄？性别？三餐？')
        r=self.chat('172厘米')
        self.assertIsNone(r['plan'])
        self.assertIn('年龄',r['reply'])
        self.assertNotIn('六个月',r['reply'])
        self.assertEqual(r['reply'].count('？'),1)

    def test_model_cannot_invent_portions_or_assign_food_to_unmentioned_meal(self):
        self.output.update(plan=None,profile_changes=[{'field':'breakfast_habit','value':'早餐一碗面条100克','evidence':'早餐面条'},
            {'field':'lunch_habit','value':'午餐一碗面条','evidence':'早餐面条'}])
        self.chat('我通常早餐面条')
        profile=product.snapshot(server)['profile']
        self.assertEqual(profile['breakfast_habit'],'早餐面条')
        self.assertFalse(intake.known(profile,'breakfast_habit'));self.assertNotIn('lunch_habit',profile)

if __name__=='__main__':unittest.main()
