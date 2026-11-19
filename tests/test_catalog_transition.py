"""Definitive catalogue and immutable legacy books, including signed visitor sessions."""
from copy import deepcopy

import pytest
from api._cloud import SignedSessions, CloudAPI
from envs.inventory import CATALOG, LEGACY_CATALOG, Inventory
from api._viewer import ViewerSession

SECRET = 'catalogue-transition-test-only-secret-32-characters'


def test_fixed_stock_and_approved_distribution():
    inventory=Inventory()
    assert inventory.catalog_version=='trendy-27-v1'
    assert len(inventory.initial)==27
    assert set(inventory.initial.values())==set(range(5,11))
    assert inventory.initial==Inventory().initial
    expected={'E01-L1':3,'E01-L2':3,'E01-L3':6,'E02-L1':2,'E02-L2':1,'E02-L3':1,
              'E03-L1':1,'E03-L2':1,'E04-L1':1,'E04-L2':1,'E04-L3':1,
              'E05-L1':1,'E05-L2':1,'E05-L3':1,'E06-L1':1,'E06-L2':1,'E06-L3':1}
    assert {level:sum(p['level']==level for p in CATALOG.values()) for level in expected}==expected
    assert not any(p['level']=='E03-L3' for p in CATALOG.values())
    assert {p['subcategory'] for p in CATALOG.values() if p['level']=='E01-L1'}=={'Rostro'}
    assert {p['subcategory'] for p in CATALOG.values() if p['level']=='E01-L2'}=={'Labios'}
    assert {p['subcategory'] for p in CATALOG.values() if p['level']=='E01-L3'}=={'Ojos','Cejas'}


def test_kit_is_one_unit_and_reserving_does_not_change_physical_stock():
    sku='TRD-01-04';inventory=Inventory();initial=inventory.total[sku]
    assert CATALOG[sku]['unit']=='kit'
    order=inventory.reserve({sku:1})
    assert inventory.total[sku]==initial and inventory.available(sku)==initial-1
    inventory.pick(order['id'],sku,1)
    assert inventory.total[sku]==initial-1
    inventory.deliver(order['id'],sku)
    assert inventory.total[sku]==initial-1
    assert not inventory.deliver(order['id'],sku)
    inventory.check()


def test_legacy_session_survives_reload_mid_lift_and_is_not_relabelled():
    session=ViewerSession(settings={'makeup':False,'orders':1,'policy':'heuristic'})
    session.inventory=Inventory({sku:5 for sku in LEGACY_CATALOG})
    session.reset({'makeup':True,'orders':1,'seed':42,'policy':'heuristic'})
    # Desde 2026-11-13 el elevador es instantáneo por acción (sin fase 'raising', docs/decisiones.md):
    # «a mitad de la elevación» = bandeja ya subida ('ready') con el pedido sin terminar.
    for _ in range(250):
        if session.env.lift_phase=='ready':break
        assert not session.done
        session.step()
    assert session.env.lift_phase=='ready' and not session.done
    before=deepcopy(session.payload());signed=SignedSessions(SECRET)
    restored=signed.load(signed.dump(session))
    assert restored.payload()==before
    assert restored.inventory.catalog_version=='legacy-18'
    assert all(l['sku'].startswith('TMP-') for l in restored.env.lines)
    assert len(restored.layout_payload()['catalog'])==18
    assert restored.step()['state']==session.step()['state']
    stock=restored.inventory.total.copy()
    restored.reset({'makeup':True,'orders':1,'seed':24})
    assert restored.inventory.total==stock
    assert all(l['sku'].startswith('TMP-') for l in restored.env.lines)
    fresh,_=CloudAPI(SECRET).handle('GET','state')
    assert len(fresh['state']['inventory']['products'])==27
    assert all(p['sku'].startswith('TRD-') for p in fresh['state']['inventory']['products'])


def test_no_implicit_alias_or_mixed_catalogue():
    with pytest.raises(ValueError,match='Inventario inicial inválido'):
        Inventory({'TMP-E01-L1':5,'TRD-01-01':5})
    with pytest.raises(ValueError,match='Líneas inválidas'):
        Inventory().reserve({'TMP-E01-L1':1})


def test_pre_lift_legacy_cookie_uses_legacy_catalogue_for_initial_plan():
    import json, zlib, hmac
    from base64 import urlsafe_b64decode, urlsafe_b64encode
    from hashlib import sha256
    session=ViewerSession(inventory=Inventory({s:5 for s in LEGACY_CATALOG}),
                          settings={'makeup':True,'orders':1,'seed':42})
    signed=SignedSessions(SECRET)
    encoded=signed.dump(session).split('.')[0]
    record=json.loads(zlib.decompress(urlsafe_b64decode(encoded+'='*(-len(encoded)%4))))
    record.pop('mechanism')
    for order in record['inventory']['orders'].values():
        for line in order['lines']:line.pop('height_m')
    encoded=urlsafe_b64encode(zlib.compress(json.dumps(record).encode())).decode().rstrip('=')
    token=encoded+'.'+hmac.new(signed.key,encoded.encode(),sha256).hexdigest()
    restored=signed.load(token)
    assert restored.env.plan['next_sku'].startswith('TMP-')
    assert restored.inventory.total==session.inventory.total
    assert restored.step()['state']['tiempo']==1
