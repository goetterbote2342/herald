#!/usr/bin/env python3
"""Set the MSI's installed product description in the Windows user's language."""
from contextlib import contextmanager
import ctypes as C
from locale import windows_locale
from pathlib import Path
import shutil
import sys
from tempfile import TemporaryDirectory

from product_descriptions import descriptions

SEQUENCE = 'InstallExecuteSequence'
INSTALL_OR_REPAIR = 'NOT (REMOVE~="ALL")'
FALLBACK_ACTION = 'JpSetARPCOMMENTS'


def localized_actions():
    for locale, description in descriptions().items():
        if locale == 'en':
            continue
        languages = sorted(lcid for lcid, name in windows_locale.items() if lcid <= 65535 and
                           (name == locale or name.split('_')[0] == locale))
        if not languages:
            raise ValueError(f'No Windows language IDs for {locale}')
        # A single Windows Installer condition can contain at most 255 characters.
        for offset in range(0, len(languages), 8):
            selected = ' OR '.join(f'UserLanguageID={lcid}' for lcid in languages[offset:offset + 8])
            yield f'KylleneDescription_{locale}_{offset // 8}', f'{INSTALL_OR_REPAIR} AND ({selected})', description


def checked(result):
    if result:
        raise C.WinError(result)


@contextmanager
def handle(msi, create):
    value = create()
    try:
        yield value
    finally:
        msi.MsiCloseHandle(value)


class Database:
    def __init__(self, msi, handle):
        self.msi = msi
        self.handle = handle

    def execute(self, sql, values=(), columns=()):
        msi = self.msi
        view = C.c_uint()
        checked(msi.MsiDatabaseOpenViewW(self.handle, C.c_wchar_p(sql), C.byref(view)))
        with handle(msi, lambda: view.value) as query, handle(msi, lambda: msi.MsiCreateRecord(len(values))) as record:
            for index, item in enumerate(values, 1):
                result = (msi.MsiRecordSetInteger(record, index, item) if isinstance(item, int) else
                          msi.MsiRecordSetStringW(record, index, C.c_wchar_p(item)))
                checked(result)
            checked(msi.MsiViewExecute(query, record))
            data = []
            row = C.c_uint()
            while columns:
                status = msi.MsiViewFetch(query, C.byref(row))
                if status == 259:  # ERROR_NO_MORE_ITEMS
                    break
                checked(status)
                with handle(msi, lambda: row.value) as record_handle:
                    data.append(tuple(self.column(record_handle, i, kind) for i, kind in enumerate(columns, 1)))
            return data

    def column(self, record, index, kind):
        if kind is int:
            return self.msi.MsiRecordGetInteger(record, index)
        buffer = C.create_unicode_buffer(512)
        size = C.c_uint(len(buffer))
        checked(self.msi.MsiRecordGetStringW(record, index, buffer, C.byref(size)))
        return buffer.value


@contextmanager
def database(msi, path, mode):
    value = C.c_uint()
    checked(msi.MsiOpenDatabaseW(C.c_wchar_p(str(path)), C.c_void_p(mode), C.byref(value)))
    with handle(msi, lambda: value.value) as db:
        yield Database(msi, db)


def localize(path):
    msi = C.WinDLL('msi')
    with TemporaryDirectory(dir=path.parent) as scratch:
        directory = Path(scratch)
        working = directory / path.name
        shutil.copyfile(path, working)
        fallback = descriptions()['en']
        actions = list(localized_actions())
        with database(msi, working, 1) as db:  # Transacted write.
            sequence = dict(db.execute(f'SELECT `Action`, `Sequence` FROM `{SEQUENCE}`', columns=(str, int)))
            # REMOVE may only be resolved at InstallValidate. Set the fallback and translation
            # after that point and before Windows registers the product description.
            occupied = set(sequence.values())
            slots = [slot for slot in range(sequence['RegisterProduct'] - 1, sequence['InstallValidate'], -1)
                     if slot not in occupied][:len(actions) + 1]
            if len(slots) != len(actions) + 1:
                raise ValueError('No sequence slots for localized product descriptions')
            # One MSI needs to hold both accented Latin text and Simplified Chinese.
            codepage = directory / '_ForceCodepage.idt'
            codepage.write_bytes(b'\r\n\r\n65001\t_ForceCodepage\r\n')
            checked(msi.MsiDatabaseImportW(db.handle, C.c_wchar_p(scratch), C.c_wchar_p(codepage.name)))
            db.execute('UPDATE `CustomAction` SET `Target` = ? WHERE `Action` = ?', (fallback, FALLBACK_ACTION))
            db.execute(f'UPDATE `{SEQUENCE}` SET `Condition` = ?, `Sequence` = ? WHERE `Action` = ?',
                       (INSTALL_OR_REPAIR, slots.pop(), FALLBACK_ACTION))
            for (name, condition, value), slot in zip(actions, slots):
                db.execute('INSERT INTO `CustomAction` (`Action`, `Type`, `Source`, `Target`) VALUES (?, ?, ?, ?)',
                           (name, 51, 'ARPCOMMENTS', value))
                db.execute(f'INSERT INTO `{SEQUENCE}` (`Action`, `Condition`, `Sequence`) VALUES (?, ?, ?)',
                           (name, condition, slot))
            checked(msi.MsiDatabaseCommit(db.handle))
        with database(msi, working, 0) as db:
            for name, _, value in [(FALLBACK_ACTION, INSTALL_OR_REPAIR, fallback), *actions]:
                if db.execute('SELECT `Target` FROM `CustomAction` WHERE `Action` = ?', (name,),
                              columns=(str,)) != [(value,)]:
                    raise ValueError(f'MSI lost the product description for {name}')
        working.replace(path)


if __name__ == '__main__':
    localize(Path(sys.argv[1]).resolve(strict=True))
