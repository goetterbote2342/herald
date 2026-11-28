from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
import sys
import unittest

PACKAGING = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PACKAGING))
try:
    import product_descriptions
finally:
    sys.path.pop(0)


class ProductDescriptionsTest(unittest.TestCase):
    def test_rejects_compose_escapes_before_exporting_native_metadata(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            values = root / 'values'
            values.mkdir()
            (values / 'strings.xml').write_text(
                r'<resources><string name="desktop_product_description">App\nDescription</string></resources>',
                encoding='utf-8',
            )
            with patch.object(product_descriptions, 'RESOURCES', root):
                with self.assertRaisesRegex(ValueError, 'plain.*description'):
                    product_descriptions.descriptions()
