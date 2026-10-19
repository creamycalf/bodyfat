import copy
import unittest
import test_workbench
import product
import server
import workbench


class NutritionContextTests(unittest.TestCase):
    setUp=test_workbench.WorkbenchTests.setUp
    tearDown=test_workbench.WorkbenchTests.tearDown
    chat=test_workbench.WorkbenchTests.chat

    def meal(self):
        self.output['record_events']=[{'type':'meal','evidence':'午餐我吃了150克熟米饭','value':{
            'description':'150克熟米饭','nutrition':{'kcal':[170,210]},'uncertainty':'米饭含水量不同',
            'nutrition_context':{'method':'laboratory','reliability':'100%'}}}]
        self.chat('午餐我吃了150克熟米饭，请记录。')
        return server.records()[0]

    def test_model_cannot_claim_verified_provenance(self):
        record=self.meal()
        self.assertEqual(record['value']['nutrition_context'],{
            'method':'conversation_estimate','basis':'午餐我吃了150克熟米饭','reliability':'uncalibrated'})

    def test_missing_values_stay_unknown_and_partial_totals_are_counted(self):
        record=self.meal()
        other=copy.deepcopy(record);other['id']='unknown-meal';other['value']['nutrition']={}
        summary=workbench.food_summary([record,other],product.today())
        self.assertEqual(summary['totals']['kcal'],{'range':[170,210],'estimated_count':1,'unknown_count':1})
        self.assertEqual(summary['totals']['protein_g'],{'range':None,'estimated_count':0,'unknown_count':2})
        self.assertEqual(workbench.nutrition_context(other['value'],'conversation_estimate')['method'],'unknown')

    def test_correction_context_and_undo(self):
        record=self.meal()
        payload={'id':record['id'],'operation':'edit','date':product.today(),'description':'半份米饭',
                 'nutrition_mode':'scale','factor':0.5}
        preview=product.action(server,{'action':'meal_preview',**payload})
        self.assertEqual(preview['after']['value']['nutrition_context']['method'],'scaled')
        saved=product.action(server,{'action':'meal_commit',**payload,'token':preview['token']})
        self.assertEqual(server.records()[0]['value']['nutrition']['kcal'],[85,105])
        product.action(server,{'action':'meal_undo','correction_id':saved['correction_id']})
        self.assertEqual(server.records()[0],record)
        preview=product.action(server,{'action':'meal_preview',**payload,'nutrition_mode':'unknown'})
        self.assertEqual(preview['after']['value']['nutrition_context']['method'],'unknown')
        self.assertTrue(all(v is None for v in preview['after']['value']['nutrition'].values()))

    def test_recipe_portion_metadata_preserved(self):
        result=product.normalize_meal_options({'cook':{'dish':'饭','ingredients':'米饭150克','steps':'加热',
            'servings':'1人1餐参考量','weight_basis':'米饭熟重'}})
        self.assertEqual(result['cook']['weight_basis'],'米饭熟重')
        self.assertEqual(result['cook']['servings'],'1人1餐参考量')
        for text in ('午餐为外卖','晚餐自己做饭','非饮食项目'):
            self.assertEqual(product.normalize_meal_options({'cook':{'dish':text,'ingredients':text,'steps':text}}),{})

    def test_request_to_explain_estimation_assumptions_is_not_hypothetical_food(self):
        self.output['record_events']=[{'type':'meal','evidence':'午餐我吃了150克熟米饭','value':{
            'description':'米饭','nutrition':{'kcal':[170,210]},'uncertainty':'含水量不同'}}]
        self.chat('午餐我吃了150克熟米饭，请记录并说明估算假设。')
        self.assertEqual(len(server.records()),1)
        self.assertEqual(server.records()[0]['value']['nutrition']['kcal'],[170,210])
        self.chat('假设午餐我吃了150克熟米饭，请记录并说明估算假设。')
        self.assertEqual(len(server.records()),1)

    def test_explicit_unknown_dinner_survives_missing_model_event(self):
        self.output['reply']='已记录晚餐'
        self.chat('今天晚餐我吃了自助餐，份量不清楚，请只记录这件事，营养保持未知。')
        self.assertEqual(len(server.records()),1)
        self.assertEqual(server.records()[0]['value']['nutrition_context']['method'],'unknown')
