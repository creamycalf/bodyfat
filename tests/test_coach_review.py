import unittest
from datetime import timedelta
import product
import server
import coach_review
import test_workbench


class ReviewTests(unittest.TestCase):
    setUp=test_workbench.WorkbenchTests.setUp
    tearDown=test_workbench.WorkbenchTests.tearDown

    def fixture(self,statuses):
        w=product.workspace(server)
        p=product.normalize_plan({'title':'阶段观察','goal':'建立记录','items':[
            {'title':'记下晚餐感受','detail':'记录餐食与感受','minimum':'只记一句感受'},
            {'title':'睡前记录','detail':'记下睡眠准备'}]},'今天',w,None)
        p.update(status='active',start_date=(product.datetime.now().date()-timedelta(days=7)).isoformat())
        w['plans']=[p]
        for offset,status in enumerate(statuses,1):
            day=(product.datetime.now().date()-timedelta(days=offset)).isoformat()
            tasks=product.tasks_for(w,day)
            for task in tasks:
                if status!='unreported':product.set_feedback(w,task['task_id'],status)
        server.save_json(server.DATA/'workspace.json',w)
        return p,w

    def test_seven_days_missing_is_unknown(self):
        p,w=self.fixture(['done','unreported','unreported','unreported','unreported','unreported','unreported'])
        r=coach_review.summarize(p,product.tasks_for,w,product.today())
        self.assertEqual(r['expected'],14)
        self.assertEqual(r['counts']['unreported'],12)
        self.assertEqual(r['counts']['skipped'],0)
        self.assertEqual(r['decision'],'assess')
        with self.assertRaises(product.ProductError):product.action(server,{'action':'review_plan','id':p['id'],'version':1,'choice':'simplify'})

    def test_minimum_choice_versions_future_only_and_preserves_feedback(self):
        p,w=self.fixture(['partial']*7)
        before=list(w['feedback'])
        product.action(server,{'action':'review_plan','id':p['id'],'version':1,'choice':'simplify'})
        state=product.workspace(server);new=state['plans'][-1]
        self.assertEqual(new['version'],2)
        self.assertGreater(new['start_date'],product.today())
        self.assertEqual(new['items'][0]['detail'],'只记一句感受')
        self.assertEqual(new['items'][1]['detail'],p['items'][1]['detail'])
        self.assertEqual(state['feedback'],before)
        self.assertEqual(state['reviews'][0]['choice'],'simplify')
        self.assertEqual(state['assessment_state']['stage'],'review')
        with self.assertRaises(product.ProductError):product.action(server,{'action':'review_plan','id':p['id'],'version':1,'choice':'simplify'})

    def test_maintain_preserves_plan_and_records_review_once(self):
        p,w=self.fixture(['done']*7)
        product.action(server,{'action':'review_plan','id':p['id'],'version':1,'choice':'maintain'})
        state=product.workspace(server)
        self.assertEqual(len(state['plans']),1)
        self.assertEqual(state['plans'][0],p)
        self.assertEqual(state['reviews'][0]['decision'],'maintain')

    def test_review_keeps_missing_context_unknown_and_saves_user_feedback(self):
        p,w=self.fixture(['done']*7)
        card=coach_review.summarize(p,product.tasks_for,w,product.today(),[])
        self.assertEqual(card['observations']['weight']['count'],0)
        self.assertIn('饥饿感',card['unknowns'])
        product.action(server,{'action':'review_plan','id':p['id'],'version':1,'choice':'maintain',
            'hunger':'hungry','difficulty':'下班后经常太饿','note':'希望下周观察晚餐前感受'})
        saved=product.workspace(server)['reviews'][0]
        self.assertEqual(saved['hunger'],'hungry')
        self.assertEqual(saved['difficulty'],'下班后经常太饿')
        self.assertEqual(saved['result_version'],1)
        self.assertIn('继续观察',saved['change_explanation'])
