"""Photo calculations use explicit whole-plate shares and retain valid lab zeroes."""
import copy
import unittest

import nutrition_reports as nr


class PortionReportFixTests(unittest.TestCase):
    def setUp(self):
        self.review={'report':nr.food_report({'foods':[{'name':'餐盘',
            'nutrition_basis':'portion_estimate','nutrition':{
                'kcal':[600,900],'protein_g':[30,45],'carbs_g':[60,90],'fat_g':[0,0]}}]})}

    def estimate(self,text,review=None):
        return nr.portion_reply(text+'，热量和营养是多少？',review or self.review)

    def test_fractions_percentages_and_equivalent_chinese_forms(self):
        cases={
            '这份只吃三分之一':('200–300','10–15'),
            '这份的1/2':('300–450','15–22.5'),
            '如果这份只吃1/2':('300–450','15–22.5'),
            '我吃这份的2/3':('400–600','20–30'),
            '这份只吃三分之二':('400–600','20–30'),
            '这餐只吃百分之五十':('300–450','15–22.5'),
            '整盘只吃25%':('150–225','7.5–11.2'),
            '这一份吃50％':('300–450','15–22.5'),
            '这份吃2／3':('400–600','20–30'),
            '这份吃33.3%':('199.8–299.7','10–15'),
            '这份吃完':('600–900','30–45'),
        }
        for text,(energy,protein) in cases.items():
            with self.subTest(text=text):
                reply=self.estimate(text)
                self.assertIn('热量约 '+energy+' 千卡',reply)
                self.assertIn('蛋白质约 '+protein+' 克',reply)
                self.assertIn('脂肪约 0 克',reply)

    def test_partial_numbers_remain_partial_and_missing_macros_are_not_zero(self):
        raw={'foods':[{'name':'已估算','nutrition_basis':'portion_estimate',
                       'nutrition':{'kcal':[600,900]}},{'name':'无法辨认的食物'}]}
        review={'report':nr.food_report(raw)}
        before=copy.deepcopy(review)
        reply=self.estimate('这份只吃三分之一',review)
        self.assertIn('热量约 200–300 千卡（仅已估算部分，不是整餐总量）',reply)
        self.assertNotIn('蛋白质约',reply)
        self.assertNotIn('脂肪约',reply)
        self.assertEqual(review,before)

    def test_separate_nutrient_question_keeps_explicit_photo_fraction(self):
        # Verbatim real-model failure: “分别” was mistaken for different
        # ingredient shares, causing validated arithmetic to be omitted.
        text='只吃这份的1/2，热量和蛋白质分别是多少？'
        before=copy.deepcopy(self.review)
        reply=nr.portion_reply(text,self.review)
        self.assertIn('热量约 300–450 千卡',reply)
        self.assertIn('蛋白质约 15–22.5 克',reply)
        self.assertEqual(self.review,before)

    def test_ingredient_remainders_multiple_diners_and_negation_do_not_scale_plate(self):
        for text in (
            '这份米饭只吃1/2，配菜全吃',
            '这份只吃一半肉，其他都吃',
            '这份剩下1/2',
            '这份的1/2留给明天',
            '这份的1/2倒掉了',
            '这份只吃1/2，剩下留给明天',
            '我和朋友把这份吃1/2',
            '两个人分食，这份吃1/2',
            '我和妈妈吃这份的1/2',
            '这份吃1/2，给孩子另外一半',
            '这份不吃一半',
            '不是这份吃1/2',
            '不会吃这份的1/2',
            '不要算这份的1/2',
            '这份吃一半以上',
            '这份吃1/2或全部',
            '这份吃1/2到2/3',
            '这份吃1/2，另一餐也吃1/2',
            '这份只吃一点',
            '这份的1/2分别吃，热量和蛋白质是多少',
            '这份的1/2分别食用，热量和蛋白质是多少',
            '这份的1/2，分别减少食物份量',
            '吃1/2',
            '吃三分之一',
        ):
            with self.subTest(text=text):self.assertEqual(self.estimate(text),'')

    def test_no_save_request_still_allows_analysis(self):
        self.assertIn('300–450',self.estimate('如果这份只吃1/2，只分析不要记录'))

    def test_invalid_ratios_and_untrusted_report_numbers_do_not_produce_results(self):
        for ratio in ('1/0','0/2','-1/2','3/2','150%','0%','百分之一百一','一二分之一','1/2000000'):
            with self.subTest(ratio=ratio):self.assertEqual(self.estimate('这份吃'+ratio),'')
        for bad in (True,float('nan'),float('inf'),[-1,1],[900,600],10**9):
            with self.subTest(bad=bad):
                review={'report':{'kind':'food','totals':{'kcal':bad},'partial_totals':{}}}
                self.assertEqual(self.estimate('这份吃1/2',review),'')

    def test_report_zero_is_readable_unknown_and_invalid_values_remain_unknown(self):
        for value,expected in ((0,'0'),(0.0,'0.0'),('0','0'),(' 0 ','0'),
                               (None,'未识别'),('','未识别'),('  ','未识别'),
                               (False,'未识别'),(True,'未识别'),(float('nan'),'未识别'),
                               (float('inf'),'未识别'),([], '未识别'),({},'未识别')):
            with self.subTest(value=value):
                report=nr.report({'tests':[{'name':'检查指标','value':value}]},'report')
                self.assertEqual(report['tests'][0]['value'],expected)
                self.assertEqual(report['tests'][0]['unit'],'未识别')


if __name__=='__main__':unittest.main()
