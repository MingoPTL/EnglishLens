import unittest
from unittest.mock import patch
import dictionary_service as service

class VocabularyTests(unittest.TestCase):
    def setUp(self):
        service.translation_cache.clear()

    @patch.object(service, 'lookup')
    @patch.object(service, 'translate_vi')
    def test_translation_and_example_share_dictionary_sense(self, get, lookup):
        get.return_value = 'cái chai'
        lookup.return_value = 200, [{'phonetics': [{'text': '/bɒtl/'}], 'meanings': [{'definitions': [{'definition': 'first sense'}, {'definition': 'a container', 'example': 'Fill the bottle.'}]}]}]
        code, data = service.vocabulary(' Bottle ')
        self.assertEqual(code, 200)
        self.assertEqual(data['meaning'], 'cái chai')
        self.assertEqual(data['definition'], 'a container')
        self.assertEqual(data['example'], 'Fill the bottle.')
        self.assertEqual(data['phonetic'], '/bɒtl/')
        get.assert_called_once_with('bottle')
        self.assertEqual(data['translationSource'], 'Argos Translate')
        service.vocabulary('bottle')
        self.assertEqual(get.call_count, 1)

    @patch.object(service, 'lookup', return_value=(404, {}))
    @patch.object(service, 'translate_vi')
    def test_missing_model_does_not_cache_failure(self, get, lookup):
        get.side_effect = RuntimeError('Model missing')
        code, data = service.vocabulary('bottle')
        self.assertEqual(code, 200)
        self.assertEqual(data['meaning'], '')
        self.assertEqual(data['example'], '')
        self.assertEqual(len(data['warnings']), 2)
        self.assertFalse(service.translation_cache)

    @patch.object(service, 'lookup', return_value=(200, [{'meanings': [{'definitions': [{'definition': 'a lamp'}]}]}]))
    @patch.object(service, 'translate_vi', side_effect=RuntimeError('Model missing'))
    def test_translation_failure_keeps_dictionary_data(self, get, lookup):
        _, data = service.vocabulary('lamp')
        self.assertEqual(data['definition'], 'a lamp')
        self.assertEqual(data['example'], '')
        self.assertTrue(data['warnings'])

    @patch.object(service, 'translate_vi')
    def test_invalid_input_never_calls_external_api(self, get):
        self.assertEqual(service.vocabulary('https://evil.test')[0], 400)
        get.assert_not_called()

if __name__ == '__main__':
    unittest.main()
