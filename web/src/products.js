import * as THREE from 'three';
import products from '../../src/warehouse_rush/configs/products.json' with { type: 'json' };
export const PRODUCTS = products;
const materials = new Map();
const geometries = new Map();
function material(color, metalness = 0) {
  const key = `${color}/${metalness}`;
  if (!materials.has(key)) materials.set(key, new THREE.MeshStandardMaterial({ color, metalness, roughness: metalness ? .28 : .48 }));
  return materials.get(key);
}
function geometry(key, make) { if (!geometries.has(key)) geometries.set(key, make());return geometries.get(key); }
// Modelos originales de baja complejidad. Coordenadas locales: base y=0, altura ~1.
// Geometrías y materiales compartidos entre las instancias de la bodega.
export function createProduct(product) {
  const group = new THREE.Group();group.name = product.sku;group.userData = { sku: product.sku, model: product.model };
  const color = product.color, white = '#fff7fb', gold = '#caa575', dark = '#302734';
  function part(kind, size, pos, tint = color, metal = 0, rotation = 0) {
    let geo;
    if (kind === 'box') geo = geometry('box', () => new THREE.BoxGeometry(1, 1, 1));
    else if (kind === 'sphere') geo = geometry('sphere', () => new THREE.SphereGeometry(.5, 16, 12));
    else if (kind === 'torus') geo = geometry('torus', () => new THREE.TorusGeometry(.4, .045, 6, 24));
    else geo = geometry('cylinder', () => new THREE.CylinderGeometry(.5, .5, 1, 16));
    const mesh = new THREE.Mesh(geo, material(tint, metal));mesh.scale.set(...size);mesh.position.set(...pos);mesh.rotation.z = rotation;
    mesh.castShadow = true;mesh.receiveShadow = true;group.add(mesh);return mesh;
  }
  const box = (s,p,c=color,m=0) => part('box',s,p,c,m);
  const cylinder = (s,p,c=color,m=0) => part('cylinder',s,p,c,m);
  const ball = (s,p,c=color) => part('sphere',s,p,c);
  function label(y=.45) { box([.2,.12,.012],[0,y,.151],white); }
  function pencil(x=0,c=color) { cylinder([.07,.84,.07],[x,.42,0],c);const tip = new THREE.Mesh(geometry('tip',()=>new THREE.ConeGeometry(.035,.13,12)),material('#c4947c'));tip.position.set(x,.905,0);group.add(tip);cylinder([.075,.13,.075],[x,.065,0],gold,.65); }
  function bottle(cap=dark) { cylinder([.32,.65,.32],[0,.325,0]);cylinder([.27,.27,.27],[0,.785,0],cap,.5);label(); }
  function compact(bear=false) {
    cylinder([.76,.14,.76],[0,.08,0],color,.3);cylinder([.62,.025,.62],[0,.16,0],'#ee9bab');
    const lid=cylinder([.76,.07,.76],[0,.47,-.31],color,.35);lid.rotation.x=Math.PI/2;
    const mirror=cylinder([.61,.012,.61],[0,.47,-.267],'#dee3ef',.85);mirror.rotation.x=Math.PI/2;
    if(bear){ball([.18,.18,.08],[-.21,.79,-.3]);ball([.18,.18,.08],[.21,.79,-.3]);ball([.25,.2,.08],[0,.44,-.22],'#f7bfd2');}
  }
  switch(product.model) {
    case 'pencil': pencil();break;
    case 'pencil-kit': for(let i=0;i<6;i++) pencil((i-2.5)*.12);break;
    case 'lip-kit': for(let i=0;i<8;i++){const x=(i%4-1.5)*.18,z=Math.floor(i/4)*.2; cylinder([.12,.49,.12],[x,.245,z],['#a63e65','#c47777','#ed9cb6','#b76b6a'][i%4]);cylinder([.125,.31,.125],[x,.645,z],'#f5b8d1');}break;
    case 'mascara-kit': bottle(gold);cylinder([.13,.78,.13],[.3,.39,0],gold,.6);break;
    case 'tube': cylinder([.24,.27,.24],[0,.135,0],white);box([.27,.53,.15],[0,.535,0]);box([.29,.045,.17],[0,.82,0]);label(.52);break;
    case 'gloss': box([.28,.46,.28],[0,.23,0]);box([.29,.4,.29],[0,.66,0],'#d9d2db',.85);label(.24);break;
    case 'character-gloss': bottle(color);ball([.37,.3,.32],[0,.91,0]);ball([.035,.05,.035],[-.08,.48,.16],dark);ball([.035,.05,.035],[.08,.48,.16],dark);break;
    case 'bottle': bottle();break;
    case 'spray': bottle('#f7c4df');cylinder([.1,.1,.1],[0,.96,0],gold,.6);break;
    case 'jar': cylinder([.7,.32,.7],[0,.16,0]);cylinder([.73,.1,.73],[0,.37,0],white);box([.28,.13,.015],[0,.18,.352],white);break;
    case 'compact': compact();break;
    case 'bear-compact': compact(true);break;
    case 'palette': box([1.05,.10,.56],[0,.06,0]);for(let i=0;i<12;i++)box([.14,.025,.19],[(i%6-2.5)*.166,.125,(Math.floor(i/6)-.5)*.25],['#efc1b2','#ed8f9b','#c07670','#9c6264','#d4ac89','#e7c083'][i%6]);box([1.05,.48,.04],[0,.37,-.28]);box([.93,.35,.012],[0,.38,-.253],'#e9d5de',.6);break;
    case 'sachet': box([.65,.9,.045],[0,.45,0]);box([.65,.035,.06],[0,.88,0],white);box([.42,.42,.012],[0,.43,.03],white);break;
    case 'brush': cylinder([.11,.49,.11],[0,.245,0],dark);cylinder([.19,.23,.19],[0,.6,0],gold,.8);ball([.46,.48,.40],[0,.88,0],dark);break;
    case 'sponge': {const points=[new THREE.Vector2(0,0),new THREE.Vector2(.24,.1),new THREE.Vector2(.28,.3),new THREE.Vector2(.23,.55),new THREE.Vector2(.08,.85),new THREE.Vector2(0,.95)];const mesh=new THREE.Mesh(geometry('sponge',()=>new THREE.LatheGeometry(points,20)),material(color));mesh.castShadow=true;group.add(mesh);break;}
    case 'wallet': box([.58,.78,.10],[0,.39,0]);for(let i=0;i<3;i++)box([.43,.012,.012],[0,.52+i*.08,.06],dark);ball([.045,.045,.025],[.18,.2,.065],gold);break;
    case 'bag': box([.85,.62,.35],[0,.33,0]);const handle=part('torus',[.6,.45,.7],[0,.68,0],color);handle.rotation.y=0;box([.8,.025,.365],[0,.6,0],gold,.6);break;
    case 'pins': for(let i=0;i<5;i++){box([.075,.75,.06],[(i-2)*.15,.4,0],i%2?dark:color);box([.025,.58,.075],[(i-2)*.15+.018,.42,.025],gold,.6);}break;
    case 'comb-kit': for(const x of [-.23,.23]){box([.10,.4,.08],[x,.2,0]);box([.12,.5,.08],[x-.13,.62,0]);for(let i=0;i<9;i++)box([.3,.025,.08],[x,.4+i*.055,0]);}break;
    case 'butterfly': for(const side of [-1,1])for(const y of [.3,.65]){const wing=ball([.48,.4,.13],[side*.22,y,0]);wing.rotation.z=side*(y>.4?-.4:.4);}cylinder([.09,.68,.09],[0,.46,0],gold,.7);break;
    case 'necklace': {box([.72,.94,.04],[0,.47,-.05],'#f7df8c');const chain=part('torus',[.66,.83,.7],[0,.53,0],gold,.8);chain.scale.y=.85;ball([.25,.21,.12],[0,.21,.04]);ball([.17,.3,.08],[-.17,.25,.04]);ball([.17,.3,.08],[.17,.25,.04]);break;}
    case 'brow-kit': box([.72,.65,.07],[0,.35,-.05],white);for(const x of [-.24,0,.24]){box([.045,.52,.045],[x,.38,.015],gold,.7);ball([.11,.14,.035],[x,.16,.02]);}break;
    default: throw new Error(`Modelo desconocido: ${product.model}`);
  }
  return group;
}
