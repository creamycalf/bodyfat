"""Practical constraints survive long chats without reviving withdrawn facts."""
import json
import unittest
import product
import server
import test_workbench


class LongConversationMemoryTests(unittest.TestCase):
    setUp=test_workbench.WorkbenchTests.setUp
    tearDown=test_workbench.WorkbenchTests.tearDown
    chat=test_workbench.WorkbenchTests.chat

    def seed(self,old_text='我38岁，家里没有冰箱，上班没法热饭，我不吃鱼。'):
        old={'id':'old-practical','role':'user','text':old_text,'created_at':'2026-09-01T12:00:00'}
        noise=[{'id':f'noise-{i}','role':'assistant' if i%2 else 'user','text':'讨论当天感受。',
                'created_at':'2026-10-01T12:00:00'} for i in range(40)]
        conversation={'id':'old-lifestyle-chat','messages':[old,*noise]}
        server.save_json(server.CONVERSATIONS,[conversation])
        return conversation

    def test_old_practical_constraints_reach_new_chat_after_many_messages(self):
        self.seed()
        self.chat('结合我以前说的生活条件，今天晚餐怎么安排？',conversation_id='new-dinner-chat')
        related=json.loads(self.prompt[1]['content'])['related_conversation_facts']
        statements=str(related)
        self.assertIn('没有冰箱',statements);self.assertIn('没法热饭',statements);self.assertIn('不吃鱼',statements)
        self.assertNotIn('38岁',statements)
        self.assertTrue(all(item['source_message_id']=='old-practical' for item in related))
        self.assertEqual(product.snapshot(server)['profile'],{})

    def test_third_party_hypothetical_quoted_and_private_facts_are_not_recalled(self):
        for text in ('我老公家里没有冰箱，他上班没法热饭。','如果我没有冰箱，晚饭该怎么办？',
                     '我朋友说：“我家里没有冰箱。”','不要保存：我家里没有冰箱。'):
            with self.subTest(text=text):
                conversation=self.seed(text)
                self.assertFalse(product.conversation_fact_context(server,'晚饭怎么安排',[conversation],product.workspace(server),{},[]))

    def test_disabled_and_undone_sources_are_excluded(self):
        conversation=self.seed()
        w=product.workspace(server);w['receipts']['old-practical']={'undone':True}
        self.assertFalse(product.conversation_fact_context(server,'晚饭怎么安排',[conversation],w,{},[]))
        w['receipts']={};conversation['messages'][0]['memory_enabled']=False
        self.assertFalse(product.conversation_fact_context(server,'晚饭怎么安排',[conversation],w,{},[]))

    def test_later_explicit_constraint_wins_without_erasing_other_dimensions(self):
        conversation=self.seed('我没时间做饭，家里没有冰箱。')
        conversation['messages'].append({'id':'new-cooking','role':'user','text':'现在我每天可以做饭。',
                                          'created_at':'2026-10-19T12:00:00'})
        related=product.conversation_fact_context(server,'晚餐怎么安排',[conversation],product.workspace(server),{},[])
        self.assertIn('每天可以做饭',str(related));self.assertNotIn('没时间做饭',str(related))
        self.assertIn('没有冰箱',str(related))

    def test_retracted_practical_source_does_not_return(self):
        conversation=self.seed()
        w=product.workspace(server);w['profile_history']=[{'field':'preferences','status':'retracted',
                                                        'source_message_id':'old-practical'}]
        self.assertFalse(product.conversation_fact_context(server,'晚饭怎么安排',[conversation],w,{},[]))

    def test_positive_updates_and_current_profile_override_old_restrictions(self):
        conversation=self.seed('我家里没有冰箱，上班没法热饭，我不吃鱼。')
        profile={'preferences':'现在能吃鱼','meal_schedule':'上班可以热饭','food_habits':'家里有冰箱'}
        self.assertFalse(product.conversation_fact_context(server,'晚饭怎么安排',[conversation],product.workspace(server),profile,[]))
        conversation['messages'].append({'id':'new-conditions','role':'user','text':'现在我有冰箱了，上班可以热饭了，我现在可以吃鱼了。',
                                          'created_at':'2026-10-19T12:00:00'})
        related=product.conversation_fact_context(server,'晚饭怎么安排',[conversation],product.workspace(server),{},[])
        self.assertIn('有冰箱了',str(related));self.assertIn('可以吃鱼了',str(related))
        self.assertNotIn('没有冰箱',str(related));self.assertNotIn('没法热饭',str(related));self.assertNotIn('不吃鱼',str(related))

    def test_direct_practical_forget_and_later_reassertion(self):
        conversation=self.seed('我家里没有冰箱，我不吃鱼。')
        conversation['messages'].append({'id':'forget','role':'user','text':'请忘掉我的冰箱情况。',
                                          'created_at':'2026-10-18T12:00:00'})
        recall=lambda:product.conversation_fact_context(server,'晚饭怎么安排',[conversation],product.workspace(server),{},[])
        self.assertNotIn('冰箱',str(recall()));self.assertIn('不吃鱼',str(recall()))
        conversation['messages'].append({'id':'again','role':'user','text':'现在我有冰箱了。','created_at':'2026-10-19T12:00:00'})
        self.assertIn('有冰箱了',str(recall()))

    def test_recall_question_about_fridge_and_avoidance_uses_food_context(self):
        conversation=self.seed('我家里没有冰箱，我不吃鱼。')
        conversation['messages'].append({'id':'forget','role':'user','text':'请忘掉我的冰箱情况。',
                                          'created_at':'2026-10-19T12:00:00'})
        related=product.conversation_fact_context(server,'你还记得我家有没有冰箱、有什么忌口吗？',
                                                  [conversation],product.workspace(server),{},[])
        self.assertNotIn('冰箱',str(related));self.assertIn('不吃鱼',str(related))

    def test_practical_forget_questions_negation_other_people_and_hypothesis_keep_facts(self):
        for command in ('不要忘掉我的冰箱情况。','如果忘掉我的冰箱情况会怎样？','能不能忘掉我的冰箱情况？',
                        '我朋友说：“忘掉我的冰箱情况。”','我老公要求忘掉他的冰箱情况。'):
            with self.subTest(command=command):
                conversation=self.seed('我家里没有冰箱。')
                conversation['messages'].append({'id':'not-command','role':'user','text':command,'created_at':'2026-10-19T12:00:00'})
                related=product.conversation_fact_context(server,'晚饭怎么安排',[conversation],product.workspace(server),{},[])
                self.assertIn('没有冰箱',str(related))

    def test_withdrawn_avoidance_does_not_return_from_different_old_source(self):
        conversation=self.seed('我不吃鱼。')
        w=product.workspace(server);w['profile_history']=[{'field':'allergies','status':'retracted',
            'value':['不吃鱼'],'source_message_id':'another-old-source','valid_until':'2026-10-19T12:00:00'}]
        self.assertFalse(product.conversation_fact_context(server,'晚饭怎么安排',[conversation],w,{},[]))

    def test_history_budget_preserves_complete_recent_messages_and_question(self):
        messages=[{'role':'user' if i%2==0 else 'assistant','text':str(i)+'x'*5998} for i in range(24)]
        messages[-1]['text']='医生有没有给过活动限制？'
        history=product.bounded_dialogue_history(messages)
        self.assertLessEqual(sum(len(item['content']) for item in history),24000)
        self.assertEqual(history[-1]['content'],'医生有没有给过活动限制？')
        self.assertLess(len(history),24)
        self.assertTrue(all(item['content'] in [m['text'] for m in messages] for item in history))

    def test_synonyms_retrieve_old_eye_record_ahead_of_unrelated_checks(self):
        old={'id':'old-eye','type':'lab_or_measurement','value':{'description':'视网膜复查待安排'},
             'confirmed':True,'created_at':'2026-01-01T12:00:00'}
        noise=[{'id':f'other-{i}','type':'lab_or_measurement','value':{'description':'血常规化验'},
                'confirmed':True,'created_at':product.now()} for i in range(20)]
        server.save_json(server.RECORDS,[old,*noise])
        matches=server.memory_search('我之前眼睛检查的情况还记得吗？')
        self.assertEqual(matches[0]['record']['id'],'old-eye')
        old['status']='retracted';server.save_json(server.RECORDS,[old,*noise])
        self.assertFalse(any(item['record']['id']=='old-eye' for item in server.memory_search('眼睛检查')))


if __name__=='__main__':unittest.main()
