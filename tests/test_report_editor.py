"""Report revision, provenance, arithmetic and explicit intake tests."""
import copy
import unittest

import product
import server
import test_workbench
import nutrition_reports
import food_catalog


class ReportEditorTests(unittest.TestCase):
    tearDown=test_workbench.WorkbenchTests.tearDown

    def setUp(self):
        test_workbench.WorkbenchTests.setUp(self)
        media=server.load_json(server.MEDIA,[])
        media[0]['review']['report']=nutrition_reports.food_report({'foods':[{'name':'原米饭',
            'grams':[180,220],'per_100g':{'kcal':[100,120]}}]})
        media[0]['review']['record_candidates']=[{'type':'meal','label':'原米饭',
            'value':{'description':'原米饭','nutrition':{'kcal':[180,264]}}}]
        server.save_json(server.MEDIA,media)

    def request(self, **changes):
        foods=[{'name':'米饭','grams':[200,200],'per_100g':{'kcal':[100,100],
                'protein_g':[2,2],'carbs_g':[20,20],'fat_g':[1,1]},
                'source_kind':'user_label','source_id':'测试标签-米饭','source_version':'本次核对',
                'weight_basis':'熟重','edible_basis':'可食部分','included':True},
               {'name':'整道菜示例','grams':[300,300],'per_100g':{'kcal':[150,150]},
                'included':False}]
        return {'id':'food-1','servings':2,'foods':foods,'eaten_servings':'',
                'confirm_consumption':False,'date':product.today(),**changes}

    def commit(self, request):
        preview=product.action(server,{'action':'report_preview',**request})
        return preview,product.action(server,{'action':'report_commit',**request,'token':preview['token']})

    def test_preview_is_read_only_and_commit_recalculates_with_sources(self):
        before=product.snapshot(server)
        request=self.request(save_favorites=True)
        preview=product.action(server,{'action':'report_preview',**request})
        self.assertEqual(product.snapshot(server),before)
        self.assertEqual(preview['after']['totals']['kcal'],[200,200])
        self.assertEqual(preview['after']['counted_count'],1)
        self.assertEqual(preview['after']['coverage']['protein_g'],1)
        result=product.action(server,{'action':'report_commit',**request,'token':preview['token']})
        self.assertFalse(result['consumption_saved'])
        state=product.snapshot(server)
        self.assertEqual(state['records'],[])
        self.assertEqual(state['media'][0]['review']['report']['foods'][0]['source_meta']['kind'],'user_label')
        self.assertEqual(state['saved_foods'][0]['name'],'米饭')

    def test_explicit_eaten_portion_updates_one_record_and_undo_restores(self):
        request=self.request(eaten_servings=1,confirm_consumption=True)
        preview,result=self.commit(request)
        state=product.snapshot(server)
        self.assertEqual(len(state['records']),1)
        self.assertEqual(state['records'][0]['value']['nutrition']['kcal'],[100,100])
        self.assertEqual(state['records'][0]['value']['nutrition']['protein_g'],[2,2])
        self.assertTrue(result['consumption_saved'])
        product.action(server,{'action':'report_commit',**request,'token':preview['token']})
        self.assertEqual(len(server.records()),1)
        product.action(server,{'action':'report_undo','id':'food-1','token':preview['token']})
        self.assertEqual(server.records(),[])
        self.assertEqual(product.snapshot(server)['media'][0]['review']['report'],preview['before'])

    def test_per_serving_conversion_and_unknowns(self):
        request=self.request()
        request['foods']=[{'name':'包装食品','grams':[50,50],
            'per_100g':{'kcal':[75,75],'protein_g':None},
            'density_basis':'per_serving','serving_grams':50,'source_kind':'user_label',
            'source_id':'标签A','included':True}]
        request.update(eaten_servings=1,confirm_consumption=True,servings=1)
        preview,_=self.commit(request)
        row=preview['after']['foods'][0]
        self.assertEqual(row['per_100g']['kcal'],[150,150])
        self.assertEqual(row['source_meta']['original_basis'],'per_serving')
        self.assertEqual(server.records()[0]['value']['nutrition']['kcal'],[75,75])
        self.assertIsNone(server.records()[0]['value']['nutrition']['protein_g'])

    def test_visible_portion_estimate_survives_edit_without_density_invention(self):
        row={'name':'混合炸物','grams':None,'density_basis':'visible_portion',
             'nutrition':{'kcal':[600,900],'protein_g':None},'source_kind':'model_estimate'}
        request=self.request(foods=[row],servings=None)
        preview,_=self.commit(request)
        saved=preview['after']['foods'][0]
        self.assertEqual(saved['nutrition']['kcal'],[600,900])
        self.assertIsNone(saved['per_100g']['kcal'])
        self.assertIsNone(saved['grams'])
        self.assertEqual(server.records(),[])
        row['grams']=[100,200]
        changed=product.action(server,{'action':'report_preview',**self.request(foods=[row],servings=None)})
        self.assertEqual(changed['after']['totals']['kcal'],[600,900])

    def test_visible_portion_requires_valid_numeric_values_and_honest_source(self):
        row={'name':'混合炸物','grams':None,'density_basis':'visible_portion',
             'nutrition':{'kcal':[900,600]},'source_kind':'model_estimate'}
        with self.assertRaises(product.ProductError):
            product.action(server,{'action':'report_preview',**self.request(foods=[row])})
        row['nutrition']={'kcal':[600,900]};row['source_kind']='usda_fdc'
        with self.assertRaises(product.ProductError):
            product.action(server,{'action':'report_preview',**self.request(foods=[row])})

    def test_stale_preview_and_unverified_source_rejected(self):
        request=self.request()
        preview=product.action(server,{'action':'report_preview',**request})
        media=server.load_json(server.MEDIA,[]);media[0]['review']['summary']='后来重新分析'
        server.save_json(server.MEDIA,media)
        with self.assertRaises(product.ProductError):
            product.action(server,{'action':'report_commit',**request,'token':preview['token']})
        bad=copy.deepcopy(request);bad['foods'][0]['source_kind']='database_verified'
        with self.assertRaises(product.ProductError):product.action(server,{'action':'report_preview',**bad})

    def test_no_consumption_without_explicit_checkbox(self):
        with self.assertRaises(product.ProductError):
            product.action(server,{'action':'report_preview',**self.request(eaten_servings=0.5)})

    def test_can_edit_report_without_knowing_diners_but_cannot_record_consumption(self):
        request=self.request(servings=None)
        preview,_=self.commit(request)
        self.assertIsNone(preview['after']['servings'])
        self.assertEqual(server.records(),[])
        with self.assertRaises(product.ProductError):
            product.action(server,{'action':'report_preview',**self.request(servings=None,eaten_servings=0.2,confirm_consumption=True)})

    def test_verified_usda_source_cannot_be_forged_or_changed_in_editor(self):
        reference=food_catalog.match('米饭')
        row={'name':'米饭','grams':[100,100],
             'per_100g':{key:[value,value] for key,value in reference['per_100g'].items()},
             'source_kind':'usda_fdc','source_id':reference['id'],'weight_basis':'熟重'}
        request=self.request(foods=[row],servings=None)
        preview,_=self.commit(request)
        self.assertEqual(preview['after']['foods'][0]['source_meta']['kind'],'usda_fdc')
        tampered=copy.deepcopy(row);tampered['per_100g']['kcal']=[120,120]
        with self.assertRaises(product.ProductError):
            product.action(server,{'action':'report_preview',**self.request(foods=[tampered])})
        tampered=copy.deepcopy(row);tampered['weight_basis']='生重'
        with self.assertRaises(product.ProductError):
            product.action(server,{'action':'report_preview',**self.request(foods=[tampered])})

    def test_existing_intake_requires_reconfirmation_when_report_changes(self):
        self.commit(self.request(eaten_servings=1,confirm_consumption=True))
        with self.assertRaises(product.ProductError):
            product.action(server,{'action':'report_preview',**self.request()})
        changed=self.request(eaten_servings=1,confirm_consumption=True)
        changed['foods'][0]['grams']=[100,100]
        self.commit(changed)
        self.assertEqual(len(server.records()),1)
        self.assertEqual(server.records()[0]['value']['nutrition']['kcal'],[50,50])


if __name__=='__main__':unittest.main()
