import unittest
import coach_actions
import product
import server
import test_workbench


class AllergenGuardFixTests(unittest.TestCase):
    setUp=test_workbench.WorkbenchTests.setUp
    tearDown=test_workbench.WorkbenchTests.tearDown
    chat=test_workbench.WorkbenchTests.chat

    def test_natural_allergy_statement_matches_ingredients_and_possible_dish(self):
        profile={'allergies':['对花生过敏']}
        for dish in ('花生酱拌面','宫保鸡丁'):
            self.assertEqual(product.meal_allergen_conflicts(profile,{'takeout':{'dish':dish}}),['花生'])
        self.assertEqual(coach_actions.known_allergens({'allergies':['没有过敏']}),[])
        self.assertEqual(coach_actions.known_allergens({'allergies':['对花生不过敏']}),[])

    def test_chat_removes_only_specific_unsafe_recommendation(self):
        server.save_json(server.PROFILE,{'allergies':['对花生过敏']})
        self.output={'reply':'清炒豆腐可以按平常份量选。建议搭配半份宫保鸡丁。去掉花生即可。炒面可结合饥饿感调整。',
                     'decision':{'action':'none'},'plan':None}
        answer=self.chat('食堂宫保鸡丁、清炒豆腐、炒面怎么选？')
        self.assertIn('清炒豆腐',answer['reply']);self.assertIn('饥饿感',answer['reply'])
        self.assertNotIn('搭配半份宫保鸡丁',answer['reply'])
        self.assertNotIn('去掉花生即可',answer['reply'])
        self.assertIn('交叉接触',answer['reply'])

    def test_safe_warning_is_not_deleted(self):
        reply='先避开宫保鸡丁，不要认为挑掉花生就安全。可以选择其他能核实配料的菜。'
        guarded,conflicts=coach_actions.guard_allergen_reply(reply,{'allergies':['对花生过敏']})
        self.assertEqual(guarded,reply);self.assertFalse(conflicts)

    def test_unrelated_warning_does_not_bypass_food_guard(self):
        for reply in ('可以选宫保鸡丁去掉花生，不要喝含糖饮料。','今天晚餐：宫保鸡丁配米饭。'):
            guarded,conflicts=coach_actions.guard_allergen_reply(reply,{'allergies':['花生']})
            self.assertTrue(conflicts);self.assertNotIn('宫保鸡丁',guarded)

    def test_image_advice_passes_same_guard_on_publication(self):
        server.save_json(server.PROFILE,{'allergies':['花生']})
        review=server.normalize_image_analysis({'category':'food','summary':'菜单',
            'foods':[{'name':'宫保鸡丁'}],'advice':['建议选半份宫保鸡丁。']},'food')
        media=server.load_json(server.MEDIA,[]);media[0]['review']=review;server.save_json(server.MEDIA,media)
        answer=product.chat(server,{'text':'这餐怎么选','media_id':'food-1','conversation_id':'test-conversation',
             'client_message_id':'allergen-photo-publication'},image_review_only=True)
        self.assertNotIn('建议选半份宫保鸡丁',answer['reply']);self.assertIn('交叉接触',answer['reply'])
        detail=product.snapshot(server)['media'][0]['review']['report']['advice']
        self.assertNotIn('建议选半份宫保鸡丁',str(detail));self.assertIn('交叉接触',str(detail))


if __name__=='__main__':unittest.main()
