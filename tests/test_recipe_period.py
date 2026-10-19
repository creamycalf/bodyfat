import copy
import unittest
from datetime import date, timedelta
import test_workbench
import product
import server


class RecipePeriodTests(unittest.TestCase):
    setUp=test_workbench.WorkbenchTests.setUp
    tearDown=test_workbench.WorkbenchTests.tearDown
    chat=test_workbench.WorkbenchTests.chat

    def draft(self):
        self.output.update(decision={'action':'update','reason':'建立计划'},plan={'title':'饮食计划','goal':'规律吃饭','items':[{'title':'午餐','when':'每天'}]})
        self.chat('从今天开始执行计划')
        p=product.snapshot(server)['plans'][0]
        self.output.update(plan=None,decision={'action':'none'},recipe_option={'dish':'蒸饭配鸡蛋','ingredients':'米饭一碗、鸡蛋一个','steps':'1. 加热米饭。2. 鸡蛋蒸熟后搭配。'})
        return self.chat('查看做法，不要修改计划',plan_help={'id':p['id'],'version':p['version'],'item_id':p['items'][0]['id'],'mode':'cook'})

    def test_save_refresh_and_duplicate_preserve_health_and_tasks(self):
        result=self.draft();before=product.snapshot(server)
        self.assertEqual(before['plans'][0]['items'][0]['meal_options'],{})
        payload={'action':'recipe_save','id':result['client_message_id'],'option':{'dish':'客户端篡改'}}
        product.action(server,payload);after=product.snapshot(server)
        self.assertEqual(after['plans'][0]['items'][0]['meal_options']['cook'],result['recipe_draft']['option'])
        for key in ('profile','records','feedback'):self.assertEqual(before[key],after[key])
        self.assertEqual([(t['task_id'],t['status']) for t in before['tasks']],[(t['task_id'],t['status']) for t in after['tasks']])
        product.action(server,payload)
        self.assertEqual(after,product.snapshot(server))
        self.assertTrue(after['conversations'][0]['messages'][-1]['result']['recipe_draft']['saved_at'])

    def test_stale_profile_and_old_plan_rejected(self):
        result=self.draft();payload={'action':'recipe_save','id':result['client_message_id']}
        product.action(server,{'action':'profile','fields':{'allergies':'鸡蛋'}})
        with self.assertRaises(product.ProductError):product.action(server,payload)
        w=product.workspace(server);w['plans'][0]['status']='replaced';server.save_json(server.DATA/'workspace.json',w)
        with self.assertRaises(product.ProductError):product.action(server,payload)

    def test_incomplete_recipe_not_offered_for_save(self):
        result=self.draft();d=result['recipe_draft'];self.output['recipe_option']['steps']='待补充'
        response=self.chat('再看做法',plan_help={'id':d['plan_id'],'version':d['version'],'item_id':d['item_id'],'mode':'cook'})
        self.assertNotIn('recipe_draft',response)
        self.assertIn('未返回完整的可保存食谱',response['reply'])

    def test_recipe_request_contract_includes_savable_fields(self):
        result=self.draft()
        contract=self.prompt[-1]['content'].split('【本轮食谱输出约定】',1)[1]
        self.assertIn('"recipe_option"',contract)
        for field in ('dish','ingredients','steps'):
            self.assertIn('"'+field+'"',contract)
        d=result['recipe_draft']
        self.chat('查看外卖建议',plan_help={'id':d['plan_id'],'version':d['version'],'item_id':d['item_id'],'mode':'takeout'})
        contract=self.prompt[-1]['content'].split('【本轮食谱输出约定】',1)[1]
        for field in ('dish','search','ordering'):
            self.assertIn('"'+field+'"',contract)

    def test_older_draft_cannot_overwrite_newer_saved_recipe(self):
        first=self.draft();d=first['recipe_draft'];self.output['recipe_option']['dish']='新做法'
        second=self.chat('重新看做法',plan_help={'id':d['plan_id'],'version':d['version'],'item_id':d['item_id'],'mode':'cook'})
        product.action(server,{'action':'recipe_save','id':second['client_message_id']})
        with self.assertRaises(product.ProductError):product.action(server,{'action':'recipe_save','id':first['client_message_id']})

    def test_takeout_saves_only_takeout_option(self):
        first=self.draft();d=first['recipe_draft']
        product.action(server,{'action':'recipe_save','id':first['client_message_id']})
        self.output['recipe_option']={'dish':'米饭蔬菜鸡蛋','search':'家常菜 蒸蛋','ordering':'少油，酱汁单放'}
        second=self.chat('查看外卖建议',plan_help={'id':d['plan_id'],'version':d['version'],'item_id':d['item_id'],'mode':'takeout'})
        product.action(server,{'action':'recipe_save','id':second['client_message_id']})
        options=product.snapshot(server)['plans'][0]['items'][0]['meal_options']
        self.assertEqual(options['cook'],d['option']);self.assertEqual(options['takeout'],self.output['recipe_option'])

    def test_local_revision_keeps_end_and_review_but_explicit_cycle_can_change(self):
        today=date.today();raw={'title':'活动','goal':'规律','duration_days':7,'items':[{'title':'午休散步','when':'每天'}]}
        old=product.normalize_plan(raw,'今天开始',{},None)
        old.update(start_date=(today-timedelta(days=1)).isoformat(),end_date=(today+timedelta(days=5)).isoformat(),review_date=(today+timedelta(days=6)).isoformat())
        revised=product.normalize_plan(raw,'把散步改到午休',{},None,old)
        self.assertEqual(revised['end_date'],old['end_date']);self.assertEqual(revised['review_date'],old['review_date'])
        renewed=product.normalize_plan(raw,'从今天重新开始一周',{},None,old)
        self.assertEqual(renewed['end_date'],(today+timedelta(days=6)).isoformat())
        temporary=product.normalize_plan(raw,'明天改成散步',{},None,old)
        self.assertEqual(temporary['start_date'],temporary['end_date'])

    def test_future_plan_does_not_start_early_on_local_edit(self):
        raw={'title':'活动','goal':'规律','items':[{'title':'散步','when':'每天'}]}
        old=product.normalize_plan(raw,'三天后开始',{},None)
        old['start_date']=(date.today()+timedelta(days=3)).isoformat()
        revised=product.normalize_plan(raw,'改到午休',{},None,old)
        self.assertEqual(revised['start_date'],old['start_date']);self.assertEqual(revised['end_date'],old['end_date'])

    def test_negated_extension_keeps_period_and_tomorrow_new_cycle_is_not_one_day(self):
        raw={'title':'活动','goal':'规律','duration_days':7,'items':[{'title':'散步','when':'每天'}]}
        old=product.normalize_plan(raw,'今天开始',{},None)
        old['end_date']=(date.today()+timedelta(days=3)).isoformat()
        for text in ('把散步改到午休，不要延期2天','不延长，只改散步时间','不用重新开始一周，把活动改简单'):
            with self.subTest(text=text):
                result=product.normalize_plan(raw,text,{},None,old)
                self.assertEqual(result['end_date'],old['end_date'])
                self.assertEqual(result['start_date'],old['start_date'])
        result=product.normalize_plan(raw,'明天开始新一轮，执行一周',{},None,old)
        self.assertEqual(result['end_date'],(date.today()+timedelta(days=7)).isoformat())
