import ast
import copy
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
import coach_actions
import product
import server
import test_coach_review


class DeliveryTests(unittest.TestCase):
    setUp=test_coach_review.ReviewTests.setUp
    tearDown=test_coach_review.ReviewTests.tearDown
    fixture=test_coach_review.ReviewTests.fixture

    def test_reject_numeric_nutrients_but_keep_recipe_reference_weights(self):
        for text in ('每天1800千卡','蛋白质100克','脂肪占30%','80g protein','一千八百大卡'):
            with self.subTest(text=text):
                self.assertTrue(coach_actions.has_unverified_nutrients(text))
                with self.assertRaises(product.ProductError):
                    product.normalize_plan({'title':'行动','goal':'观察','items':[{'title':'晚餐','detail':text}]},'明天',{},None)
        self.assertFalse(coach_actions.has_unverified_nutrients('1人1餐食谱参考：豆腐100克，重量不是实际摄入'))
        safe,removed=coach_actions.redact_unverified_nutrients('睡眠可能影响精力。每天1800千卡不作为建议。你最难坚持哪一餐？')
        self.assertTrue(removed)
        self.assertIn('睡眠可能影响精力',safe)
        self.assertNotIn('1800千卡',safe)
        self.assertIn('哪一餐',safe)

    def test_replacement_is_selected_item_only_future_only_and_audited(self):
        p,w=self.fixture(['unreported']*7)
        item=w['plans'][0]['items'][0]
        item['alternatives']='用语音记一句感受'
        item['meal_options']={'cook':{'dish':'旧菜谱'}}
        server.save_json(server.DATA/'workspace.json',w)
        before=copy.deepcopy(w)
        request={'action':'review_plan','id':p['id'],'version':1,'choice':'replace','item_id':item['id'],'note':'打字不方便'}
        product.action(server,request)
        state=product.workspace(server);new=state['plans'][-1]
        self.assertGreater(new['start_date'],product.today())
        self.assertEqual(new['items'][0]['detail'],'用语音记一句感受')
        self.assertEqual(new['items'][0]['meal_options'],{})
        self.assertEqual(new['items'][0]['alternatives'],'')
        self.assertEqual(new['items'][1],before['plans'][0]['items'][1])
        self.assertEqual(new['actions'],new['items'])
        self.assertEqual(state['plans'][0]['items'],before['plans'][0]['items'])
        self.assertEqual(state['feedback'],before['feedback'])
        self.assertEqual(state['reviews'][0]['note'],'打字不方便')
        with self.assertRaises(product.ProductError):product.action(server,request)

    def test_bad_replacement_does_not_write(self):
        p,w=self.fixture(['partial']*7)
        w['plans'][0]['items'][0]['alternatives']='每天摄入1800千卡'
        server.save_json(server.DATA/'workspace.json',w)
        for item_id in ('not-an-item',p['items'][0]['id']):
            with self.assertRaises(product.ProductError):
                product.action(server,{'action':'review_plan','id':p['id'],'version':1,'choice':'replace','item_id':item_id})
            self.assertEqual(product.workspace(server),w)

    def test_unsafe_alternative_is_rejected_before_plan_save(self):
        with self.assertRaises(product.PlanSafetyError):
            product.normalize_plan({'title':'行动','goal':'记录','items':[{'title':'晚餐记录','detail':'记一句感受','alternatives':'连续三天不吃饭'}]},'明天',{},None)

    def test_android_allowlist_covers_all_local_python_imports(self):
        root=Path(__file__).resolve().parents[1]
        tree=ast.parse((root/'android/standalone/prepare.py').read_text('utf-8'))
        files=next(ast.literal_eval(node.value) for node in tree.body if isinstance(node,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='files' for t in node.targets))
        self.assertIn('coach_actions.py',files);self.assertIn('coach_review.py',files)
        for filename in files:
            self.assertTrue((root/filename).is_file(),filename)
            if not filename.endswith('.py'):continue
            for node in ast.walk(ast.parse((root/filename).read_text('utf-8-sig'))):
                names=[alias.name for alias in node.names] if isinstance(node,ast.Import) else [node.module or ''] if isinstance(node,ast.ImportFrom) else []
                for name in names:
                    local=name.split('.')[0]+'.py'
                    if (root/local).is_file():self.assertIn(local,files,filename+' requires '+local)
        with tempfile.TemporaryDirectory(prefix='coach-package-') as folder:
            package=Path(folder)
            script=package/'android/standalone/prepare.py'
            script.parent.mkdir(parents=True)
            shutil.copyfile(root/'android/standalone/prepare.py',script)
            for filename in files:shutil.copyfile(root/filename,package/filename)
            icon=package/'android/res/drawable/icon.xml';icon.parent.mkdir(parents=True)
            shutil.copyfile(root/'android/res/drawable/icon.xml',icon)
            # Preparation now verifies the shipped offline speech dependencies.
            for relative in ('app/src/main/assets/voice','app/libs'):
                shutil.copytree(root/'android/standalone'/relative,script.parent/relative)
            built=subprocess.run([sys.executable,str(script)],cwd=package,capture_output=True,text=True,timeout=20)
            self.assertEqual(built.returncode,0,built.stderr)
            engine=package/'android/standalone/app/src/main/assets/engine'
            self.assertEqual(sorted(p.name for p in engine.iterdir()),sorted(files))
            env={**os.environ,'PYTHONPATH':str(engine)}
            loaded=subprocess.run([sys.executable,'-c','import server, product, coach_review, coach_actions; print("engine imports OK")'],cwd=engine,env=env,capture_output=True,text=True,timeout=20)
            self.assertEqual(loaded.returncode,0,loaded.stderr)
