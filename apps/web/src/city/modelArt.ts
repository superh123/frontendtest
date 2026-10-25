import type {Point} from './cityGeometry';
export type Paint=string|CanvasGradient;
export function face(c:CanvasRenderingContext2D,p:Point[],fill:Paint,edge?:string){c.beginPath();p.forEach((v,i)=>i?c.lineTo(...v):c.moveTo(...v));c.closePath();c.fillStyle=fill;c.fill();if(edge){c.strokeStyle=edge;c.lineWidth=.55;c.stroke();}}
export function oval(c:CanvasRenderingContext2D,x:number,y:number,rx:number,ry:number,fill:Paint,rotation=0){c.beginPath();c.ellipse(x,y,rx,ry,rotation,0,Math.PI*2);c.fillStyle=fill;c.fill();}
export function stroke(c:CanvasRenderingContext2D,p:Point[],color:string,w=1){c.beginPath();p.forEach((v,i)=>i?c.lineTo(...v):c.moveTo(...v));c.strokeStyle=color;c.lineWidth=w;c.lineJoin='round';c.lineCap='round';c.stroke();}
export function tint(hex:string,n:number){const v=parseInt(hex.slice(1),16);return `rgb(${Math.min(255,(v>>16)*n)},${Math.min(255,((v>>8)&255)*n)},${Math.min(255,(v&255)*n)})`;}
export function material(c:CanvasRenderingContext2D,x:number,y:number,w:number,h:number,color:string,bright=1,dark=.87){const g=c.createLinearGradient(x,y,x+w,y+h);g.addColorStop(0,tint(color,bright));g.addColorStop(1,tint(color,dark));return g;}
export const LIGHT={x:.42,y:.24};
export function castShadow(c:CanvasRenderingContext2D,foot:Point[],height:number,opacity=.20){
 const end=foot.map(p=>[p[0]+height*LIGHT.x,p[1]+height*LIGHT.y] as Point);
 c.save();c.shadowColor=`rgba(37,49,35,${opacity})`;c.shadowBlur=7;c.shadowOffsetX=3;c.shadowOffsetY=2;
 // Convex hull of the footprint and its projection: a continuous grounded cast shadow.
 const all=[...foot,...end].sort((a,b)=>a[0]-b[0]||a[1]-b[1]);const cross=(a:Point,b:Point,p:Point)=>(b[0]-a[0])*(p[1]-a[1])-(b[1]-a[1])*(p[0]-a[0]);
 const lower:Point[]=[],upper:Point[]=[];for(const p of all){while(lower.length>1&&cross(lower.at(-2)!,lower.at(-1)!,p)<=0)lower.pop();lower.push(p);}for(const p of [...all].reverse()){while(upper.length>1&&cross(upper.at(-2)!,upper.at(-1)!,p)<=0)upper.pop();upper.push(p);}face(c,[...lower.slice(0,-1),...upper.slice(0,-1)],`rgba(44,58,39,${opacity})`);c.restore();
}
// Small architectural solids in screen coordinates, sharing the main model's 2:1 projection.
export function block(c:CanvasRenderingContext2D,x:number,y:number,w:number,d:number,h:number,color='#ded6c3'){
 const p:Point=[x,y],a:Point=[x+w,y+w*.5],z:Point=[x+w-d,y+(w+d)*.5],v:Point=[x-d,y+d*.5];
 face(c,[v,z,[z[0],z[1]-h],[v[0],v[1]-h]],material(c,v[0],v[1]-h,w,h,color,.92,.79));face(c,[a,z,[z[0],z[1]-h],[a[0],a[1]-h]],material(c,a[0],a[1]-h,-d,h,color,.78,.64));face(c,[[x,y-h],[a[0],a[1]-h],[z[0],z[1]-h],[v[0],v[1]-h]],material(c,x-d,y-h,w+d,15,color,1.08,.98),'rgba(255,248,220,.38)');return {p,a,z,v};
}
export function arch(c:CanvasRenderingContext2D,x:number,bottom:number,w:number,h:number,trim='#e5d2b4',dark='#646a60',thickness=1.8){c.beginPath();c.moveTo(x-w/2,bottom);c.lineTo(x-w/2,bottom-h+w/2);c.arc(x,bottom-h+w/2,w/2,Math.PI,Math.PI*2);c.lineTo(x+w/2,bottom);c.closePath();c.fillStyle=dark;c.fill();c.strokeStyle=trim;c.lineWidth=thickness;c.stroke();}
export function arcade(c:CanvasRenderingContext2D,a:Point,b:Point,h:number,count:number,lod:number,trim='#eee1c5',dark='#738078'){
 const width=Math.hypot(b[0]-a[0],b[1]-a[1]);c.save();c.transform((b[0]-a[0])/width,(b[1]-a[1])/width,0,1,a[0],a[1]-h);
 for(let i=0;i<count;i++){const x=(i+.5)*width/count;arch(c,x,h-3,width/count*.47,h*.55,trim,dark,lod?1.2:.8);}
 stroke(c,[[0,2],[width,2]],trim,1.4);c.restore();
}
export function foliage(c:CanvasRenderingContext2D,x:number,y:number,size:number,color='#56813f',kind=0){
 c.save();c.shadowColor='rgba(36,52,30,.18)';c.shadowBlur=3;oval(c,x+size*.8,y+size*.4,size*1.25,size*.42,'rgba(37,56,30,.17)',.35);c.restore();
 stroke(c,[[x,y],[x,y-size*.8]],'#8c7350',Math.max(1,size*.18));
 if(kind===1){const g=material(c,x-size,y-size*2.6,size*2,size*2,color,1.16,.69);c.beginPath();c.moveTo(x,y-size*2.7);c.bezierCurveTo(x+size*.65,y-size*2.1,x+size*.78,y-size*.5,x+size*.56,y-2);c.quadraticCurveTo(x,y+1,x-size*.56,y-2);c.bezierCurveTo(x-size*.78,y-size*.5,x-size*.65,y-size*2.1,x,y-size*2.7);c.fillStyle=g;c.fill();return;}
 // Overlapping matte lobes produce a small physical canopy, rather than a glossy sphere.
 for(const [dx,dy,rx,ry,n]of [[.24,-.83,.76,.84,.81],[-.35,-1.0,.68,.83,1.01],[.02,-1.43,.73,.79,1.05],[.31,-1.23,.57,.64,.91]]){const g=material(c,x+(dx-rx)*size,y+(dy-ry)*size,rx*2*size,ry*2*size,tintHex(color,n),1.12,.86);oval(c,x+dx*size,y+dy*size,rx*size,ry*size,g);}
}
function tintHex(hex:string,n:number){const v=parseInt(hex.slice(1),16);return '#'+[v>>16,(v>>8)&255,v&255].map(a=>Math.min(255,Math.round(a*n)).toString(16).padStart(2,'0')).join('');}
