"""Actual chat persistence regressions using only temporary fictional data."""
import copy
import unittest

import product
import server
import test_workbench


class FactOwnershipFixTests(unittest.TestCase):
    setUp=test_workbench.WorkbenchTests.setUp
    tearDown=test_workbench.WorkbenchTests.tearDown
    chat=test_workbench.WorkbenchTests.chat

    def reset(self,profile=None):
        server.save_json(server.PROFILE,profile or {})
        server.save_json(server.RECORDS,[])
        server.save_json(server.DATA/'workspace.json',{})
        self.output={'reply':'会按你明确说的情况继续讨论。',
                     'decision':{'action':'none'},'plan':None}

    def test_negative_hypothetical_question_and_third_party_cannot_delete(self):
        profile={'age':38,'allergies':['花生'],'height_cm':175}
        for text in (
            '不要删除我的年龄记录。',
            '请勿删除我的年龄记录。',
            '我不是让你删除我的年龄记录。',
            '暂时不删除我的年龄记录。',
            '我没让你删除我的年龄记录。',
            '别把我的年龄记录删掉。',
            '不需要清除我的过敏资料。',
            '如果删除我的过敏记录，之后还会提醒我吗？',
            '删除我的年龄记录会怎么样？',
            '删除我的过敏记录，会影响提醒吗？',
            '我可以删除年龄吗？',
            '删除我的年龄有什么影响。',
            '我忘记我的年龄了。',
            '我朋友想删除自己的过敏信息。',
            '我老公想删除他的年龄记录。',
            '她要清除自己的身高记录。',
            '“请删除我的年龄记录。”这是朋友说的。',
        ):
            with self.subTest(text=text):
                self.reset(copy.deepcopy(profile))
                self.chat(text)
                self.assertEqual(product.snapshot(server)['profile'],profile)
                self.assertFalse(product.workspace(server)['profile_history'])

    def test_explicit_self_delete_keeps_retracted_audit_history(self):
        self.reset({'age':38,'allergies':['花生']})
        self.chat('请撤回并删除我的过敏信息。')
        state=product.snapshot(server)
        self.assertEqual(state['profile'],{'age':38})
        self.assertEqual(state['profile_history'][-1]['field'],'allergies')
        self.assertEqual(state['profile_history'][-1]['status'],'retracted')

    def test_delete_only_the_targeted_clause(self):
        self.reset({'age':38,'allergies':['花生']})
        self.chat('删除我的年龄记录，过敏资料保留。')
        self.assertEqual(product.snapshot(server)['profile'],{'allergies':['花生']})
        self.reset({'age':38,'allergies':['花生']})
        self.chat('不要删除我的年龄，删除我的过敏资料。')
        self.assertEqual(product.snapshot(server)['profile'],{'age':38})

    def test_explicit_no_save_is_respected_for_new_and_existing_facts(self):
        self.reset({'age':38,'allergies':['花生']})
        self.chat('不要保存我的年龄。')
        self.assertNotIn('age',product.snapshot(server)['profile'])
        self.reset()
        self.output['profile_changes']=[{'field':'age','value':50,'evidence':'50岁'}]
        self.chat('不要保存：我50岁，身高180厘米，体重90公斤。')
        self.assertEqual(product.snapshot(server)['profile'],{})
        self.assertFalse(server.records())

    def test_spouses_relatives_and_pronouns_cannot_become_self_facts(self):
        for subject in ('我老公','我老婆','我的丈夫','我的妻子','我的配偶','我伴侣','我先生','我太太','我父母',
                        '我爸爸','我妈妈','她','他','他们','我儿子','我女儿','我姐姐'):
            with self.subTest(subject=subject):
                self.reset()
                self.output['profile_changes']=[
                    {'field':'conditions','value':['糖尿病'],'evidence':'糖尿病'},
                    {'field':'height_cm','value':180,'evidence':'身高180厘米'}]
                self.chat(subject+'40岁，有糖尿病，身高180厘米，体重90公斤。')
                self.assertEqual(product.snapshot(server)['profile'],{})
                self.assertFalse(server.records())

    def test_third_person_scope_requires_explicit_self_reset(self):
        self.reset()
        self.chat('我老公40岁。有糖尿病，身高180厘米。但我38岁，身高175厘米，体重85公斤。')
        profile=product.snapshot(server)['profile']
        self.assertEqual(profile.get('age'),38)
        self.assertEqual(profile.get('height_cm'),175)
        self.assertNotIn('conditions',profile)
        self.assertEqual([r['value']['kg'] for r in server.records() if r['type']=='weight'],[85])
        self.assertEqual(product.self_fact_text('她40岁。有糖尿病，身高180厘米。'),'')

    def test_real_facts_before_hypothetical_are_kept(self):
        self.reset()
        self.output['profile_changes']=[{'field':'allergies','value':['花生'],'evidence':'对花生过敏'}]
        self.chat('我男，38岁，身高175厘米，体重85公斤，对花生过敏。如果我想减脂，先从饮食还是运动开始更合适？')
        profile=product.snapshot(server)['profile']
        self.assertEqual(profile.get('age'),38)
        self.assertEqual(profile.get('sex'),'男')
        self.assertEqual(profile.get('height_cm'),175)
        self.assertIn('花生',str(profile.get('allergies')))
        self.assertEqual([r['value']['kg'] for r in server.records() if r['type']=='weight'],[85])

    def test_hypothetical_scope_carries_to_its_consequent(self):
        self.reset()
        self.output['profile_changes']=[{'field':'conditions','value':['糖尿病'],'evidence':'糖尿病'}]
        self.chat('如果我50岁，有糖尿病，身高180厘米，体重90公斤，应该怎么办？')
        self.assertEqual(product.snapshot(server)['profile'],{})
        self.assertFalse(server.records())
        self.reset()
        self.chat('如果我50岁有糖尿病，应该怎么办？我38岁，身高175厘米。')
        self.assertEqual(product.snapshot(server)['profile'].get('age'),38)
        self.assertEqual(product.snapshot(server)['profile'].get('height_cm'),175)

    def test_quotes_cannot_be_used_as_self_evidence_or_joined_across_gaps(self):
        self.reset()
        self.output['profile_changes']=[{'field':'conditions','value':['糖尿病'],'evidence':'糖尿病'}]
        self.chat('我引用一句话：“我50岁，有糖尿病，身高180厘米，体重90公斤。”')
        self.assertEqual(product.snapshot(server)['profile'],{})
        self.assertFalse(server.records())
        self.reset()
        self.chat('我朋友说：“我50岁，有糖尿病，身高180厘米，体重90公斤。')
        self.assertEqual(product.snapshot(server)['profile'],{})
        self.assertFalse(server.records())
        source='我对花生“朋友50岁”过敏。'
        kept=product.self_fact_text(source)
        self.assertNotIn('我对花生过敏',kept)
        self.assertNotIn('50岁',kept)
        self.assertIn('\n',kept)

    def test_other_suggestions_does_not_mean_another_person(self):
        self.reset()
        self.chat('我38岁，身高175厘米。其他建议等会再说。')
        self.assertEqual(product.snapshot(server)['profile'].get('age'),38)
        self.assertEqual(product.snapshot(server)['profile'].get('height_cm'),175)


if __name__=='__main__':unittest.main()
