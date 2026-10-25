import {OVERVIEW, type Bounds, type Point} from './cityGeometry';
export type CameraPose={x:number;y:number;zoom:number};
export function levelOfDetail(zoom:number,buildingFocus=false):0|1|2|3{return buildingFocus&&zoom>=5.8?3:zoom<1.55?0:zoom<3.5?1:2;}
export class CityCamera{
 pose:CameraPose={x:OVERVIEW.x,y:OVERVIEW.y,zoom:1};target={...this.pose};private from={...this.pose};private started=0;private animating=false;
 width=1;height=1;baseScale=1;buildingFocus=false;
 resize(width:number,height:number){this.width=width;this.height=height;this.baseScale=Math.min(width/OVERVIEW.width,height/OVERVIEW.height)*.98;}
 screenToWorld(x:number,y:number,pose=this.pose):Point{return [pose.x+(x-this.width/2)/(this.baseScale*pose.zoom),pose.y+(y-this.height/2)/(this.baseScale*pose.zoom)];}
 worldToScreen(x:number,y:number):Point{return [this.width/2+(x-this.pose.x)*this.baseScale*this.pose.zoom,this.height/2+(y-this.pose.y)*this.baseScale*this.pose.zoom];}
 private animate(target:CameraPose,now=performance.now()){this.from={...this.pose};this.target={...target,x:Math.max(80,Math.min(1380,target.x)),y:Math.max(130,Math.min(870,target.y))};this.started=now;this.animating=true;}
 zoomAt(x:number,y:number,zoom:number,now=performance.now()){zoom=Math.max(1,Math.min(8,zoom));this.buildingFocus=false;if(zoom<=1.01){this.home(now);return;}const world=this.screenToWorld(x,y);this.animate({zoom,x:world[0]-(x-this.width/2)/(this.baseScale*zoom),y:world[1]-(y-this.height/2)/(this.baseScale*zoom)},now);}
 focus(x:number,y:number,zoom:number,building=false,now=performance.now()){this.buildingFocus=building;this.animate({x,y,zoom:Math.max(1,Math.min(8,zoom))},now);}
 pan(dx:number,dy:number){if(this.pose.zoom<=1.02)return;const scale=this.baseScale*this.pose.zoom;this.animating=false;this.pose={...this.pose,x:Math.max(80,Math.min(1380,this.pose.x-dx/scale)),y:Math.max(130,Math.min(870,this.pose.y-dy/scale))};this.target={...this.pose};}
 home(now=performance.now()){this.buildingFocus=false;this.animate({x:OVERVIEW.x,y:OVERVIEW.y,zoom:1},now);}
 update(now:number){if(!this.animating)return;const t=Math.min(1,Math.max(0,(now-this.started)/300)),e=1-(1-t)**3;this.pose={x:this.from.x+(this.target.x-this.from.x)*e,y:this.from.y+(this.target.y-this.from.y)*e,zoom:this.from.zoom+(this.target.zoom-this.from.zoom)*e};if(t>=1)this.animating=false;}
 viewport():Bounds{const a=this.screenToWorld(0,0),b=this.screenToWorld(this.width,this.height);return {x:a[0],y:a[1],width:b[0]-a[0],height:b[1]-a[1]};}
}
