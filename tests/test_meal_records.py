import copy
import unittest
import test_workbench
import product
import server


class MealCorrectionTests(unittest.TestCase):
    def setUp(self):
        test_workbench.WorkbenchTests.setUp(self)
        self.record=server.prepare_record({'type':'meal','value':{'description':'午餐米饭和蔬菜',
            'nutrition':{'kcal':[400,600],'protein_g':[10,20]}}})
        self.record.update(occurred_at=product.today(),media_id='food-1')
        server.save_json(server.RECORDS,[self.record])
        self.payload={'id':self.record['id'],'operation':'edit','date':product.today(),
                      'description':'午餐实际吃了一半','nutrition_mode':'scale','factor':0.5}

    def tearDown(self):test_workbench.WorkbenchTests.tearDown(self)

    def preview(self,**kw):return product.action(server,{'action':'meal_preview',**self.payload,**kw})
    def commit(self,**kw):
        preview=self.preview(**kw)
        return product.action(server,{'action':'meal_commit',**self.payload,**kw,'token':preview['token']})

    def test_preview_is_read_only_and_commit_preserves_identity_and_unknowns(self):
        before=product.snapshot(server)
        preview=self.preview()
        self.assertEqual(product.snapshot(server),before)
        result=product.action(server,{'action':'meal_commit',**self.payload,'token':preview['token']})
        after=server.records()[0]
        self.assertEqual(after['id'],self.record['id']);self.assertEqual(after['media_id'],'food-1')
        self.assertEqual(after['value']['nutrition']['kcal'],[200,300])
        self.assertIsNone(after['value']['nutrition']['fat_g'])
        self.assertEqual(product.snapshot(server)['food_summary']['totals']['kcal']['range'],[200,300])
        product.action(server,{'action':'meal_commit',**self.payload,'token':preview['token']})
        self.assertEqual(len(product.snapshot(server)['meal_corrections']),1)
        product.action(server,{'action':'meal_undo','correction_id':result['correction_id']})
        self.assertEqual(server.records(),[self.record])
        self.assertEqual(server.load_json(server.MEDIA,[]),before['media'])
        self.commit()  # Same correction is allowed again after a fresh preview.

    def test_stale_preview_cannot_overwrite_later_update(self):
        preview=self.preview();changed=copy.deepcopy(self.record);changed['value']['description']='新记录'
        server.save_json(server.RECORDS,[changed])
        with self.assertRaises(product.ProductError):
            product.action(server,{'action':'meal_commit',**self.payload,'token':preview['token']})
        self.assertEqual(server.records(),[changed])

    def test_preview_token_binds_payload_and_photo_state(self):
        preview=self.preview()
        with self.assertRaises(product.ProductError):
            product.action(server,{'action':'meal_commit',**self.payload,'factor':2,'token':preview['token']})
        media=server.load_json(server.MEDIA,[]);media[0]['review']['summary']='更新后的照片分析'
        server.save_json(server.MEDIA,media)
        with self.assertRaises(product.ProductError):
            product.action(server,{'action':'meal_commit',**self.payload,'token':preview['token']})
        self.assertEqual(server.records(),[self.record])
        self.assertEqual(product.snapshot(server)['meal_corrections'],[])

    def test_undo_preserves_unrelated_new_records_but_rejects_changed_target(self):
        result=self.commit();other=server.prepare_record({'type':'weight','value':{'kg':80}})
        server.save_json(server.RECORDS,server.records()+[other])
        product.action(server,{'action':'meal_undo','correction_id':result['correction_id']})
        self.assertEqual(server.records(),[self.record,other])
        result=self.commit();changed=server.records();changed[0]['value']['description']='后来更正'
        server.save_json(server.RECORDS,changed)
        with self.assertRaises(product.ProductError):product.action(server,{'action':'meal_undo','correction_id':result['correction_id']})
        self.assertEqual(server.records(),changed)

    def test_remove_and_persisted_undo_restore_record_without_deleting_photo(self):
        result=self.commit(operation='remove')
        self.assertEqual(server.records(),[])
        self.assertEqual(len(server.load_json(server.MEDIA,[])),1)
        self.assertEqual(product.snapshot(server)['food_summary']['record_count'],0)
        product.action(server,{'action':'meal_undo','correction_id':result['correction_id']})
        self.assertEqual(server.records(),[self.record])
        with self.assertRaises(product.ProductError):product.action(server,{'action':'meal_undo','correction_id':result['correction_id']})

    def test_invalid_payloads_and_unknown_nutrition(self):
        for patch in ({'factor':float('nan')},{'factor':-1},{'factor':True},{'date':'2099-01-01'},
                      {'description':''},{'id':'missing'},{'operation':'invent'}):
            with self.subTest(patch=patch),self.assertRaises(product.ProductError):self.preview(**patch)
        self.commit(nutrition_mode='unknown')
        self.assertTrue(all(v is None for v in server.records()[0]['value']['nutrition'].values()))
