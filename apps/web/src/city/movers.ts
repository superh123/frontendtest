import type {Building,CityLayout,ScenePath,Snapshot} from '../data/types';
import {pathLength,pointAlong,project,type Bounds} from './cityGeometry';
import {destinationFor,movementAmplitude,type Destination,type DistrictActivity} from './activity';
export type VisualMover={id:number;car:boolean;van:boolean;homeDistrict:string;destinationType:Destination;targetId:string|null;path:ScenePath;length:number;progress:number;speed:number;rank:number;queueIndex:number;x:number;y:number;angle:number;active:boolean;visible:boolean};
export function createMoverPool(layout:CityLayout):VisualMover[]{
 const roads=layout.paths.filter(p=>p.kind==='road'&&pathLength(p.points)>65),walks=layout.paths.filter(p=>p.kind==='footpath'&&!p.id.startsWith('approach-')&&pathLength(p.points)>35),parks=layout.paths.filter(p=>p.kind==='park');
 const allShops=[...layout.buildings.filter(b=>b.id==='cafe-14'),...layout.buildings.filter(b=>b.kind==='shop'&&b.id!=='cafe-14')];const shops=allShops.slice(0,12);
 return Array.from({length:400},(_,id)=>{const car=id<100,queue=id>=100&&id<172,shop=queue?shops[((id-100)%shops.length+shops.length)%shops.length]:allShops[id%allShops.length];const park=!car&&!queue&&id%4===0;const approach=layout.paths.find(p=>p.id==='approach-'+shop.id)!;const path=car?roads[id%roads.length]:park?parks[id%parks.length]:id%3===1?walks[id%walks.length]:approach??walks[id%walks.length];return {id,car,van:car&&id%11===0,homeDistrict:path.district,destinationType:queue?'shop':'work',targetId:!car&&!park?shop.id:null,path,length:pathLength(path.points),progress:((id*0.61803398875)%1),speed:car?12+(id%5)*2:4+(id%4)*.6,rank:((id*17)%97)/97,queueIndex:queue?Math.floor((id-100)/shops.length):-1,x:0,y:0,angle:0,active:true,visible:true};});
}
export function updateMovers(pool:VisualMover[],dt:number,time:number,activities:Map<string,DistrictActivity>,firms:Map<string,boolean>,viewport:Bounds){const period=time%60;let active=0,drawn=0,queued=0;
 for(const m of pool){const a=activities.get(m.homeDistrict)!;m.destinationType=m.queueIndex>=0?'shop':destinationFor(period,m.id,m.path.kind==='park');const open=!m.targetId||firms.get(m.targetId)!==false;
 m.active=open&&(m.queueIndex>=0?m.queueIndex<a.queueCapacity:m.rank<movementAmplitude(a,m.destinationType,m.car,period));if(!m.active){m.visible=false;continue;}active++;
 if(m.queueIndex>=0){const p=pointAlong(m.path.points,Math.min(.95,.10+m.queueIndex*.13),m.length);m.x=p.x;m.y=p.y;m.angle=p.angle;queued++;}
 else{m.progress=(m.progress+dt*m.speed/m.length)%1;const p=pointAlong(m.path.points,m.progress,m.length);m.x=p.x;m.y=p.y;m.angle=p.angle;}
 m.visible=m.x>viewport.x-18&&m.x<viewport.x+viewport.width+18&&m.y>viewport.y-25&&m.y<viewport.y+viewport.height+25;if(m.visible)drawn++;
 }return {active,drawn,queued};
}
export function drawMover(c:CanvasRenderingContext2D,m:VisualMover,lod:0|1|2|3,time:number){
 c.save();c.translate(m.x,m.y);if(m.car){c.rotate(m.angle);c.fillStyle='rgba(35,55,49,.17)';c.fillRect(-5,1,11,3);const length=m.van?12:lod?10:7,width=lod?4:3;c.fillStyle=['#e8c99a','#b4c7c2','#cb9685','#ede5cd','#b5c0ab'][m.id%5];c.fillRect(-length/2,-width/2,length,width);if(lod){c.fillStyle='#667f82';c.fillRect(1,-width/2+.5,2,width-1);c.fillStyle='#dde9de';c.fillRect(length/2-.7,-width/2+.4,.7,.7);c.fillRect(length/2-.7,width/2-1.1,.7,.7);if(lod>=2){c.fillStyle='#4c5a51';c.fillRect(-3,-width/2-.4,2,.8);c.fillRect(2,width/2-.4,2,.8);}}}
 else if(!lod){c.fillStyle=['#c5ab89','#536d63','#b88e7f','#e6d9b8'][m.id%4];c.beginPath();c.arc(0,-1.5,1.5,0,7);c.fill();}
 else{c.fillStyle='rgba(50,67,44,.18)';c.beginPath();c.ellipse(1.5,1,2.8,1.1,.3,0,7);c.fill();const sway=m.queueIndex>=0?0:Math.sin(time*7+m.id)*.65;const h=lod===1?4.6:6.2;c.strokeStyle=['#c1a58b','#667e75','#c49b8c','#b8c3a4','#8a9fa5'][m.id%5];c.lineWidth=lod===1?2:2.4;c.lineCap='round';c.beginPath();c.moveTo(0,-h);c.lineTo(0,-2);c.stroke();c.strokeStyle='#72796c';c.lineWidth=.65;c.beginPath();c.moveTo(-.6,-2);c.lineTo(-1.2+sway,.5);c.moveTo(.6,-2);c.lineTo(1.2-sway,.5);c.stroke();c.fillStyle='#ddc5a1';c.beginPath();c.arc(Math.cos(m.angle)*.35,-h-1.4,lod===1?1.1:1.35,0,7);c.fill();if(lod>=2){c.strokeStyle='#cdbb9b';c.lineWidth=.8;c.beginPath();c.moveTo(-1,-h+1);c.lineTo(-2.1+sway,-h+3.3);c.moveTo(1,-h+1);c.lineTo(2.1-sway,-h+3.3);c.stroke();}}
 c.restore();
}
export function shopDoor(b:Building){return project(b.x+b.w*.5,b.y+b.d,b.elevation??0);}
