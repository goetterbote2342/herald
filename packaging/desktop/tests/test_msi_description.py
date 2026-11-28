from pathlib import Path
import re
import runpy
import sys
import unittest

PACKAGING = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PACKAGING))
try:
    localized_actions = runpy.run_path(str(PACKAGING / 'localize-msi-description.py'))['localized_actions']
finally:
    sys.path.pop(0)


class MsiDescriptionTest(unittest.TestCase):
    def test_description_follows_windows_user_language_with_english_fallback(self):
        values = {}
        for _, condition, text in localized_actions():
            self.assertLessEqual(len(condition), 255)
            self.assertTrue(condition.startswith('NOT Installed AND'))
            for lcid in map(int, re.findall(r'UserLanguageID=(\d+)', condition)):
                self.assertNotIn(lcid, values)
                values[lcid] = text

        self.assertNotIn(1033, values)  # English uses the description already on the MSI.
        self.assertNotIn(2070, values)  # The app ships Brazilian Portuguese.
        self.assertEqual(values[1046], 'Um cliente de desktop para o Hermes Agent.')
        self.assertEqual(values[2052], 'Hermes Agent 的桌面客户端。')
        self.assertEqual(values[3084], 'Un client de bureau pour Hermes Agent.')  # French (Canada).
        self.assertEqual(values[2058], 'Un cliente de escritorio para Hermes Agent.')  # Spanish (Mexico).
