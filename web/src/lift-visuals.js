import * as THREE from 'three';

// Accesorio telescópico añadido al chasis existente, con bandeja de rodillos.
export class LiftVisuals {
  constructor(view) {
    this.view = view;this.height = this.target = .55;
    this.main = this.build(view.robot);this.avatar = this.build(view.avatar);
  }

  build(parent) {
    const group = new THREE.Group();parent.add(group);
    const metal = this.view.material('lift-metal', 0xa9bac6, {metalness:.75, roughness:.3});
    const pink = this.view.material('lift-platform', 0xe9b8cf, {metalness:.35, roughness:.5});
    const tray = new THREE.Group();group.add(tray);
    const plate = new THREE.Mesh(new THREE.BoxGeometry(.64, .04, .63), pink);plate.position.y=-.025;tray.add(plate);
    for (let i=0;i<5;i++) {
      const roller=new THREE.Mesh(new THREE.CylinderGeometry(.018,.018,.57,12),metal);
      roller.rotation.z=Math.PI/2;roller.position.set(0,0,(i-2)*.115);tray.add(roller);
    }
    const segments=[];
    for (const x of [-.28,.28]) for (let i=0;i<3;i++) {
      const segment = new THREE.Mesh(new THREE.BoxGeometry(.085-i*.015,1,.085-i*.015),metal);
      segment.userData.segment=i;segment.position.x=x;segment.position.z=.28;
      segment.castShadow=true;segments.push(segment);group.add(segment);
    }
    group.traverse(o=>{if(o.isMesh)o.castShadow=true;});
    return {group,tray,segments};
  }

  update(state, enabled) {
    this.main.group.visible=this.avatar.group.visible=enabled;
    this.target=state.lift?.height ?? .55;
  }

  animate(dt) {
    this.height=THREE.MathUtils.lerp(this.height,this.target,1-Math.exp(-dt*12));
    for (const assembly of [this.main,this.avatar]) {
      assembly.tray.position.y=this.height;
      for (const segment of assembly.segments) {
        const length=Math.max(.1,(this.height-.22)/3);
        segment.scale.y=length+.08;
        segment.position.y=.22+(segment.userData.segment+.5)*length;
      }
    }
  }
}
