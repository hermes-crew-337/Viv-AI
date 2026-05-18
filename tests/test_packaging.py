import importlib
import unittest


class PackagingTests(unittest.TestCase):
    def test_extractors_constants_match_vivisect_when_available(self):
        extractors = importlib.import_module('viv_ai.extractors')
        vivisect = importlib.import_module('vivisect')

        self.assertEqual(extractors.LOC_IMPORT, vivisect.LOC_IMPORT)
        self.assertEqual(extractors.LOC_STRING, vivisect.LOC_STRING)
        self.assertEqual(extractors.LOC_UNI, vivisect.LOC_UNI)
        self.assertEqual(extractors.REF_CODE, vivisect.REF_CODE)


if __name__ == '__main__':
    unittest.main()
