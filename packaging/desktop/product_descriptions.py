from pathlib import Path
import xml.etree.ElementTree as ET

RESOURCES = Path(__file__).resolve().parents[2] / 'shared/ui/src/commonMain/composeResources'


def descriptions():
    result = {}
    for catalogue in sorted(RESOURCES.glob('values*/strings.xml')):
        locale = catalogue.parent.name.removeprefix('values').removeprefix('-').replace('-r', '_') or 'en'
        value = ET.parse(catalogue).findtext('string[@name="desktop_product_description"]')
        if not value or any(char in value for char in ('\\', '\n', '\r', '\t')):
            raise ValueError(f'Expected a plain single-line product description in {catalogue.parent.name}')
        result[locale] = value
    if 'en' not in result:
        raise ValueError('Missing the default product description')
    return result
