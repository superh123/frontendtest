import {prism,buildingBounds,buildingOutline,landmarkKinds} from './buildingArt';
export {prism,buildingBounds,buildingOutline} from './buildingArt';
import {castShadow,foliage,material} from './modelArt';
import {renderAlcatraz} from './palaceArt';
﻿import {drawBridge,drawPalace,drawWaterfront,drawLake} from './landmarkArt';
export {drawPalace} from './landmarkArt';
import type {Building, CityLayout, Landmark, ScenePoint, Tree} from '../data/types';
import {project, COAST, intersects, pointInPolygon, SCENE_WIDTH, SCENE_HEIGHT, type Bounds, type Point} from './cityGeometry';
export {project} from './cityGeometry';
export type DetailLevel=0|1|2;
export function shade(hex:string,n:number){const v=parseInt(hex.slice(1),16);return `rgb(${Math.min(255,(v>>16)*n)},${Math.min(255,((v>>8)&255)*n)},${Math.min(255,(v&255)*n)})`;}
export function polygon(c:CanvasRenderingContext2D,points:number[][],fill:string,stroke?:string){c.beginPath();points.forEach((p,i)=>i?c.lineTo(p[0],p[1]):c.moveTo(p[0],p[1]));c.closePath();c.fillStyle=fill;c.fill();if(stroke){c.strokeStyle=stroke;c.stroke();}}
function ellipse(c:CanvasRenderingContext2D,x:number,y:number,rx:number,ry:number,fill:string,rotation=0){c.beginPath();c.ellipse(x,y,rx,ry,rotation,0,Math.PI*2);c.fillStyle=fill;c.fill();}
function line(c:CanvasRenderingContext2D,points:ScenePoint[],color:string,width:number){c.beginPath();points.forEach((p,i)=>i?c.lineTo(...p):c.moveTo(...p));c.strokeStyle=color;c.lineWidth=width;c.lineJoin='round';c.lineCap='round';c.stroke();}
function drawTree(c:CanvasRenderingContext2D,t:Tree,_lod:DetailLevel){foliage(c,t.x,t.y,t.size,['#4e793c','#6d8c4c','#3c6635','#7d965a'][t.shade],t.kind);}
function drawPark(c:CanvasRenderingContext2D,lod:DetailLevel){
 polygon(c,[[148,610],[285,536],[652,725],[481,801]],'#8eac72','#d6d0b4');
 line(c,[[151,610],[285,539],[649,725]],'#c8c9a7',3);
 for(const [x,y] of [[251,593],[315,639],[362,720],[467,769],[534,717]]){ellipse(c,x,y,12,5,'#788751',.4);for(let i=0;i<13;i++)ellipse(c,x+Math.cos(i*2.4)*9,y+Math.sin(i*2.4)*3.3,1.5,.9,['#dec593','#c7918b','#e0d8ac'][i%3]);}
 for(const [x,y,rx,ry] of [[270,585,60,20],[372,653,80,25],[478,732,64,24]])ellipse(c,x,y,rx,ry,'#a8b88c',.4);
 for(const l of [{x:266,y:619,rx:43,ry:20,rotation:.3},{x:398,y:690,rx:55,ry:23,rotation:.3},{x:490,y:738,rx:34,ry:16,rotation:.3}])drawLake(c,l.x,l.y,l.rx,l.ry,l.rotation,lod);
 for(const [x,y] of [[300,725],[380,760],[489,792]]){ellipse(c,x,y,16,6,'#507638',.3);for(let i=0;i<22;i++){const a=i/22*Math.PI*2;ellipse(c,x+Math.cos(a)*13,y+Math.sin(a)*4.5,1.8,1.1,i%3===0?'#dc9c6c':i%3===1?'#d9c279':'#b7786c');}}
 // A small repeated-kit museum block, never an additional landmark.
 prism(c,{id:'park-museum',x:8.5,y:18.5,w:1.2,d:.6,h:13,color:'#d5c9ad',district:'Richmond',kind:'normal',name:'Park block'},lod);

}
function drawWindmill(c:CanvasRenderingContext2D,lod:DetailLevel){
 const x=230,y=642;ellipse(c,x+7,y+4,15,6,'rgba(50,67,39,.18)');polygon(c,[[x-8,y],[x+7,y+3],[x+5,y-36],[x-4,y-38]],'#f1e9d4');polygon(c,[[x+7,y+3],[x+12,y],[x+7,y-35],[x+5,y-36]],'#b7bfae');polygon(c,[[x-7,y-36],[x+6,y-34],[x+1,y-45]],'#976c54');c.fillStyle='#677b6d';c.fillRect(x-1,y-18,3,7);
 c.save();c.translate(x+1,y-33);c.rotate(-.24);for(let i=0;i<4;i++){c.rotate(Math.PI/2);polygon(c,[[-1,0],[2,0],[4.5,-31],[-3.5,-31]],'#fbf3df');for(let j=6;j<30;j+=4)line(c,[[-3,-j],[4,-j]],'#b8baa5',lod?.7:.5);line(c,[[0,-4],[.7,-30]],'#c6c5b0',.7);}c.restore();ellipse(c,x+1,y-33,3,3,'#a7775c');ellipse(c,x+1,y-33,1.1,1.1,'#d7c49f');
}
export function renderStatic(c:CanvasRenderingContext2D,layout:CityLayout,lod:DetailLevel=0,bounds:Bounds={x:0,y:0,width:SCENE_WIDTH,height:SCENE_HEIGHT}){
 c.clearRect(bounds.x,bounds.y,bounds.width,bounds.height);
 c.save();c.shadowColor='rgba(80,137,145,.22)';c.shadowBlur=30;ellipse(c,720,563,650,320,'#34484b');c.restore();const base=c.createLinearGradient(0,530,0,887);base.addColorStop(0,'#8a9c8a');base.addColorStop(1,'#4f6665');ellipse(c,720,560,650,320,base as unknown as string);ellipse(c,720,535,650,320,'#a5b09a');
 c.save();c.beginPath();c.ellipse(720,530,650,320,0,0,Math.PI*2);c.clip();const water=c.createLinearGradient(300,200,1150,800);water.addColorStop(0,'#83b0c1');water.addColorStop(1,'#5c8fa6');c.fillStyle=water;c.fillRect(0,0,SCENE_WIDTH,SCENE_HEIGHT);
 c.strokeStyle='rgba(221,239,231,.07)';c.lineWidth=.5;for(let y=Math.max(210,Math.floor(bounds.y/9)*9);y<Math.min(850,bounds.y+bounds.height);y+=9){c.beginPath();c.moveTo(bounds.x,y);c.lineTo(bounds.x+bounds.width,y);c.stroke();}
 const coast=COAST.map(p=>project(...p));polygon(c,coast,material(c,200,280,900,600,'#a6bc8c',1.04,.91) as unknown as string);c.save();c.beginPath();coast.forEach((p,i)=>i?c.lineTo(...p):c.moveTo(...p));c.closePath();c.clip();
 // Hills are soft miniature terrain under repeated houses, not new geography data.
 ellipse(c,795,571,130,54,'#a6b18e',.35);ellipse(c,991,403,95,40,'#a2b08d',.22);ellipse(c,878,389,43,20,'#a2b08d',.12);
 for(const path of layout.paths.filter(p=>p.kind==='road')){const pts=path.points;const xs=pts.map(p=>p[0]),ys=pts.map(p=>p[1]);if(!intersects({x:Math.min(...xs)-12,y:Math.min(...ys)-12,width:Math.max(...xs)-Math.min(...xs)+24,height:Math.max(...ys)-Math.min(...ys)+24},bounds))continue;line(c,pts,'#e1ddc9',path.width+7);line(c,pts,'#7c8881',path.width);if(lod>0){c.setLineDash([3,7]);line(c,pts,'rgba(245,235,199,.55)',.65);c.setLineDash([]);}}
 drawPark(c,lod);for(const path of layout.paths.filter(p=>p.kind==='park'))line(c,path.points,'#dbd2b7',path.width);
 for(const path of layout.paths.filter(p=>p.id.startsWith('approach-')))line(c,path.points,'#d8d3bd',path.width);
 c.restore();
 // The coastal margin has a pale model-board shoreline.
 line(c,coast.slice(0,9),'#e3ddca',4);
 polygon(c,[[969,199],[1042,154],[1150,167],[1258,228],[1145,224],[1063,210],[993,230]],'#95ad77');polygon(c,[[1008,193],[1042,154],[1117,173],[1082,209]],'#b7c99a');polygon(c,[[1117,173],[1150,167],[1258,228],[1191,219]],'#a5bc87');line(c,[[982,209],[1049,181],[1157,185]],'#e0dcc1',7);
 if(intersects(layout.landmarks.find(l=>l.kind==='alcatraz')!.bounds,bounds))renderAlcatraz(c,lod);
 c.restore();
 polygon(c,[[393,336],[425,333],[452,351],[452,375],[427,386],[405,369]],'#a7b58a');line(c,[[408,343],[420,360],[438,369]],'#dad5bc',9);
 if(intersects(layout.landmarks.find(l=>l.kind==='bridge')!.bounds,bounds))drawBridge(c,lod);
 if(intersects(layout.landmarks.find(l=>l.kind==='palace')!.bounds,bounds))drawPalace(c,lod,layout.paths.filter(p=>p.kind==='park'&&p.district==='Marina').map(p=>p.points),layout.trees.filter(t=>t.x>180&&t.x<500&&t.y>280&&t.y<495),drawTree);
 drawWaterfront(c,layout,lod,bounds);
 // A few fixed benches and garden edges are revealed only at district/street scale.
 if(lod>0)for(const path of layout.paths.filter(p=>p.kind==='park'&&p.district==='Richmond'))for(let i=1;i<path.points.length;i+=Math.max(2,Math.ceil(path.points.length/2))){const p=path.points[i];if(!intersects({x:p[0]-8,y:p[1]-4,width:16,height:10},bounds))continue;line(c,[[p[0]-4,p[1]+6],[p[0]+4,p[1]+8]],'#a79576',2);if(lod===2){line(c,[[p[0]-3,p[1]+8],[p[0]-3,p[1]+11]],'#75806c',.7);line(c,[[p[0]+3,p[1]+9],[p[0]+3,p[1]+12]],'#75806c',.7);}}
 // Cast all building shadows onto the ground first, then depth-sort the physical pieces.
 for(const b of layout.buildings){const feet=[project(b.x,b.y),project(b.x+b.w,b.y),project(b.x+b.w,b.y+b.d),project(b.x,b.y+b.d)];castShadow(c,feet,b.h+(b.kind==='pyramid'?60:0),b.kind==='tower'?.14:.19);}
 const pieces=[...layout.trees.filter(t=>!(t.x>180&&t.x<500&&t.y>280&&t.y<495)).map(tree=>({depth:tree.y,tree,building:null as Building|null})),...layout.buildings.map(building=>({depth:project(building.x+building.w/2,building.y+building.d/2)[1],tree:null as Tree|null,building}))].sort((a,b)=>a.depth-b.depth);
 for(const piece of pieces){if(piece.tree){const t=piece.tree;if(intersects({x:t.x-18,y:t.y-35,width:36,height:45},bounds))drawTree(c,t,lod);}else if(piece.building&&intersects(buildingBounds(piece.building),bounds))prism(c,piece.building,lod);}
 if(intersects({x:190,y:568,width:88,height:84},bounds))drawWindmill(c,lod);


}
export type SceneTile={canvas:HTMLCanvasElement;bounds:Bounds};
export class StaticSceneCache{
 readonly layers:SceneTile[][]=[[],[],[]];readonly renderCount:number;
 constructor(layout:CityLayout){let count=0;const tileSize=360;for(const lod of [0,1,2] as const)for(let y=0;y<SCENE_HEIGHT;y+=tileSize)for(let x=0;x<SCENE_WIDTH;x+=tileSize){const bounds={x,y,width:Math.min(tileSize,SCENE_WIDTH-x),height:Math.min(tileSize,SCENE_HEIGHT-y)};const density=[1,2,4][lod],canvas=document.createElement('canvas');canvas.width=(bounds.width+4)*density;canvas.height=(bounds.height+4)*density;const c=canvas.getContext('2d')!;c.scale(density,density);c.translate(-x+2,-y+2);renderStatic(c,layout,lod,{x:x-2,y:y-2,width:bounds.width+4,height:bounds.height+4});this.layers[lod].push({canvas,bounds});count++;}this.renderCount=count;}
 draw(c:CanvasRenderingContext2D,lod:DetailLevel,viewport:Bounds){let count=0;for(const tile of this.layers[lod])if(intersects(tile.bounds,viewport)){const b=tile.bounds;c.drawImage(tile.canvas,b.x-2,b.y-2,b.width+4,b.height+4);count++;}return count;}
 dispose(){for(const layer of this.layers)for(const tile of layer){tile.canvas.width=0;tile.canvas.height=0;}}
}
export function landmarkAt(layout:CityLayout,x:number,y:number):Landmark|undefined{
 for(const l of layout.landmarks){if(!landmarkKinds.includes(l.kind))continue;const b=layout.buildings.find(b=>b.id===l.id);if(b&&pointInPolygon(x,y,buildingOutline(b)))return l;}
 // Tight hit zones keep the bridge and park from intercepting nearby buildings.
 const palace=layout.landmarks.find(l=>l.kind==='palace')!;if((x>283&&x<397&&y>225&&y<400)||(((x-340)/123)**2+((y-390)/82)**2<1))return palace;
 const park=layout.landmarks.find(l=>l.kind==='park')!;if(pointInPark(x,y))return park;
 const bridge=layout.landmarks.find(l=>l.kind==='bridge')!;const distance=Math.abs(145*x+575*y-267900)/Math.hypot(145,575);if(x>415&&x<1000&&distance<11)return bridge;
 const island=layout.landmarks.find(l=>l.kind==='alcatraz')!;if(((x-island.x)/77)**2+((y-island.y)/35)**2<1||x>1099&&x<1110&&y>278&&y<313)return island;
 return undefined;
}
function pointInPark(x:number,y:number){return x>148&&x<652&&y>536&&y<801&&x+y>750&&y-x*.56>365&&y-x*.56<550;}
