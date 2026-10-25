export type Point = [number, number];
export type Bounds = { x: number; y: number; width: number; height: number };
export const SCENE_WIDTH = 1440;
export const SCENE_HEIGHT = 940;
export const OVERVIEW = { x: 720, y: 505, width: 1440, height: 820 };
export const project = (x: number, y: number, height = 0): Point => [700 + (x - y) * 32, 195 + (x + y) * 16 - height];
export const unproject = (x: number, y: number): Point => [(x - 700) / 64 + (y - 195) / 32, (y - 195) / 32 - (x - 700) / 64];
export const COAST: Point[] = [[-3,11],[0,9],[3,9],[4,7],[6,8],[8,6],[8,3],[10,2],[11,-3],[22,-2],[22,22],[-4,25],[-4,14]];
export function pointInPolygon(x: number, y: number, points: Point[]) {
  let inside = false;
  for (let i = 0, j = points.length - 1; i < points.length; j = i++) {
    const a = points[i], b = points[j];
    if ((a[1] > y) !== (b[1] > y) && x < (b[0] - a[0]) * (y - a[1]) / (b[1] - a[1]) + a[0]) inside = !inside;
  }
  return inside;
}
export function onLand(x: number, y: number) {
  const p = project(x,y);
  return pointInPolygon(x,y,COAST) && ((p[0]-720)/650)**2 + ((p[1]-530)/320)**2 < .94;
}
export const intersects = (a: Bounds, b: Bounds) => a.x < b.x+b.width && a.x+a.width > b.x && a.y < b.y+b.height && a.y+a.height > b.y;
export function pathLength(points: Point[]) { let length=0; for(let i=1;i<points.length;i++) length+=Math.hypot(points[i][0]-points[i-1][0],points[i][1]-points[i-1][1]); return length; }
export function pointAlong(points: Point[], progress: number, length=pathLength(points)): {x:number;y:number;angle:number} {
  let remaining=Math.max(0,Math.min(1,progress))*length;
  for(let i=1;i<points.length;i++) {const a=points[i-1],b=points[i],d=Math.hypot(b[0]-a[0],b[1]-a[1]);if(remaining<=d||i===points.length-1){const t=d?Math.min(1,remaining/d):0;return {x:a[0]+(b[0]-a[0])*t,y:a[1]+(b[1]-a[1])*t,angle:Math.atan2(b[1]-a[1],b[0]-a[0])};}remaining-=d;}
  return {x:points[0][0],y:points[0][1],angle:0};
}

// Bake rounded paths into the fixture, so walkers and painted footpaths share
// exactly the same centreline at every level of detail.
export function smoothPath(points:Point[]):Point[]{const out:Point[]=[points[0]];let start=points[0];for(let i=1;i<points.length-1;i++){const control=points[i],end:Point=[(control[0]+points[i+1][0])/2,(control[1]+points[i+1][1])/2];for(let step=1;step<=12;step++){const t=step/12,u=1-t;out.push([u*u*start[0]+2*u*t*control[0]+t*t*end[0],u*u*start[1]+2*u*t*control[1]+t*t*end[1]]);}start=end;}out.push(points[points.length-1]);return out;}
