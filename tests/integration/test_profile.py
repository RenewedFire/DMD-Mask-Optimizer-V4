import hashlib
import json
import os
import struct
import zipfile
from pathlib import Path

import pytest

from scripts import lock_profile as module


ROOT = Path(__file__).resolve().parents[2]


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_pe(path, machine=0x8664):
    dos = bytearray(64)
    dos[:2] = b'MZ'
    struct.pack_into('<I', dos, 60, len(dos))
    path.write_bytes(dos + b'PE\0\0' + struct.pack('<H', machine) + bytes(18))


@pytest.fixture
def case(tmp_path, monkeypatch):
    profile_path = tmp_path / 'profile.json'
    profile = json.loads((ROOT / 'profiles' / 'twst_405.json').read_text(encoding='utf-8'))
    rom = tmp_path / 'selected.zip'
    with zipfile.ZipFile(rom, 'w') as archive:
        archive.writestr(zipfile.ZipInfo('dmd.rom'), b'123456789')
        archive.writestr(zipfile.ZipInfo('cpu.rom'), b'abc')
    dump = tmp_path / 'selected.txt'
    dump.write_bytes(b'2026 synthetic capture\n0123\n')
    profile['rom_sha256'] = sha256(rom)
    profile['dump_sha256'] = sha256(dump)
    profile['rom_members'] = [
        {'name': 'cpu.rom', 'size': 3, 'crc32': '352441c2',
         'sha256': 'ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad'},
        {'name': 'dmd.rom', 'size': 9, 'crc32': 'cbf43926',
         'sha256': '15e2b0d3c33891ebb0f1ef609ec419420c20e320ce94c65fbc8c3312448eb225'},
    ]
    toolchain = tmp_path / 'toolchain'
    for name, record in profile['components'].items():
        target = toolchain / record['binary']
        target.parent.mkdir(parents=True, exist_ok=True)
        write_pe(target)
        record.update(architecture='x64', sha256=sha256(target),
                      build_command=f'Build-Synthetic {name}', compiler='Synthetic Compiler 1.0',
                      compiler_flags=['/O2'], dependencies={}, pending=[],
                      release_archive_sha256='f' * 64)
    decoder = profile['components']['bundled decoder']
    decoder['binary_version'] = decoder['source_version']
    for name, dependency in [('ColorizingDMD editor', 'editor/LiteZip.dll'), ('PinMAME 3.6', 'pinmame/Bass64.dll')]:
        target = toolchain / dependency
        target.write_bytes(b'synthetic dependency')
        profile['components'][name]['dependencies'][dependency] = sha256(target)

    def save_profile():
        profile_path.write_text(json.dumps(profile), encoding='utf-8')

    save_profile()
    monkeypatch.setattr(module, 'PROFILE_PATH', profile_path)
    return rom, dump, toolchain, profile, save_profile


def test_profile(case):
    rom, dump, toolchain, profile, _ = case
    locked = module.lock_profile(rom, dump, toolchain)
    assert locked.rom_sha256 == profile['rom_sha256']
    assert locked.dump_sha256 == profile['dump_sha256']
    assert [(member.name, member.size, member.crc32, member.sha256)
            for member in locked.rom_members] == [
        (item['name'], item['size'], item['crc32'], item['sha256'])
        for item in profile['rom_members']
    ]
    assert (locked.width, locked.height, locked.native_shades) == (128, 32, 4)
    assert locked.native_binaries_verified
    assert locked.profile_sha256 == module.lock_profile(rom, dump, toolchain).profile_sha256


@pytest.mark.parametrize(('index', 'component'), [(0, 'ROM'), (1, 'dump')])
def test_rejects_changed_fixture(case, index, component):
    case[index].write_bytes(b'changed')
    with pytest.raises(module.ProfileError, match=rf'{component}.*SHA-256'):
        module.lock_profile(*case[:3])


@pytest.mark.parametrize(('field', 'value'), [('size', 4), ('crc32', 'ffffffff'), ('sha256', 'f' * 64)])
def test_rejects_incorrect_rom_inventory(case, field, value):
    _, _, _, profile, save_profile = case
    profile['rom_members'][0][field] = value
    save_profile()
    with pytest.raises(module.ProfileError, match=rf'ROM member inventory.*cpu\.rom.*{field}'):
        module.lock_profile(*case[:3])


@pytest.mark.parametrize(('members', 'diagnostic'), [
    ('missing', r'expected ROM member .*absent\.rom.*missing from the archive'),
    ('unexpected', r'unexpected ROM member .*cpu\.rom.*in the archive'),
])
def test_names_missing_or_unexpected_rom_member(case, members, diagnostic):
    _, _, _, profile, save_profile = case
    if members == 'missing':
        profile['rom_members'].append({**profile['rom_members'][0], 'name': 'absent.rom'})
    else:
        profile['rom_members'].pop(0)
    save_profile()
    with pytest.raises(module.ProfileError, match=diagnostic):
        module.lock_profile(*case[:3])


@pytest.mark.parametrize('name', ['ColorizingDMD editor', 'bundled decoder', 'PinMAME 3.6'])
def test_requires_every_native_component(case, name):
    _, _, _, profile, save_profile = case
    del profile['components'][name]
    save_profile()
    with pytest.raises(module.ProfileError, match=rf'{name}: missing required component'):
        module.lock_profile(*case[:3])


@pytest.mark.parametrize(('replacement', 'diagnostic'), [
    ({}, 'ColorizingDMD editor: missing required component'),
    ([], 'profile.*components.*object'),
    (None, 'profile.*components.*object'),
])
def test_rejects_empty_or_malformed_components_map(case, replacement, diagnostic):
    _, _, _, profile, save_profile = case
    profile['components'] = replacement
    save_profile()
    with pytest.raises(module.ProfileError, match=diagnostic):
        module.lock_profile(*case[:3])


def test_rejects_empty_component_record(case):
    _, _, _, profile, save_profile = case
    profile['components']['bundled decoder'] = {}
    save_profile()
    with pytest.raises(module.ProfileError, match='bundled decoder.*missing.*binary'):
        module.lock_profile(*case[:3])


@pytest.mark.parametrize(('field', 'value'), [
    ('architecture', 'x128'), ('binary', 'editor/../elsewhere.exe'),
    ('build_command', None), ('build_command', ''), ('compiler', ' '),
    ('compiler_flags', '/O2'), ('compiler_flags', []), ('dependencies', []), ('dependencies', None),
    ('dependencies', {}),
    ('pending', 'not a list'), ('release_archive_sha256', None), ('sha256', None), ('sha256', 'a' * 63),
    ('source_commit', '3721691'), ('source_commit', 'g' * 40),
])
def test_names_invalid_native_fields(case, field, value):
    _, _, _, profile, save_profile = case
    profile['components']['ColorizingDMD editor'][field] = value
    if field == 'release_archive_sha256':
        del profile['components']['ColorizingDMD editor']['provenance']
    save_profile()
    with pytest.raises(module.ProfileError, match=rf'ColorizingDMD editor.*{field}'):
        module.lock_profile(*case[:3])


def test_cli_names_missing_build_command_without_traceback(case, capsys):
    rom, dump, toolchain, profile, save_profile = case
    del profile['components']['ColorizingDMD editor']['build_command']
    save_profile()
    assert module.main(['--rom', str(rom), '--dump', str(dump), '--toolchain', str(toolchain)]) == 1
    output = capsys.readouterr()
    assert 'ColorizingDMD editor: missing build_command' in output.err
    assert not output.out


@pytest.mark.parametrize('digest', [None, '', 'x' * 64])
def test_rejects_deactivated_dependency_hash(case, digest):
    _, _, toolchain, profile, save_profile = case
    dependency = 'pinmame/Bass64.dll'
    (toolchain / dependency).write_bytes(b'original')
    profile['components']['PinMAME 3.6']['dependencies'][dependency] = digest
    save_profile()
    with pytest.raises(module.ProfileError, match=r'PinMAME 3\.6.*dependencies.*Bass64\.dll.*SHA-256'):
        module.lock_profile(*case[:3])


def test_rejects_decoder_source_from_another_commit(case):
    _, _, _, profile, save_profile = case
    profile['components']['bundled decoder']['source_commit'] = 'b' * 40
    save_profile()
    with pytest.raises(module.ProfileError, match='bundled decoder.*source_commit.*ColorizingDMD editor'):
        module.lock_profile(*case[:3])


def test_decoder_version_mismatch_remains_unavailable_without_pending_notice(case):
    _, _, _, profile, save_profile = case
    profile['components']['bundled decoder']['binary_version'] = '2.2.0'
    del profile['components']['bundled decoder']['provenance']
    save_profile()
    with pytest.raises(module.ProfileError, match='bundled decoder.*binary_version.*source_version'):
        module.lock_profile(*case[:3])


@pytest.mark.parametrize('name', ['ColorizingDMD editor', 'bundled decoder', 'PinMAME 3.6'])
def test_names_changed_binary(case, name):
    rom, dump, toolchain, profile, _ = case
    target = toolchain / profile['components'][name]['binary']
    target.write_bytes(target.read_bytes() + b'changed')
    with pytest.raises(module.ProfileError, match=rf'{name}.*SHA-256'):
        module.lock_profile(rom, dump, toolchain)


def test_names_missing_binary(case):
    rom, dump, toolchain, profile, _ = case
    (toolchain / profile['components']['PinMAME 3.6']['binary']).unlink()
    with pytest.raises(module.ProfileError, match=r'PinMAME 3\.6.*missing.*VPinMAME64\.dll'):
        module.lock_profile(rom, dump, toolchain)


def test_names_changed_dependency(case):
    rom, dump, toolchain, profile, save_profile = case
    dependency = 'pinmame/Bass64.dll'
    target = toolchain / dependency
    target.write_bytes(b'original')
    profile['components']['PinMAME 3.6']['dependencies'][dependency] = sha256(target)
    save_profile()
    assert module.lock_profile(rom, dump, toolchain).native_binaries_verified
    target.write_bytes(b'changed')
    with pytest.raises(module.ProfileError, match=r'PinMAME 3\.6 dependency .*Bass64\.dll.*SHA-256'):
        module.lock_profile(rom, dump, toolchain)


def test_rejects_wrong_binary_architecture_even_when_hashed(case):
    rom, dump, toolchain, profile, save_profile = case
    record = profile['components']['bundled decoder']
    target = toolchain / record['binary']
    write_pe(target, machine=0x014C)
    record['sha256'] = sha256(target)
    save_profile()
    with pytest.raises(module.ProfileError, match='bundled decoder.*architecture.*x64.*x86'):
        module.lock_profile(rom, dump, toolchain)


def test_names_pending_native_provenance(case):
    _, _, _, profile, save_profile = case
    profile['components']['bundled decoder']['pending'] = ['verified build provenance']
    save_profile()
    with pytest.raises(module.ProfileError, match='bundled decoder.*verified build provenance'):
        module.lock_profile(*case[:3])


def test_accepts_explicit_local_installation_provenance(case):
    rom, dump, toolchain, profile, save_profile = case
    for component in profile['components'].values():
        component['release_archive_sha256'] = None
        component['provenance'] = {
            'kind': 'local-installation',
            'installation_path': r'C:\\vPinball\\VisualPinball\\VPinMAME',
        }
    save_profile()
    assert module.lock_profile(rom, dump, toolchain).native_binaries_verified


def test_rejects_local_installation_without_absolute_path(case):
    _, _, _, profile, save_profile = case
    component = profile['components']['PinMAME 3.6']
    component['release_archive_sha256'] = None
    component['provenance'] = {'kind': 'local-installation', 'installation_path': 'VPinMAME'}
    save_profile()
    with pytest.raises(module.ProfileError, match=r'PinMAME 3\.6.*provenance.*installation_path'):
        module.inspect_fixtures(*case[:2])


@pytest.mark.skipif(os.environ.get('DMD_PROFILE_LOCAL') != '1', reason='requires local fixtures')
def test_local_twister_fixture():
    case = module.inspect_fixtures(ROOT / 'twst_405.zip', ROOT / 'twst_405.txt')
    assert case.rom_sha256 == '7419195a51f1295e9f928e0105326cba3c4e32b9b2d3b59c004f773d132707a3' and case.dump_sha256 == 'f711aec5d42fdc423ca02bfd2c8f05c158afaee27a97acdbf59d532b81095b11'.lower()
    assert len(case.rom_members) == 5


@pytest.mark.skipif(os.environ.get('DMD_LOCAL_RUNTIME') != '1', reason='requires staged local runtime')
def test_local_runtime_baseline_locks_twister_fixture():
    profile = module.lock_profile(
        ROOT / 'twst_405.zip',
        ROOT / 'twst_405.txt',
        ROOT / 'artifacts' / '2026-11-18-task-1-fix-3' / 'toolchain',
    )
    assert profile.native_binaries_verified
