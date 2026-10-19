import copy
import unittest
import server


class SystemMessageTests(unittest.TestCase):
    def test_gateway_receives_both_rules_and_context_without_history_mutation(self):
        source=[{'role':'system','content':'rules'}, {'role':'system','content':'facts'},
                {'role':'user','content':'hello'}, {'role':'assistant','content':'reply'}]
        before=copy.deepcopy(source)
        merged=server.combine_system_messages(source)
        self.assertEqual(merged,[{'role':'system','content':'rules\n\nfacts'},*source[2:]])
        self.assertEqual(source,before)

    def test_multimodal_content_and_nonconsecutive_roles_are_preserved(self):
        source=[{'role':'system','content':'rules'},{'role':'user','content':[{'type':'image_url','image_url':{'url':'fake'}}]},
                {'role':'system','content':'later'},{'role':'system','content':[{'type':'text','text':'block'}]}]
        self.assertEqual(server.combine_system_messages(source),source)


if __name__=='__main__':unittest.main()
