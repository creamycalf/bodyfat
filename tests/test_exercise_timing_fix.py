import copy
import unittest
import coach_actions
import product
import test_workbench


class ExerciseTimingFixTests(unittest.TestCase):
    setUp=test_workbench.WorkbenchTests.setUp
    tearDown=test_workbench.WorkbenchTests.tearDown
    chat=test_workbench.WorkbenchTests.chat

    def session(self):
        return {'warmup':{'name':'舒适范围热身','seconds':180},'cooldown':{'name':'舒缓活动','seconds':300},
                'circuit':{'rounds':2,'items':[{'name':name,'work_seconds':40,'rest_seconds':20}
                   for name in ('墙壁俯卧撑','死虫','侧卧抬腿','髋后伸','提踵')]}}

    def test_total_uses_actual_actions_and_all_rest(self):
        reply=coach_actions.exercise_session_reply(self.session())
        self.assertIn('合计18分钟',reply);self.assertIn('每轮5分钟',reply)
        self.assertIn('练习段共10分钟',reply)

    def test_invalid_timing_is_not_rendered(self):
        for invalid in (True,-10,5000,None):
            item=self.session();item['circuit']['items'][0]['rest_seconds']=invalid
            self.assertEqual(coach_actions.exercise_session_reply(item),'')
        item=self.session();item['warmup']['name']='热身3分钟'
        self.assertEqual(coach_actions.exercise_session_reply(item),'')
        item=self.session();item['circuit']['items'][0]['name']='墙壁俯卧撑，每组练10分钟'
        self.assertEqual(coach_actions.exercise_session_reply(item),'')

    def test_chat_replaces_inconsistent_minutes_with_computed_timing(self):
        self.output={'reply':'膝盖不适时停止。每天20分钟，练习段12分钟。',
                     'exercise_session':self.session(),'decision':{'action':'none'},'plan':None}
        answer=self.chat('想开始健身，给我居家运动起步安排。')
        self.assertIn('膝盖不适时停止',answer['reply'])
        self.assertIn('合计18分钟',answer['reply'])
        self.assertNotIn('练习段12分钟',answer['reply']);self.assertNotIn('每天20分钟',answer['reply'])

    def test_missing_structure_cannot_publish_unchecked_duration(self):
        self.output={'reply':'先做舒适范围的动作。共20分钟，循环2轮。','decision':{'action':'none'},'plan':None}
        answer=self.chat('给我健身起步安排。')
        self.assertNotIn('共20分钟',answer['reply']);self.assertIn('尚未核算',answer['reply'])

    def test_safety_condition_in_timing_sentence_is_preserved(self):
        self.output={'reply':'每天练10分钟，出现胸痛立即停止。','exercise_session':self.session(),
            'decision':{'action':'none'},'plan':None}
        answer=self.chat('给我健身起步安排。')
        self.assertIn('出现胸痛立即停止',answer['reply'])


if __name__=='__main__':unittest.main()
