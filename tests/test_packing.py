from envs.env import Action
from envs.inventory import Inventory
from envs.layout import PACKING_LAYOUT, WIDE_LAYOUT, Layout
from envs.missions import MakeupMissionEnv
from pipelines.baselines import HeuristicPolicy
from api._cloud import SignedSessions
from api._viewer import ViewerSession


def test_conveyor_footprint_and_docking_are_physical():
    layout=Layout.load(PACKING_LAYOUT)
    assert layout.dispatch_cells == {(22,16),(23,16)}
    for blocked in (False,True):
        assert layout.approaches('DELIVERY',blocked)=={(21,16)}
        assert not layout.free((22,16),blocked) and not layout.free((23,16),blocked)
        assert layout.base in layout.distance_field('DELIVERY',blocked)
    layout.validate_routes()


def test_delivery_requires_the_conveyor_intake_side():
    sku='TMP-E01-L1'
    env=MakeupMissionEnv(inventory=Inventory({sku:1}))
    obs,_=env.reset(seed=0);policy=HeuristicPolicy()
    while env.state.etapa!='entregar' or env.lift_phase!='idle':
        obs,_,_,_,_=env.step(policy.action(obs,env))
    # Poses controladas para verificar acceso lateral, sin simular navegación falsa.
    env.state.x,env.state.y,env.state.theta,env.state.v=22,15,2,0
    assert not env.facing_target()
    _,_,_,_,info=env.step(Action.DESCARGAR)
    assert info['deliveries']==0 and env.carried_lines
    env.state.x,env.state.y,env.state.theta=21,16,1
    assert env.facing_target()
    _,_,_,_,info=env.step(Action.DESCARGAR)
    assert info['success'] and info['deliveries']==1
    assert env.inventory.total[sku]==0
    env.inventory.check()


def test_pre_conveyor_session_keeps_old_map_until_new_order():
    session=ViewerSession(layout_path=WIDE_LAYOUT,settings={'makeup':True,'seed':42})
    for _ in range(5):session.step()
    signed=SignedSessions('unit-test-packing-migration-secret-32-characters')
    restored=signed.load(signed.dump(session))
    assert restored.env.layout.data['version']=='0.3.0'
    assert restored.env.layout.free((23,16))
    assert restored.payload()==session.payload()
    restored.reset({'makeup':True,'seed':1})
    assert restored.env.layout.data['version']=='0.4.0'
    assert not restored.env.layout.free((23,16))
