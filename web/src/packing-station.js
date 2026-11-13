import * as THREE from 'three';

const clamp = THREE.MathUtils.clamp;
const OPEN_ANGLE = -Math.PI * .47;
const DURATION = 3.6;

// Efecto de empaque posterior a una entrega confirmada. No modifica inventario.
export class PackingStation {
  constructor(view) {
    this.view = view;this.epoch = this.lastWall = performance.now();this.elapsed = 0;this.orderId = null;this.items = new Map();
    this.compact = !view.layout.dispatch_area;this.boxX = this.compact ? 0 : 1;
    this.requested = this.delivered = 0;this.complete = false;this.isAnimating = false;
    this.group = new THREE.Group();this.group.name = 'packing-station';
    this.group.position.copy(view.world(...view.layout.stations.DELIVERY));view.scene.add(this.group);
    this.productRoot = new THREE.Group();this.group.add(this.productRoot);
    this.lidAngle = OPEN_ANGLE;
    this.build();
  }

  box(size, position, material, parent = this.group) {
    const mesh = new THREE.Mesh(new THREE.BoxGeometry(...size), material);
    mesh.position.set(...position);mesh.castShadow = mesh.receiveShadow = true;parent.add(mesh);return mesh;
  }

  build() {
    const view = this.view;
    const frame = view.material('packing-frame', 0xd5a6ba, {metalness:.35, roughness:.6});
    const metal = view.material('packing-metal', 0x91a0ab, {metalness:.75, roughness:.3});
    const blush = view.material('packing-box', 0xeabed0, {roughness:.8});
    const inside = view.material('packing-paper', 0xfff4ed, {roughness:.96});
    const ribbon = view.material('packing-ribbon', 0xb96e93, {metalness:.15, roughness:.4});
    if (!this.compact) {
      for (const x of [-.35,.48]) for (const z of [-.31,.31]) {
        this.box([.055,.54,.055],[x,.27,z],metal);
        this.box([.12,.035,.12],[x,.025,z],frame);
      }
      this.box([1.18,.10,.76],[.04,.55,0],frame);
      const canvas=document.createElement('canvas');canvas.width=256;canvas.height=128;
      const ctx=canvas.getContext('2d');ctx.fillStyle='#bcb6ce';ctx.fillRect(0,0,256,128);
      ctx.strokeStyle='#dbd5e7';ctx.lineWidth=5;
      for (const x of [30,100,170,240]) {ctx.beginPath();ctx.moveTo(x-12,40);ctx.lineTo(x+12,64);ctx.lineTo(x-12,88);ctx.stroke();}
      this.beltTexture=new THREE.CanvasTexture(canvas);this.beltTexture.colorSpace=THREE.SRGBColorSpace;
      this.beltTexture.wrapS=THREE.RepeatWrapping;this.beltTexture.repeat.set(2,1);
      const belt=new THREE.Mesh(new THREE.PlaneGeometry(1.08,.64),new THREE.MeshStandardMaterial({map:this.beltTexture,roughness:.9}));
      belt.rotation.x=-Math.PI/2;belt.position.set(.02,.62,0);this.group.add(belt);
      for (const x of [-.44,.51]) {
        const roller=new THREE.Mesh(new THREE.CylinderGeometry(.045,.045,.68,16),metal);
        roller.rotation.x=Math.PI/2;roller.position.set(x,.575,0);this.group.add(roller);
      }
      const intake=this.box([.29,.025,.62],[-.45,.575,0],metal);intake.rotation.z=Math.atan2(.07,.29);
      for (const z of [-.35,.35]) this.box([1.12,.06,.025],[.02,.65,z],frame);
      this.buildLabel('DESPACHO · EMPAQUE', [.02,.48,.39], .90,.13);
    }
    // La caja descansa sobre una mesa baja; ninguna unidad se coloca en el suelo.
    const bx=this.boxX;
    for (const x of [bx-.34,bx+.34]) for (const z of [-.34,.34]) this.box([.045,.25,.045],[x,.125,z],metal);
    this.box([.98,.05,.98],[bx,.255,0],frame);
    this.box([.94,.04,.94],[bx,.30,0],inside);
    for (const x of [bx-.45,bx+.45]) this.box([.04,.28,.94],[x,.46,0],blush);
    for (const z of [-.45,.45]) this.box([.86,.28,.04],[bx,.46,z],blush);
    const tissue = this.box([.84,.016,.84],[bx,.33,0],inside);tissue.rotation.y=.035;
    this.lid=new THREE.Group();this.lid.position.set(bx,.625,-.47);this.group.add(this.lid);
    this.box([.94,.035,.94],[0,.01,.47],blush,this.lid);
    this.box([.075,.006,.94],[0,.032,.47],ribbon,this.lid);
    this.box([.94,.007,.075],[0,.033,.47],ribbon,this.lid);
    for (const x of [-.09,.09]) {
      const bow=new THREE.Mesh(new THREE.TorusGeometry(.095,.014,7,20),ribbon);
      bow.rotation.x=Math.PI/2;bow.scale.set(1.25,.65,1);bow.position.set(x,.055,.47);this.lid.add(bow);
    }
    this.lid.rotation.x=OPEN_ANGLE;
    this.boxLabel=this.buildLabel('PEDIDO', [bx,.49,.476], .68,.16);
    const pickMaterial=new THREE.MeshBasicMaterial({colorWrite:false,depthWrite:false,transparent:true,opacity:0});
    this.pick=new THREE.Mesh(new THREE.BoxGeometry(this.compact?1:2,1.7,1),pickMaterial);
    this.pick.position.set(this.compact?0:.5,.85,0);this.pick.userData.station='DELIVERY';this.group.add(this.pick);
  }

  buildLabel(text, position, width, height) {
    const canvas=document.createElement('canvas');canvas.width=768;canvas.height=160;
    const texture=new THREE.CanvasTexture(canvas);texture.colorSpace=THREE.SRGBColorSpace;
    const material=new THREE.MeshStandardMaterial({map:texture,roughness:.9});
    const label=this.box([width,height,.012],position,material);
    const ctx=canvas.getContext('2d');
    label.userData.draw=text=>{
      ctx.fillStyle='#fff5f8';ctx.fillRect(0,0,768,160);ctx.strokeStyle='#c893ae';ctx.lineWidth=5;ctx.strokeRect(3,3,762,154);
      ctx.fillStyle='#654455';ctx.textAlign='center';ctx.textBaseline='middle';ctx.font='600 48px Arial';ctx.fillText(text,384,82);texture.needsUpdate=true;
    };
    label.userData.draw(text);return label;
  }

  update(state, enabled, instant) {
    this.group.visible=enabled;if(!enabled)return;
    const order=state.order;
    const changed=this.orderId!==order.id;
    if(changed){this.orderId=order.id;this.items.clear();this.epoch=this.lastWall=performance.now();this.elapsed=0;this.lidAngle=OPEN_ANGLE;}
    this.requested=order.lines.reduce((n,l)=>n+l.quantity,0);
    this.delivered=order.lines.reduce((n,l)=>n+l.delivered,0);
    this.complete=order.state==='DELIVERED';
    const pose=this.view.world(state.x,state.y).sub(this.group.position);
    const rotation=new THREE.Quaternion().setFromAxisAngle(new THREE.Vector3(0,1,0),-state.theta*Math.PI/2);
    let incoming=0;
    for(const line of order.lines)for(let i=0;i<line.delivered;i++){
      const key=`${line.sku}:${i}`;if(this.items.has(key))continue;
      const start=new THREE.Vector3((incoming%3-1)*.17,.70,(Math.floor(incoming/3)-.5)*.19).applyQuaternion(rotation).add(pose);
      this.items.set(key,{sku:line.sku,index:i,slot:this.items.size,start,at:changed||instant?this.elapsed-DURATION-1:this.elapsed+incoming*.40});incoming++;
    }
    if(changed||instant)this.lidAngle=this.complete?0:OPEN_ANGLE;
    this.notify();
  }

  positionFor(sku,index) {
    const item=this.items.get(`${sku}:${index}`);if(!item)return new THREE.Vector3(this.boxX,.47,0);
    const columns=Math.max(1,Math.ceil(Math.sqrt(this.requested)));
    const packed=new THREE.Vector3(this.boxX+(item.slot%columns-(columns-1)/2)*.215,
      .47,(Math.floor(item.slot/columns)-(Math.ceil(this.requested/columns)-1)/2)*.215);
    const age=this.elapsed-item.at;
    if(age>=DURATION)return packed;
    if(age<0)return item.start.clone();
    const entry=new THREE.Vector3(this.compact?this.boxX:-.35,.75,0);
    if(age<.65)return item.start.clone().lerp(entry,age/.65);
    if(this.compact){
      const p=entry.clone().lerp(packed,clamp((age-.65)/(DURATION-.65),0,1));
      p.y+=Math.sin(clamp((age-.65)/(DURATION-.65),0,1)*Math.PI)*.16;return p;
    }
    if(age<2.6)return new THREE.Vector3(THREE.MathUtils.lerp(-.35,.79,(age-.65)/1.95),.75,0);
    const t=clamp((age-2.6)/(DURATION-2.6),0,1);
    // La cinta termina sobre la boca de la caja; caída corta sobre el papel interior.
    return new THREE.Vector3(.79,.75,0).lerp(packed,t);
  }

  status() {
    let packed=0;for(const item of this.items.values())if(this.elapsed-item.at>=DURATION)packed++;
    const moving=packed<this.delivered;
    return {orderId:this.orderId,phase:moving?'conveying':this.complete&&packed===this.requested?(Math.abs(this.lidAngle)<.02?'ready':'closing'):packed?'partial':'waiting',packed,delivered:this.delivered,requested:this.requested};
  }

  notify() {
    const status=this.status(), key=JSON.stringify(status);
    if(key!==this.lastStatus){this.lastStatus=key;this.boxLabel.userData.draw(`${this.orderId?.slice(0,8).toUpperCase()||'PEDIDO'} · ${status.phase==='ready'?'LISTO':'♡'}`);this.view.onPackingChange?.(status);}
  }

  animate(dt) {
    const now=performance.now(), wallDt=Math.min(1,Math.max(0,(now-this.lastWall)/1000));
    this.lastWall=now;this.elapsed=(now-this.epoch)/1000;
    const status=this.status(), closed=this.complete&&status.packed===this.requested;
    const target=closed?0:OPEN_ANGLE;
    this.lidAngle=THREE.MathUtils.lerp(this.lidAngle,target,1-Math.exp(-wallDt*5));
    this.lid.rotation.x=this.lidAngle;
    this.isAnimating=status.phase==='conveying'||Math.abs(this.lidAngle-target)>.001;
    if(status.phase==='conveying'&&this.beltTexture)this.beltTexture.offset.x=-this.elapsed*.22;
    this.notify();
  }
}
