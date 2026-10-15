import unittest
from unittest.mock import patch
import jsonschema
from . import planning

class PlanningTests(unittest.TestCase):
    def test_only_fields_and_bounded_statuses(self):
        field = {'name':'launch_year','kind':'integer','nullable':False,'description':'Year of launch'}
        value = {'status':'ready','fields':[field]}
        jsonschema.validate(value, planning.SCHEMA)
        for extra in ('value','pointer','filter','question'):
            with self.assertRaises(jsonschema.ValidationError):
                jsonschema.validate({'status':'ready','fields':[{**field,extra:'invented'}]}, planning.SCHEMA)
        for value in ({'status':'ready','fields':[]}, {'status':'unsupported','fields':[field]}, {'status':'ready','fields':[field]*13}):
            with self.assertRaises(jsonschema.ValidationError): jsonschema.validate(value, planning.SCHEMA)

    def test_original_question_history_and_audit(self):
        data={'question':'When did it launch?', 'history':[{'role':'user','text':'Voyager 1'}]}
        with patch.object(planning,'generate',return_value=({'status':'needs_clarification','fields':[]},{'recorded':True})) as generate:
            result=planning.handle(object(),data)
        self.assertTrue(result['audit']['recorded'])
        self.assertIn('When did it launch?',generate.call_args.args[1][1]['content'])
        with self.assertRaises(ValueError): planning.handle(object(),{**data,'evidence':[]})
