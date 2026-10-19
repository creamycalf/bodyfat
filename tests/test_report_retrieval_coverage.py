"""Report retrieval covers named dates/metrics without claiming ownership."""
import copy
import unittest
from unittest.mock import patch

import nutrition_reports
import product


def saved_report(key, date, metric='LDL', value='4.2', **flags):
    return {'id':key,'type':'report','created_at':date+'T12:00:00',
            'review':{'summary':'检查报告，尚待核对','report':nutrition_reports.report({
                'tests':[{'name':metric,'value':value,'unit':'mmol/L','reference':'<3.4','date':date}]},'report')},
            **flags}


class ReportRetrievalCoverageTests(unittest.TestCase):
    def context(self, media, text, selected=(), conversations=()):
        with patch.object(product,'today',return_value='2026-10-19'):
            return product.report_context(media,conversations,'current-chat',text,list(selected))

    def test_named_historical_and_current_dates_reach_beyond_six_recent_reports(self):
        old=saved_report('ldl-last-year','2025-09-03')
        noise=[saved_report('unrelated-'+str(i),'2026-0'+str(i+1)+'-03','尿酸') for i in range(8)]
        new=saved_report('ldl-this-year','2026-10-01',value='3.0')
        local=[{'id':'current-chat','messages':[{'media_id':item['id']} for item in noise[-2:]]}]
        context=self.context([old,*noise,new],'去年9月与今年复查的LDL相比有什么变化？',conversations=local)
        self.assertEqual([item['id'] for item in context],['ldl-last-year','ldl-this-year'])
        self.assertEqual([item['tests'][0]['date'] for item in context],['2025-09-03','2026-10-01'])
        self.assertTrue(all(item['tests'][0]['unit']=='mmol/L' for item in context))
        self.assertTrue(all(item['review_status']=='pending' for item in context))

    def test_alias_and_named_metric_keep_old_report_without_date(self):
        old=saved_report('old-ldl','2025-09-03','低密度脂蛋白胆固醇')
        media=[old,*[saved_report('noise-'+str(i),'2026-10-01','尿酸') for i in range(7)]]
        self.assertEqual([item['id'] for item in self.context(media,'LDL这个指标是什么情况？')],['old-ldl'])

    def test_named_late_metric_survives_normalization_and_context_budget(self):
        rows=[{'name':'其他指标'+str(i),'value':i,'unit':'U/L','reference':'0-100','date':'2026-10-01'} for i in range(45)]
        rows.append({'name':'载脂蛋白B','value':'1.3','unit':'g/L','reference':'0.6-1.1','date':'2026-10-01'})
        report=nutrition_reports.report({'tests':rows},'report')
        self.assertEqual(len(report['tests']),46)
        media={'id':'many-tests','type':'report','review':{'report':report}}
        context=self.context([media],'请解释这张报告的载脂蛋白B。',selected=[media])
        self.assertLessEqual(len(context[0]['tests']),40)
        row=next(row for row in context[0]['tests'] if row['name']=='载脂蛋白B')
        self.assertEqual((row['value'],row['unit'],row['reference'],row['date']),('1.3','g/L','0.6-1.1','2026-10-01'))
        self.assertGreater(context[0]['omitted_test_count'],0)

    def test_single_selected_report_stays_focused_and_unknown_ownership_stays_unknown(self):
        old=saved_report('old','2025-09-01')
        new=saved_report('new','2026-10-01')
        self.assertEqual([item['id'] for item in self.context([old,new],'这张报告的LDL怎么理解？',[new])],['new'])
        context=self.context([old,new],'对比两次LDL检查。')
        self.assertTrue(all(item['ownership_status']=='unverified' for item in context))
        self.assertTrue(all('归属' in item['comparison_notice'] for item in context))

    def test_disabled_retracted_dismissed_media_and_food_never_return(self):
        blocked=[saved_report('disabled','2025-09-01',memory_enabled=False),
                 saved_report('retracted','2025-09-01',status='retracted'),
                 saved_report('dismissed','2025-09-01',review_status='dismissed')]
        food={'id':'food','type':'food','review':{'report':{'kind':'food','foods':[{'name':'米饭'}]}}}
        good=saved_report('good','2026-10-01')
        before=copy.deepcopy([*blocked,food,good])
        context=self.context([*blocked,food,good],'对比所有LDL检查报告。',selected=blocked)
        self.assertEqual([item['id'] for item in context],['good'])
        self.assertEqual([*blocked,food,good],before)

    def test_report_storage_bound_and_missing_ocr_are_explicit(self):
        rows=[{'name':'指标'+str(i),'value':i,'date':'2026-10-01'} for i in range(230)]
        rows[0]['value']=None
        report=nutrition_reports.report({'tests':rows},'report')
        self.assertEqual(len(report['tests']),200)
        self.assertEqual(report['tests'][0]['value'],'未识别')
        self.assertEqual(report['coverage']['omitted_count'],30)
        self.assertGreater(report['coverage']['unreadable_fields_count'],0)
        self.assertIn('遗漏',report['notice'])

    def test_requested_missing_date_is_not_presented_as_an_available_comparison(self):
        new=saved_report('new','2026-10-01')
        context=self.context([new],'对比去年9月与今年复查LDL。')
        self.assertEqual(context[0]['unmatched_requested_dates'],['2025-09'])
        self.assertIn('未找到',context[0]['comparison_notice'])

    def test_exact_day_uses_named_metric_date_not_another_row_or_upload_date(self):
        old=saved_report('exact','2026-09-01')
        new=saved_report('later','2026-09-17')
        old['created_at']='2026-10-18T12:00:00'
        old['review']['report']['tests'].append({'name':'尿酸','date':'2026-10-19','value':'400'})
        context=self.context([old,new],'查一下2026年9月1日的LDL报告。')
        self.assertEqual([item['id'] for item in context],['exact'])
        missing=self.context([old],'今年10月复查的LDL报告在哪？')
        self.assertEqual(missing[0]['unmatched_requested_dates'],['2026-10'])

    def test_invalid_metric_date_stays_unknown_instead_of_matching_prefix(self):
        media=saved_report('invalid-date','2026-13-01')
        context=self.context([media],'今年1月的LDL报告。')
        self.assertEqual(context[0]['unmatched_requested_dates'],['2026-01'])

    def test_legacy_truncation_is_not_claimed_to_be_a_complete_report(self):
        media=saved_report('legacy','2026-10-01')
        media['review']['report'].pop('coverage')
        media['review']['report'].pop('notice')
        context=self.context([media],'请解释这张报告。',[media])
        self.assertEqual(context[0]['coverage_status'],'unknown')
        self.assertIn('未列出不等于',context[0]['notice'])


if __name__=='__main__':unittest.main()
