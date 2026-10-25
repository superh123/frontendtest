import {renderPalace} from './palaceArt';
﻿import type {CityLayout, ScenePoint, Tree} from '../data/types';
import {intersects,type Bounds,type Point} from './cityGeometry';
type LOD=0|1|2;
const oval=(c:CanvasRenderingContext2D,x:number,y:number,rx:number,ry:number,color:string|CanvasGradient,rotation=0)=>{c.beginPath();c.ellipse(x,y,rx,ry,rotation,0,Math.PI*2);c.fillStyle=color;c.fill();};
const shape=(c:CanvasRenderingContext2D,points:Point[],color:string|CanvasGradient)=>{c.beginPath();points.forEach((p,i)=>i?c.lineTo(...p):c.moveTo(...p));c.closePath();c.fillStyle=color;c.fill();};
const stroke=(c:CanvasRenderingContext2D,points:Point[],color:string,width:number)=>{c.beginPath();points.forEach((p,i)=>i?c.lineTo(...p):c.moveTo(...p));c.strokeStyle=color;c.lineWidth=width;c.lineCap='round';c.lineJoin='round';c.stroke();};

// One shared profile for each cable AND its suspenders: they cannot diverge.
export function bridgeSection(t:number,side=-1){
 const u=Math.max(0,Math.min(1,t));
 const h=u<.24?120*Math.pow(u/.24,1.35):u>.78?120*Math.pow((1-u)/.22,1.35):120-78*4*((u-.24)/.54)*(1-(u-.24)/.54);
 const x=420+575*u+side*6,y=360-145*u+side*4;
 return {deck:[x,y] as Point,cable:[x,y-h] as Point,height:h};
}
export function drawBridge(c:CanvasRenderingContext2D,_lod:LOD){
 const nearA=bridgeSection(0,1).deck,nearB=bridgeSection(1,1).deck,farA=bridgeSection(0,-1).deck,farB=bridgeSection(1,-1).deck;
 c.save();c.shadowColor='rgba(25,63,75,.28)';c.shadowBlur=12;c.shadowOffsetX=7;c.shadowOffsetY=16;shape(c,[farA,farB,nearB,nearA],'#cc6847');c.restore();
 shape(c,[nearA,nearB,[nearB[0],nearB[1]+8],[nearA[0],nearA[1]+8]],'#a7442f');
 shape(c,[farA,farB,nearB,nearA],'#dc7951');stroke(c,[bridgeSection(0,0).deck,bridgeSection(1,0).deck],'#e9b37a',.8);
 // The back cable is drawn first; all suspension wires terminate at its deck edge.
 for(const side of [-1,1]){
  for(let i=1;i<64;i++){const p=bridgeSection(i/64,side);stroke(c,[p.cable,p.deck],side<0?'#cfb697':'#e7cbb0',.72);}
  const cable=Array.from({length:241},(_,i)=>bridgeSection(i/240,side).cable);stroke(c,cable,side<0?'#c39d78':'#efd2ae',1.65);
 }
 for(const t of [.24,.78]){
  const p=bridgeSection(t,0).deck;
  for(const side of [-1,1]){
   const x=p[0]+side*7,y=p[1]+side*4;
   oval(c,x,y+9,8,3,'#e2d6b9');
   shape(c,[[x-3,y+6],[x+3,y+8],[x+3,y-121],[x-3,y-123]],'#c65336');
   shape(c,[[x-3,y-123],[x-5,y-122],[x-5,y+5],[x-3,y+6]],'#f09b6e');
   stroke(c,[[x-3,y-121],[x-3,y+3]],'#ed9368',1.5);
  }
  for(const h of [36,73,109,121]){const a=bridgeSection(t,-1).deck,b=bridgeSection(t,1).deck;shape(c,[[a[0]-1,a[1]-h],[b[0]+2,b[1]-h],[b[0]+2,b[1]-h+5],[a[0]-1,a[1]-h+5]],'#d56c48');stroke(c,[[a[0]-1,a[1]-h],[b[0]+2,b[1]-h]],'#f0a173',1);}
 }
 stroke(c,[farA,farB],'#efb28b',1.3);stroke(c,[[nearA[0],nearA[1]+1],[nearB[0],nearB[1]+1]],'#f1a67a',1.3);
 // A few tiny cars belong to this fixed miniature landmark, rather than extra agents.
 for(const [i,t]of [.08,.18,.36,.46,.62,.87,.94].entries()){const p=bridgeSection(t,i%2?-.4:.4).deck;c.save();c.translate(...p);c.rotate(Math.atan2(-145,575));c.fillStyle=['#efe3bd','#9fb4b0','#bd775f'][i%3];c.fillRect(-3,-1.2,6,2.4);c.fillStyle='#668485';c.fillRect(-.5,-1,1.8,2);c.restore();}
 // Low concrete anchor blocks sit in the headland at both endpoints.
 for(const t of [0,1]){const p=bridgeSection(t,0).deck;shape(c,[[p[0]-8,p[1]-5],[p[0]+6,p[1]-7],[p[0]+13,p[1]+1],[p[0]-2,p[1]+6]],'#d6c9ae');}
}

// Irregular, inset shorelines, bounded by the fixture ellipses so baked walkers stay dry.
export function shoreline(x:number,y:number,rx:number,ry:number,rotation:number):Point[]{return Array.from({length:96},(_,i)=>{const a=i/96*Math.PI*2,r=.90+.065*Math.sin(a*3+.7)+.025*Math.cos(a*5),u=Math.cos(a)*rx*r,v=Math.sin(a)*ry*r;return [x+u*Math.cos(rotation)-v*Math.sin(rotation),y+u*Math.sin(rotation)+v*Math.cos(rotation)] as Point;});}
export function drawLake(c:CanvasRenderingContext2D,x:number,y:number,rx:number,ry:number,rotation:number,lod:LOD){
 const shore=shoreline(x,y,rx,ry,rotation);c.save();c.shadowColor='rgba(54,77,46,.16)';c.shadowBlur=3;c.shadowOffsetX=3;c.shadowOffsetY=2;shape(c,shore,'#9caa8a');c.restore();
 stroke(c,[...shore,shore[0]],'#d7ccb1',7);const water=c.createLinearGradient(x-rx,y-ry,x+rx,y+ry);water.addColorStop(0,'#96b8bb');water.addColorStop(.45,'#7da4ad');water.addColorStop(1,'#5f8797');shape(c,shore,water);stroke(c,shore.slice(4,40),'rgba(230,228,200,.65)',1.1);
 for(let i=0;i<11;i++){const px=x+Math.cos(i*2.1)*rx*.6,py=y+Math.sin(i*1.7)*ry*.52;oval(c,px,py,2.4,1.2,['#99ab6b','#a9b879','#84995d'][i%3],.3);if(i%4===0)oval(c,px-.3,py-.7,.65,.65,'#ead6b7');}
}
export function drawPalace(c:CanvasRenderingContext2D,lod:LOD,paths:ScenePoint[][]=[],trees:Tree[]=[],treePainter?:(c:CanvasRenderingContext2D,t:Tree,l:LOD)=>void){renderPalace(c,lod,paths,trees,treePainter,drawLake);}

export function pierGeometry(x:number,y:number,length:number){
 const n:Point=[1/Math.sqrt(5),2/Math.sqrt(5)],t:Point=[-2/Math.sqrt(5),1/Math.sqrt(5)],half=6;
 const p=(d:number,w:number):Point=>[x+n[0]*d+t[0]*w,y+n[1]*d+t[1]*w];
 return {normal:n,tangent:t,point:p,top:[p(-4,-half),p(length,-half),p(length,half),p(-4,half)]};
}
export function drawWaterfront(c:CanvasRenderingContext2D,layout:CityLayout,lod:LOD,bounds:Bounds){
 c.save();c.beginPath();c.ellipse(720,530,650,320,0,0,Math.PI*2);c.clip();
 // The quay follows the exact coast segment x + 2y = 2498.
 stroke(c,[[1268,615],[976,761]],'#cbc4ac',13);stroke(c,[[1272,617],[980,763]],'#8a9c96',2);
 for(const p of layout.piers){if(!intersects({x:p.x-15,y:p.y-15,width:p.length+40,height:p.length+40},bounds))continue;
  const g=pierGeometry(p.x,p.y,p.length),a=g.point(-4,6),b=g.point(p.length,6);
  c.save();c.shadowColor='rgba(35,72,78,.24)';c.shadowBlur=4;c.shadowOffsetX=3;c.shadowOffsetY=4;shape(c,g.top,'#ded6bd');c.restore();shape(c,[a,b,[b[0],b[1]+4],[a[0],a[1]+4]],'#9aab9f');stroke(c,[g.point(-2,-5),g.point(p.length,-5)],'#f2e6ca',1);
  if(lod>0)for(let d=15;d<p.length-4;d+=12)for(const side of [-1,1]){
   const a=g.point(d,side*5),b=g.point(d,side*14);stroke(c,[a,b],'#d3cdb7',2.5);
   const boat=g.point(d+5,side*10);c.save();c.translate(...boat);c.rotate(Math.atan2(g.normal[1],g.normal[0]));oval(c,0,1,3.8,1.5,'#5c8e9d');shape(c,[[-4,0],[2,-1.3],[4,0],[2,1.3],[-4,1]],'#f8eed8');c.restore();
  }
 }
 for(const b of layout.boats){if(!intersects({x:b.x-10,y:b.y-20,width:25,height:35},bounds))continue;c.save();c.translate(b.x,b.y);c.rotate(b.angle);oval(c,2,5,10,2,'rgba(235,245,236,.18)');shape(c,[[-8,0],[5,-2],[10,1],[3,4],[-6,3]],'#eee7d6');if(b.sail){stroke(c,[[0,-19],[0,3]],'#a5b4b0',.8);shape(c,[[0,-19],[0,0],[9,0]],'#faf1db');}else if(lod>0)shape(c,[[-3,-2],[3,-2],[5,1],[-2,2]],'#9fbbb9');c.restore();}
 c.restore();
}
