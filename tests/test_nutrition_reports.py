import unittest
import nutrition_reports as nr
import food_catalog
import consultation
import server

class NutritionReportTests(unittest.TestCase):
    def test_local_arithmetic_and_shares(self):
        density={'kcal':100,'protein_g':10,'carbs_g':10,'fat_g':2}
        report=nr.food_report({'foods':[{'name':'甲','grams':[100,200],'per_100g':density},{'name':'乙','grams':100,'per_100g':density}]})
        self.assertEqual(report['totals']['kcal'],[200,300])
        self.assertEqual(report['totals']['protein_g'],[20,30])
        self.assertEqual(report['foods'][0]['energy_share_pct'],60)
        self.assertAlmostEqual(sum(report['macro_energy_pct'].values()),100,delta=.2)

    def test_unknown_is_not_zero_or_complete_macro_report(self):
        report=nr.food_report({'foods':[{'name':'甲','grams':100,'per_100g':{'kcal':100}},{'name':'乙'}]})
        self.assertEqual(report['coverage']['kcal'],1)
        self.assertIsNone(report['totals']['kcal'])
        self.assertEqual(report['partial_totals']['kcal'],[100,100])
        self.assertIsNone(report['totals']['protein_g'])
        self.assertIsNone(report['macro_energy_pct'])
        for value in (True,float('nan'),[-1,2],[3,2],[0,float('inf')]):
            self.assertIsNone(nr.interval(value,100))

    def test_visible_portion_estimate_survives_without_inventing_weight_or_density(self):
        report=nr.food_report({'foods':[{'name':'混合煎炸食物（主料待核对）',
            'grams':None,'nutrition':{'kcal':[700,1500]},
            'portion_basis':'按照片整盘估计，包含吸油假设'}]},use_catalog=True)
        food=report['foods'][0]
        self.assertEqual(food['nutrition_basis'],'portion_estimate')
        self.assertEqual(food['nutrition']['kcal'],[700,1500])
        self.assertEqual(report['totals']['kcal'],[700,1500])
        self.assertEqual(report['coverage']['kcal'],1)
        self.assertIsNone(food['grams'])
        self.assertTrue(all(value is None for value in food['per_100g'].values()))
        self.assertIsNone(report['totals']['protein_g'])
        self.assertIsNone(report['macro_energy_pct'])
        self.assertEqual(food['source_meta']['basis'],'visible_portion')
        self.assertEqual(food['source_meta']['kind'],'model_estimate')
        self.assertNotIn('consumed',str(report))

    def test_legacy_meal_and_beverage_candidates_keep_only_visible_portion_estimates(self):
        report=nr.food_report({'record_candidates':[
            {'type':'meal','value':{'description':'油炸混合食物','nutrition':{'kcal':[600,1100]}}},
            {'type':'beverage','label':'饮料','value':{'nutrition':{'kcal':[90,130]}}},
            {'type':'weight','value':{'description':'体重','nutrition':{'kcal':900}}}]},use_catalog=True)
        self.assertEqual([food['name'] for food in report['foods']],['油炸混合食物','饮料'])
        self.assertEqual(report['totals']['kcal'],[690,1230])
        self.assertTrue(all(food['nutrition_basis']=='portion_estimate' for food in report['foods']))

    def test_foods_and_legacy_candidates_are_not_both_counted(self):
        report=nr.food_report({'foods':[{'name':'整盘','nutrition':{'kcal':[700,1500]}}],
            'record_candidates':[{'type':'meal','value':{'description':'重复整盘','nutrition':{'kcal':[700,1500]}}}]})
        self.assertEqual(len(report['foods']),1)
        self.assertEqual(report['totals']['kcal'],[700,1500])

    def test_visible_portion_intervals_reject_bad_numbers_and_do_not_turn_unknown_into_zero(self):
        for bad in (True,float('nan'),float('inf'),[-1,2],[3,2],[0,float('inf')],15001):
            with self.subTest(bad=bad):
                report=nr.food_report({'foods':[{'name':'可见食物','nutrition':{'kcal':bad}}]})
                self.assertIsNone(report['totals']['kcal'])
                self.assertIsNone(report['partial_totals']['kcal'])
        report=nr.food_report({'foods':[{'name':'可见食物','nutrition':{
            'kcal':[700,1000],'protein_g':1001,'carbs_g':2001,'fat_g':1501}}]})
        self.assertEqual(report['totals']['kcal'],[700,1000])
        self.assertTrue(all(report['totals'][key] is None for key in ('protein_g','carbs_g','fat_g')))

    def test_density_calculation_wins_over_duplicate_model_portion_numbers(self):
        report=nr.food_report({'foods':[{'name':'混合菜','grams':200,
            'per_100g':{'kcal':180},'nutrition':{'kcal':[1000,2000]}}]})
        self.assertEqual(report['totals']['kcal'],[360,360])
        self.assertEqual(report['foods'][0]['nutrition_basis'],'weight_density')

    def test_explicit_portion_does_not_silently_recalculate_after_weight_edit(self):
        raw={'foods':[{'name':'整盘估算','nutrition_basis':'portion_estimate','grams':200,
            'per_100g':{'kcal':180},'nutrition':{'kcal':[700,1500]}}]}
        report=nr.food_report(raw)
        self.assertEqual(report['totals']['kcal'],[700,1500])
        self.assertIsNone(report['foods'][0]['per_100g']['kcal'])
        saved=report['foods'][0]
        saved['grams']=[100,100]
        self.assertEqual(nr.food_report({'foods':[saved]})['totals']['kcal'],[700,1500])

    def test_deleting_weight_never_reuses_stale_computed_nutrition(self):
        report=nr.food_report({'foods':[{'name':'菜','grams':200,'per_100g':{'kcal':180}}]})
        food=report['foods'][0]
        food['grams']=None
        edited=nr.food_report({'foods':[food]})
        self.assertIsNone(edited['totals']['kcal'])
        self.assertIsNone(edited['foods'][0]['nutrition']['kcal'])

    def test_calorie_portion_estimate_is_not_lost_when_only_density_macros_exist(self):
        report=nr.food_report({'foods':[{'name':'餐食','grams':200,
            'per_100g':{'protein_g':10},'nutrition':{'kcal':[500,800]}}]})
        self.assertEqual(report['totals']['kcal'],[500,800])
        self.assertIsNone(report['totals']['protein_g'])

    def test_portion_estimate_source_cannot_claim_catalog_or_verified_label(self):
        for source_kind in ('model_estimate','usda_fdc','user_label','user_reference'):
            with self.subTest(source_kind=source_kind):
                report=nr.food_report({'foods':[{'name':'米饭','source_kind':source_kind,
                    'source_id':'168930','nutrition':{'kcal':[200,350]}}]},use_catalog=True)
                food=report['foods'][0]
                self.assertEqual(food['source_meta']['kind'],'model_estimate')
                self.assertEqual(food['source_meta']['id'],'')
                self.assertEqual(report['totals']['kcal'],[200,350])

    def test_only_unaccounted_unknown_component_blocks_whole_plate_estimate(self):
        report=nr.food_report({'foods':[
            {'name':'混合炸物，已包含吸油','nutrition':{'kcal':[700,1500]}},
            {'name':'吸油已计入炸物','included':False,'nutrition':{'kcal':None}}]})
        self.assertEqual(report['totals']['kcal'],[700,1500])
        self.assertEqual(report['counted_count'],1)
        report=nr.food_report({'foods':[
            {'name':'已估算食物','nutrition':{'kcal':[300,500]}},
            {'name':'另一种无法估算的可见食物','nutrition':{'kcal':None}}]})
        self.assertIsNone(report['totals']['kcal'])
        self.assertEqual(report['partial_totals']['kcal'],[300,500])

    def test_auto_type_and_candidates_share_computed_numbers(self):
        result=server.normalize_image_analysis({'category':'food','foods':[{'name':'米饭','grams':200,'per_100g':{'kcal':120}}]},'auto')
        self.assertEqual(result['category'],'food')
        self.assertEqual(result['record_candidates'][0]['value']['nutrition']['kcal'],[260,260])
        self.assertEqual(result['report']['foods'][0]['source_meta']['id'],'168930')
        self.assertIsNone(result['report']['servings'])
        self.assertNotIn('consumed',str(result))
        lab=server.normalize_image_analysis({'category':'report','tests':[{'name':'指标','value':'模糊'}]},'auto')
        self.assertEqual(lab['report']['tests'][0]['reference'],'未识别')

    def test_catalog_reference_requires_exact_plain_food_and_weight_basis(self):
        rice=server.normalize_image_analysis({'category':'food','servings':3,
            'foods':[{'name':'米饭','grams':[150,200], 'weight_basis':'熟重',
                      'per_100g':{'kcal':[50,50]}}]},'food')['report']
        self.assertEqual(rice['foods'][0]['per_100g']['kcal'],[130,130])
        self.assertEqual(rice['foods'][0]['source_meta']['kind'],'usda_fdc')
        self.assertEqual(rice['totals']['kcal'],[195,260])
        self.assertIsNone(rice['servings'])
        raw=server.normalize_image_analysis({'category':'food','foods':[
            {'name':'米饭','grams':100,'weight_basis':'生重','per_100g':{'kcal':300}}]},'food')['report']
        self.assertEqual(raw['foods'][0]['source_meta']['kind'],'model_estimate')
        self.assertEqual(raw['totals']['kcal'],[300,300])
        composite=server.normalize_image_analysis({'category':'food','foods':[
            {'name':'咖喱鸡饭','grams':300,'per_100g':{'kcal':150}}]},'food')['report']
        self.assertEqual(composite['foods'][0]['source_meta']['kind'],'model_estimate')
        claimed_label=server.normalize_image_analysis({'category':'food','foods':[
            {'name':'不明咖啡','grams':250,'per_100g':{'kcal':50},'source_kind':'user_label',
             'source_id':'模型声称标签已核对'}]},'food')['report']
        self.assertEqual(claimed_label['foods'][0]['source_meta']['kind'],'model_estimate')
        self.assertFalse(food_catalog.verified('米饭','168930',{'kcal':[float('nan'),float('nan')]}))

    def test_unknown_component_prevents_full_plate_total_and_no_consumption_inference(self):
        result=server.normalize_image_analysis({'category':'food','foods':[
            {'name':'米饭','grams':100,'per_100g':{'kcal':130}},
            {'name':'不明酱料','grams':None,'per_100g':{'kcal':None}},
            {'name':'整道菜','included':False,'grams':300,'per_100g':{'kcal':200}}]},'food')
        report=result['report']
        self.assertIsNone(report['totals']['kcal'])
        self.assertEqual(report['partial_totals']['kcal'],[130,130])
        self.assertEqual(len(result['record_candidates']),2)
        self.assertNotIn('consumed',str(result))

    def test_readiness_requires_known_not_skipped(self):
        self.assertFalse(consultation.readiness({},[])['ready'])
        p={k:'明确回答' for fields in consultation.GROUPS.values() for k in fields}
        p.update(breakfast_habit='一碗粥',lunch_habit='一碗米饭',dinner_habit='一碗面条',surgeries=['没有'])
        records=[{'type':'weight','value':{'kg':80}}]
        self.assertTrue(consultation.readiness(p,records)['ready'])
        # Unknown/skipped context does not authorize a full personalized plan.
        p['sleep_schedule']='跳过'
        self.assertFalse(consultation.readiness(p,records)['ready'])
        p['medications']='跳过'
        self.assertFalse(consultation.readiness(p,records)['ready'])
