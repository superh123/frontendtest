import type {ScenePoint,Tree} from '../data/types';
import type {Point} from './cityGeometry';
import {face,oval,stroke,material,block,arch,foliage,castShadow} from './modelArt';
type LOD=0|1|2;
type LakePainter=(c:CanvasRenderingContext2D,x:number,y:number,rx:number,ry:number,r:number,l:LOD)=>void;
function column(c:CanvasRenderingContext2D,x:number,y:number,h:number,w:number,lod:LOD){
 // Four stepped pieces, a shaded pink shaft, fluting, and a carved capital.
 block(c,x,y,w*.8,w*.8,3,'#dfcfb0');block(c,x,y-3,w*.64,w*.64,4,'#edddbf');
 const g=c.createLinearGradient(x-w*.5,0,x+w*.5,0);g.addColorStop(0,'#e2b59a');g.addColorStop(.4,'#d29a82');g.addColorStop(1,'#a96e5b');c.fillStyle=g;c.fillRect(x-w*.48,y-h,w*.96,h-6);
 if(lod>0)for(let i=-1;i<=1;i++)stroke(c,[[x+i*w*.23,y-h+4],[x+i*w*.23,y-8]],'rgba(112,67,51,.23)',.45);
 block(c,x,y-h+2,w*.72,w*.72,4,'#cdb191');block(c,x,y-h-2,w*.9,w*.9,3,'#ead5b4');
 if(lod>0)for(const side of [-1,1]){c.beginPath();c.arc(x+side*w*.58,y-h+1,w*.21,0,Math.PI*1.7);c.strokeStyle='#ad9072';c.lineWidth=.65;c.stroke();}
}
function ring(c:CanvasRenderingContext2D,x:number,y:number,rx:number,ry:number,z:number,h:number,color:string){
 const p=Array.from({length:8},(_,i)=>{const a=Math.PI/8+i*Math.PI/4;return [x+Math.cos(a)*rx,y+Math.sin(a)*ry] as Point;});
 // Front-facing facets reveal the depth of an octagonal entablature.
 for(let i=0;i<8;i++){const a=p[i],b=p[(i+1)%8];if((a[1]+b[1])/2<y)continue;face(c,[[a[0],a[1]-z],[b[0],b[1]-z],[b[0],b[1]-z-h],[a[0],a[1]-z-h]],material(c,a[0],a[1]-z-h,b[0]-a[0],h,color,a[0]<x?1.05:.88,a[0]<x?.91:.77));}
 face(c,p.map(p=>[p[0],p[1]-z-h]),material(c,x-rx,y-z-h-ry,rx*2,ry*2,color,1.13,1),'rgba(253,241,214,.6)');return p;
}
export function renderPalace(c:CanvasRenderingContext2D,lod:LOD,paths:ScenePoint[][],trees:Tree[],treePainter:((c:CanvasRenderingContext2D,t:Tree,l:LOD)=>void)|undefined,lake:LakePainter){
 const x=340,y=373,rx=45,ry=24,h=65;
 oval(c,340,399,154,91,material(c,200,320,280,180,'#a9bf89',1.04,.9));for(const p of paths)stroke(c,p,'#e0d6ba',7);lake(c,340,424,101,42,0,lod);
 // The lagoon wraps around the rotunda apron; shrubs follow its irregular perimeter.
 for(const t of trees.filter(t=>t.y<365))treePainter?.(c,t,lod);
 const wing=(start:number,end:number)=>{
  const feet=Array.from({length:9},(_,i)=>{const a=start+(end-start)*i/8;return [x+Math.cos(a)*110,402+Math.sin(a)*41] as Point;});
  stroke(c,feet,'#d9c9aa',12);for(const p of feet)column(c,p[0],p[1],37,6.4,lod);
  for(let i=1;i<feet.length;i++){const a=feet[i-1],b=feet[i],top=44;face(c,[[a[0],a[1]-top],[b[0],b[1]-top],[b[0],b[1]-top+7],[a[0],a[1]-top+7]],'#c3a687');face(c,[[a[0],a[1]-top-2],[b[0],b[1]-top-2],[b[0]+2,b[1]-top],[a[0]+2,a[1]-top]],'#f4e4c8');stroke(c,[[a[0],a[1]-top-2],[b[0],b[1]-top-2]],'#efe0c3',2);}
 };
 wing(Math.PI*.91,Math.PI*1.40);wing(Math.PI*1.60,Math.PI*2.09);
 const base=Array.from({length:8},(_,i)=>{const a=i*Math.PI/4;return [x+Math.cos(a)*49,y+Math.sin(a)*26] as Point;});castShadow(c,base,115,.21);
 ring(c,x,y,53,28,0,3,'#d2c1a1');ring(c,x,y,50,26,3,4,'#e5d3b3');ring(c,x,y,46,24,7,3,'#eedfc1');
 const vertices=Array.from({length:8},(_,i)=>{const a=Math.PI/8+i*Math.PI/4;return [x+Math.cos(a)*rx,y+Math.sin(a)*ry] as Point;});
 // Back columns establish a dark, open interior silhouette. Front facets carry true arches.
 for(const p of vertices.filter(p=>p[1]<y))column(c,p[0],p[1]-7,h,6.5,lod);
 for(let i=0;i<8;i++){
  const a=vertices[i],b=vertices[(i+1)%8];if((a[1]+b[1])/2<y)continue;
  const height=h-5,ground=10,top=[a[0],a[1]-height-ground] as Point;
  face(c,[[a[0],a[1]-ground],[b[0],b[1]-ground],[b[0],b[1]-ground-height],top],material(c,a[0],a[1]-height,b[0]-a[0],height,'#d6b999',a[0]<x?1.08:.89,a[0]<x?.98:.75));
  const width=Math.hypot(b[0]-a[0],b[1]-a[1]);c.save();c.transform((b[0]-a[0])/width,(b[1]-a[1])/width,0,1,a[0],a[1]-ground-height);
  arch(c,width/2,height,width*.60,height-8,'#efe1c5','#6d7063',2.6);
  // Moulded arch voussoirs and a projecting keystone are legible at district scale.
  if(lod>0){const ar=width*.30,cy=8+ar;for(let j=0;j<7;j++){const t=Math.PI+j/6*Math.PI;stroke(c,[[width/2+Math.cos(t)*(ar+1),cy+Math.sin(t)*(ar+1)],[width/2+Math.cos(t)*(ar+3.8),cy+Math.sin(t)*(ar+3.8)]],'#b49b7c',.6);}face(c,[[width/2-2,5],[width/2+2,5],[width/2+1.5,11],[width/2-1.5,11]],'#f0dfbf');}
  c.restore();
 }
 for(const p of vertices.filter(p=>p[1]>=y))column(c,p[0],p[1]-7,h,7.5,lod);
 // Layered entablature, framed frieze panels and projecting cornices.
 ring(c,x,y,49,26,72,4,'#cbb18e');ring(c,x,y,47,25,76,11,'#e3ccaa');
 for(let i=0;i<8;i++){const a=vertices[i],b=vertices[(i+1)%8];if((a[1]+b[1])/2<y)continue;const u:Point=[a[0]*.88+b[0]*.12,(a[1]*.88+b[1]*.12)-80],v:Point=[a[0]*.12+b[0]*.88,(a[1]*.12+b[1]*.88)-80];stroke(c,[u,v],'#bda181',.75);stroke(c,[[u[0],u[1]-5],[v[0],v[1]-5]],'#f6e6c8',.9);if(lod>0){const mx=(u[0]+v[0])/2,my=(u[1]+v[1])/2-2;face(c,[[mx-2,my],[mx,my-2],[mx+2,my],[mx,my+2]],'#c1a180');}}
 ring(c,x,y,51,27,87,3,'#f2e2c3');ring(c,x,y,48,25,90,3,'#c8b18e');
 // The dome is a lit hemisphere seated inside a raised, layered circular curb.
 const dy=y-96;oval(c,x,dy+5,43,21,'#ad9c80');oval(c,x,dy+2,45,22,'#e8d9bb');
 const dome=c.createRadialGradient(x-17,dy-25,3,x+11,dy,64);dome.addColorStop(0,'#fff6e2');dome.addColorStop(.5,'#eee3cb');dome.addColorStop(1,'#b6a789');
 c.beginPath();c.moveTo(x-42,dy);c.bezierCurveTo(x-43,dy-55,x+39,dy-55,x+42,dy);c.bezierCurveTo(x+33,dy+24,x-33,dy+24,x-42,dy);c.fillStyle=dome;c.fill();
 c.beginPath();c.ellipse(x,dy,43,21,0,0,Math.PI);c.strokeStyle='#f7e9ce';c.lineWidth=2;c.stroke();c.beginPath();c.ellipse(x,dy+3,44,21,0,0,Math.PI);c.strokeStyle='#b9a98d';c.lineWidth=1;c.stroke();
 // Discrete corner finials sit on the cornice, rather than a row of drum dots.
 for(const p of vertices.filter(p=>p[1]>=y)){const fx=x+(p[0]-x)*1.06,fy=p[1]-94;block(c,fx,fy,3,3,4,'#eadabd');if(lod>0)stroke(c,[[fx,fy-4],[fx-1,fy-9],[fx+1,fy-10]],'#f1e1c4',1.6);}
 for(const t of trees.filter(t=>t.y>=365))treePainter?.(c,t,lod);
}
export function renderAlcatraz(c:CanvasRenderingContext2D,lod:LOD){
 c.save();c.translate(-50,25);
 const cx=1120,cy=282;const shore=Array.from({length:36},(_,i)=>{const a=i/36*Math.PI*2,r=1+.055*Math.sin(i*2.4);return [cx+Math.cos(a)*74*r,cy+Math.sin(a)*28*r] as Point;});
 oval(c,cx+7,cy+7,80,29,'rgba(33,73,83,.16)');face(c,shore.map(p=>[p[0],p[1]+5]),'#8c9281');face(c,shore,'#d5d0b5');face(c,shore.map(p=>[cx+(p[0]-cx)*.92,cy+(p[1]-cy)*.81-2]),'#879c6c');
 // Broken rock facets form a low shore, with a pale walking terrace above.
 for(let i=1;i<shore.length;i+=3){const p=shore[i];face(c,[[p[0]-5,p[1]],[p[0],p[1]-5],[p[0]+6,p[1]+2],[p[0]+1,p[1]+5]],i%2?'#b5b59b':'#e0dac0');}
 stroke(c,[[1064,285],[1090,299],[1131,300],[1170,288]],'#e6dec6',3);
 block(c,1110,268,40,19,19,'#d6cbb7');block(c,1089,279,19,11,10,'#d4c8b2');block(c,1145,273,15,14,11,'#c6b8a0');
 if(lod>0)for(let i=0;i<7;i++){c.fillStyle='#7f8c7d';c.fillRect(1096+i*5.5,278+i*2.75,1.2,3);}
 // A cylindrical lighthouse with a lantern cap, unmistakable even in the overview.
 const x=1154,y=287;oval(c,x,y,5,2.5,'#d7d6bd');c.fillStyle=material(c,x-2,y-28,5,28,'#f0e8cd',1.1,.78);c.fillRect(x-2.5,y-27,5,27);oval(c,x,y-28,3.5,2,'#f8eed5');c.fillStyle='#7c9188';c.fillRect(x-2.5,y-32,5,5);oval(c,x,y-33,3.6,1.6,'#ece7d2');
 for(const [x,y,s]of [[1077,278,4],[1152,295,5],[1181,283,4]])foliage(c,x,y,s,'#4b743d');
 c.restore();
}
