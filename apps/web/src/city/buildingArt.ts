import type {Building} from '../data/types';
import {project,type Point,type Bounds} from './cityGeometry';
import {face,oval,stroke,material,block,arcade,foliage} from './modelArt';
export const landmarkKinds=['coit','pyramid','salesforce','ferry'];
const footprint=(b:Building):Point[]=>[project(b.x,b.y),project(b.x+b.w,b.y),project(b.x+b.w,b.y+b.d),project(b.x,b.y+b.d)];
export function ferryWing(b:Building):Building{return {...b,x:b.x-1.6,y:b.y+b.d-.8,w:1.6,d:.8,h:b.h-3,kind:'normal'};}
function hull(points:Point[]):Point[]{const ps=[...points].sort((a,b)=>a[0]-b[0]||a[1]-b[1]),cross=(a:Point,b:Point,p:Point)=>(b[0]-a[0])*(p[1]-a[1])-(b[1]-a[1])*(p[0]-a[0]),l:Point[]=[],u:Point[]=[];for(const p of ps){while(l.length>1&&cross(l.at(-2)!,l.at(-1)!,p)<=0)l.pop();l.push(p);}for(const p of [...ps].reverse()){while(u.length>1&&cross(u.at(-2)!,u.at(-1)!,p)<=0)u.pop();u.push(p);}return [...l.slice(0,-1),...u.slice(0,-1)];}
export function buildingOutline(b:Building):Point[]{
 const f=footprint(b),h=b.h+(b.elevation??0),tops=f.map(p=>[p[0],p[1]-h] as Point);
 if(b.kind==='pyramid')return hull([...f,project(b.x+b.w/2,b.y+b.d/2,h+60)]);
 if(b.kind==='coit'){const p=project(b.x+b.w/2,b.y+b.d/2);return [[p[0]-13,p[1]+5],[p[0]+13,p[1]+5],[p[0]+10,p[1]-h-10],[p[0]-10,p[1]-h-10]];}
 if(b.kind==='salesforce'){const p=project(b.x+b.w/2,b.y+b.d/2);return [[p[0]-23,p[1]+8],[p[0]+23,p[1]+8],[p[0]+23,p[1]-h+10],[p[0]+12,p[1]-h-6],[p[0]-12,p[1]-h-6],[p[0]-23,p[1]-h+10]];}
 if(b.kind==='ferry'){const t=project(b.x+b.w*.5,b.y+b.d*.72),w=ferryWing(b),wing=footprint(w);return hull([...f,...tops,...wing,...wing.map(p=>[p[0],p[1]-w.h] as Point),[t[0]-15,t[1]-146],[t[0]+15,t[1]-146]]);}
 return hull([...f,...tops,...(b.kind==='house'?[project(b.x+b.w*.5,b.y,h+12),project(b.x+b.w*.5,b.y+b.d,h+12)]:[])]);
}
export function buildingBounds(b:Building):Bounds{const p=buildingOutline(b),xs=p.map(p=>p[0]),ys=p.map(p=>p[1]);return {x:Math.min(...xs)-3,y:Math.min(...ys)-3,width:Math.max(...xs)-Math.min(...xs)+6,height:Math.max(...ys)-Math.min(...ys)+6};}
function body(c:CanvasRenderingContext2D,b:Building,roofColor=b.color){
 const e=b.elevation??0,{x,y,w,d,h,color}=b,p=project(x,y,e),a=project(x+w,y,e),z=project(x+w,y+d,e),v=project(x,y+d,e),up=(p:Point):Point=>[p[0],p[1]-h];
 if(e>1)face(c,footprint(b),'#a1b491');
 face(c,[v,z,up(z),up(v)],material(c,v[0],v[1]-h,z[0]-v[0],h,color,.97,.79));face(c,[a,z,up(z),up(a)],material(c,a[0],a[1]-h,z[0]-a[0],h,color,.79,.62));
 face(c,[up(p),up(a),up(z),up(v)],material(c,p[0],p[1]-h,z[0]-p[0]+20,20,roofColor,1.09,.98),'rgba(255,246,219,.4)');
 // A quiet contact line and sunlit vertical corner, rather than a thick outline.
 stroke(c,[v,z,a],'rgba(50,62,45,.13)',.65);stroke(c,[up(z),z],'rgba(251,236,202,.16)',.65);
 return {p,a,z,v,roof:[up(p),up(a),up(z),up(v)]};
}
export function prism(c:CanvasRenderingContext2D,b:Building,lod:0|1|2=0){
 if(b.kind==='coit'){drawCoit(c,b);return;}if(b.kind==='salesforce'){drawSalesforce(c,b,lod);return;}if(b.kind==='pyramid'){drawPyramid(c,b);return;}if(b.kind==='ferry'){drawFerry(c,b,lod);return;}
 const {p,a,z,v,roof}=body(c,b);const e=b.elevation??0;
 if(b.kind==='house'){
  // A complete pitched roof, including both planes and the triangular gable.
  const r0=project(b.x+b.w*.5,b.y,b.h+e+11),r1=project(b.x+b.w*.5,b.y+b.d,b.h+e+11),tile=['#b28d7e','#aebbb5','#c9b68f','#bfa6a0','#b9b9b0'][b.kit??0];
  face(c,[roof[0],roof[3],r1,r0],material(c,v[0],v[1]-b.h-10,25,25,tile,1.12,.92));face(c,[r0,r1,roof[2],roof[1]],material(c,p[0],p[1]-b.h-10,35,30,tile,.92,.73));face(c,[roof[3],roof[2],r1],material(c,v[0],v[1]-b.h,30,16,b.color,1.02,.87));stroke(c,[r0,r1],'#e6d7be',.65);
  if(lod>0){const door=project(b.x+b.w*.58,b.y+b.d,e);face(c,[[door[0]-2,door[1]-9],[door[0]+2,door[1]-7],[door[0]+2,door[1]],[door[0]-2,door[1]-2]],'#7c8a7c');if((b.kit??0)%2===0){const bay=project(b.x+b.w*.2,b.y+b.d,e);block(c,bay[0],bay[1]-5,3.5,2,7,'#d4ddcf');}}
 }
 if(b.kind==='shop'){
  const front=project(b.x+b.w*.5,b.y+b.d,e);face(c,[[front[0]-6,front[1]-13],[front[0]+6,front[1]-7],[front[0]+6,front[1]],[front[0]-6,front[1]-6]],'#61776c');
  const start=project(b.x-.04,b.y+b.d,e+14),end=project(b.x+b.w+.04,b.y+b.d,e+14),tip=project(b.x+b.w+.04,b.y+b.d+.25,e+9),left=project(b.x-.04,b.y+b.d+.25,e+9);face(c,[start,end,tip,left],material(c,start[0],start[1],30,13,b.awning??'#cfa78b',1.12,.85));stroke(c,[left,tip],'#ebd8b7',1.6);
  if(lod>0)for(let i=0;i<6;i++){const t=i/6;stroke(c,[[start[0]+(end[0]-start[0])*t,start[1]+(end[1]-start[1])*t],[left[0]+(tip[0]-left[0])*t,left[1]+(tip[1]-left[1])*t]],'#eee0c6',1.3);}
 }
 if(b.kind==='bank'){const p=project(b.x+b.w/2,b.y+b.d,e);stroke(c,[[p[0]-9,p[1]-b.h+5],[p[0]+8,p[1]-b.h+13]],'#ede7d8',2);if(lod>0)for(let i=-1;i<=1;i++){c.fillStyle='#e7dfc6';c.fillRect(p[0]+i*5-1,p[1]-21,2,17);}}
}
function drawPyramid(c:CanvasRenderingContext2D,b:Building){
 const [p,a,z,v]=footprint(b),peak=project(b.x+b.w/2,b.y+b.d/2,b.h+60),shoulder=65;
 const va:Point=[v[0]+5,v[1]-shoulder],za:Point=[z[0]-1,z[1]-shoulder],aa:Point=[a[0]-5,a[1]-shoulder];
 face(c,[v,z,za,peak,va],material(c,v[0],peak[1],45,b.h+60,'#f2eddb',1.08,.88));face(c,[z,a,aa,peak,za],material(c,a[0],peak[1],-35,b.h+60,'#cdd3c9',1,.81));stroke(c,[peak,za,z],'#f6f0db',.7);
 face(c,[[va[0]-5,va[1]+8],va,[va[0],va[1]-13]],'#ebe6d4');face(c,[aa,[aa[0]+6,aa[1]+7],[aa[0],aa[1]-13]],'#c2cabc');
}
function drawSalesforce(c:CanvasRenderingContext2D,b:Building,lod:number){
 const p=project(b.x+b.w/2,b.y+b.d/2),x=p[0],y=p[1],h=b.h,r=22;
 oval(c,x+4,y+3,25,11,'rgba(38,64,63,.15)');const g=c.createLinearGradient(x-r,0,x+r,0);g.addColorStop(0,'#a9c1c5');g.addColorStop(.25,'#c9dedb');g.addColorStop(.63,'#8babb4');g.addColorStop(1,'#658895');
 c.beginPath();c.moveTo(x-r,y);c.lineTo(x-r,y-h+15);c.bezierCurveTo(x-r,y-h-7,x+r,y-h-7,x+r,y-h+15);c.lineTo(x+r,y);c.bezierCurveTo(x+r,y+13,x-r,y+13,x-r,y);c.fillStyle=g;c.fill();
 c.save();c.clip();for(let i=-17;i<22;i+=4)stroke(c,[[x+i,y-h+12],[x+i,y+7]],'rgba(224,236,224,.17)',.5);if(lod>0)for(let yy=y-h+20;yy<y;yy+=5)stroke(c,[[x-r,yy],[x+r,yy]],'rgba(228,239,229,.13)',.5);c.restore();
 c.beginPath();c.ellipse(x,y-h+12,21,14,0,Math.PI,Math.PI*2);c.strokeStyle='#d9e7dd';c.lineWidth=1;c.stroke();
}
function drawCoit(c:CanvasRenderingContext2D,b:Building){
 const p=project(b.x+b.w/2,b.y+b.d/2),x=p[0],y=p[1],h=b.h;
 oval(c,x,y+5,40,18,material(c,x-35,y-15,65,40,'#89a26d',1.14,.8));for(let i=0;i<11;i++){const a=i/11*Math.PI*2;foliage(c,x+Math.cos(a)*31,y+Math.sin(a)*12+2,4.5+i%3,'#4c733f');}
 oval(c,x,y,14,7,'#c6c8b3');oval(c,x,y-3,13,6,'#ece4ca');const g=c.createLinearGradient(x-8,0,x+8,0);g.addColorStop(0,'#f5edd7');g.addColorStop(.45,'#e6dcc5');g.addColorStop(1,'#a9b4a6');c.fillStyle=g;c.fillRect(x-7.5,y-h,15,h-4);oval(c,x,y-h,8,4,'#ede7d4');
 for(let i=-2;i<=2;i++){stroke(c,[[x+i*2.6,y-h+6],[x+i*2.6,y-11]],'rgba(122,133,118,.21)',.6);c.fillStyle='#6e8379';c.fillRect(x+i*2.7-.6,y-h+3,1.2,8);}
 oval(c,x,y-h-2,9,4,'#f5ecd6');stroke(c,[[x-9,y-9],[x+9,y-9]],'#d8d4bd',2);
}
function drawFerry(c:CanvasRenderingContext2D,b:Building,lod:number){
 const wing=ferryWing(b);for(const part of [b,wing]){const s=body(c,{...part,color:'#ede3c9'},'#6f7f7c');arcade(c,s.a,s.z,part.h,Math.round(part.d*5),lod,'#eee3c9','#667b74');arcade(c,s.v,s.z,part.h,Math.round(part.w*4),lod,'#eee3c9','#73847a');stroke(c,[s.roof[1],s.roof[2],s.roof[3]],'#f5e8ce',2);}
 const p=project(b.x+b.w*.5,b.y+b.d*.72),x=p[0],y=p[1];
 block(c,x,y,14,14,107,'#e7dfc8');
 for(const h of [42,68,91,107]){block(c,x,y-h,16,16,3,'#efe5cc');}
 for(const side of [-1,1]){c.save();c.transform(side,.5,0,1,x,y-81);oval(c,7,0,4.5,5.3,'#c6b26d');oval(c,7,0,3.6,4.4,'#eee0a8');const cx=7;stroke(c,[[cx,-3],[cx,0],[cx+2,1]],'#5b6d61',.7);c.restore();}
 for(const side of [-1,1])for(let i=0;i<3;i++){const xx=x+side*(3+i*4);stroke(c,[[xx,y-103+Math.abs(xx-x)*.5],[xx,y-94+Math.abs(xx-x)*.5]],'#71837a',1.5);}
 block(c,x,y-110,12,12,12,'#e9e1cc');face(c,[[x-12,y-108],[x,y-136],[x+12,y-108],[x,y-102]],'#f4ead4');stroke(c,[[x,y-136],[x,y-144]],'#d3d6c3',1);oval(c,x,y-144,1.4,1.4,'#e8dfc6');
}
