import json
import zlib
import hmac
from hashlib import sha256
from base64 import urlsafe_b64decode, urlsafe_b64encode

from warehouse_rush.cloud import CloudAPI, SignedSessions
from warehouse_rush.env import WarehouseRushEnv
from warehouse_rush.layout import Layout, DEFAULT_LAYOUT, WIDE_LAYOUT
from warehouse_rush.missions import MakeupMissionEnv
from warehouse_rush.viewer import ViewerSession

SECRET = 'unit-test-layout-transition-secret-32-characters'


def test_wide_layout_has_real_aisles_and_alternative_route():
    layout = Layout.load(WIDE_LAYOUT)
    assert (layout.width, layout.height) == (25, 19)
    racks = layout.data['racks']
    for row in (racks[:3], racks[3:]):
        assert all(right['bounds'][0] - left['bounds'][2] - 1 >= 5 for left, right in zip(row, row[1:]))
    assert all(bottom['bounds'][1] - top['bounds'][3] - 1 >= 4 for top, bottom in zip(racks[:3], racks[3:]))
    routes = layout.validate_routes()
    assert routes['blocked']['P1'] > routes['normal']['P1']
    env = MakeupMissionEnv()
    for blocked in (False, True):
        for i in range(1, 7):
            assert env.layout.base in env._fields[blocked, f'E{i:02d}']


def test_legacy_training_layout_and_contract_remain_unchanged():
    env = WarehouseRushEnv()
    observation, _ = env.reset(seed=42)
    assert env.layout.source == DEFAULT_LAYOUT.resolve()
    assert (env.layout.width, env.layout.height) == (17, 13)
    assert env.config.battery_capacity == 100 and env.config.max_steps == 250
    assert observation.shape == (22,) and env.action_space.n == 5


def test_layout_api_matches_signed_state_for_both_modes():
    api = CloudAPI(SECRET)
    for makeup, size in ((True, (25, 19)), (False, (17, 13))):
        payload, token = api.handle('POST', 'reset', {'makeup': makeup, 'orders': 1})
        layout, replacement = api.handle('GET', 'layout', token=token)
        assert replacement is None
        assert (layout['layout']['width'], layout['layout']['height']) == size
        assert layout['layout_sha256'] == payload['info']['layout_sha256']
        restored, _ = api.handle('GET', 'state', token=token)
        assert restored['state'] == payload['state']


def test_pre_wide_cookie_keeps_original_geometry_until_new_order():
    session = ViewerSession(layout_path=DEFAULT_LAYOUT, settings={'makeup': True, 'seed': 42})
    for _ in range(8):
        session.step()
    signed = SignedSessions(SECRET)
    token = signed.dump(session)
    encoded = token.split('.')[0]
    record = json.loads(zlib.decompress(urlsafe_b64decode(encoded + '=' * (-len(encoded) % 4))))
    record.pop('layout_version')  # Cookie realmente anterior al nuevo mapa.
    encoded = urlsafe_b64encode(zlib.compress(json.dumps(record).encode())).decode().rstrip('=')
    token = encoded + '.' + hmac.new(signed.key, encoded.encode(), sha256).hexdigest()
    restored = signed.load(token)
    assert restored.env.layout.width == 17
    assert restored.payload() == session.payload()
    assert restored.step()['state'] == session.step()['state']
    payload = restored.reset({'makeup': True, 'seed': 1})
    assert restored.env.layout.width == 25
    assert (payload['state']['x'], payload['state']['y']) == (3, 16)
    assert len(payload['state']['inventory']['orders']) == 2
