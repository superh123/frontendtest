import {describe,it,expect} from 'vitest';
import {bridgeSection,pierGeometry,shoreline} from '../apps/web/src/city/landmarkArt';
import {landmarkAt} from '../apps/web/src/city/cityRenderer';
import {project} from '../apps/web/src/city/cityGeometry';
import {getCityLayout} from '../apps/web/src/data/fixtures';
import {pointInPolygon} from '../apps/web/src/city/cityGeometry';
describe('landmark construction',()=>{
 it('uses two continuous anchored cables with every suspender below its cable',()=>{
  for(const side of [-1,1]){expect(bridgeSection(0,side).height).toBe(0);expect(bridgeSection(1,side).height).toBe(0);let previous=bridgeSection(0,side);for(let i=1;i<=1000;i++){const p=bridgeSection(i/1000,side);expect(p.cable[1]).toBeLessThanOrEqual(p.deck[1]);expect(Math.hypot(p.cable[0]-previous.cable[0],p.cable[1]-previous.cable[1])).toBeLessThan(2);previous=p;}}
  expect(bridgeSection(.5,1).cable).not.toEqual(bridgeSection(.5,-1).cable);
 });
 it('places all four piers across the shoreline, perpendicular and within the model',()=>{
  const l=getCityLayout();expect(l.piers).toHaveLength(4);
  for(const pier of l.piers){expect(pier.x+2*pier.y).toBeCloseTo(2498);const g=pierGeometry(pier.x,pier.y,pier.length);expect(g.normal[0]*g.tangent[0]+g.normal[1]*g.tangent[1]).toBeCloseTo(0);expect(g.point(-4,0)[0]+2*g.point(-4,0)[1]).toBeLessThan(2498);expect(g.point(pier.length,0)[0]+2*g.point(pier.length,0)[1]).toBeGreaterThan(2498);for(const [x,y] of g.top)expect(((x-720)/650)**2+((y-530)/320)**2).toBeLessThan(1);}
  const ferry=l.buildings.find(b=>b.kind==='ferry')!;expect(ferry.x+ferry.w).toBeCloseTo(22);
 });
 it('keeps irregular lake surfaces inside the dry path envelope',()=>{
  for(const lake of getCityLayout().water.lakes){const p=shoreline(lake.x,lake.y,lake.rx,lake.ry,lake.rotation);const radii=p.map(([x,y])=>{const dx=x-lake.x,dy=y-lake.y,c=Math.cos(lake.rotation),s=Math.sin(lake.rotation);return Math.hypot((dx*c+dy*s)/lake.rx,(-dx*s+dy*c)/lake.ry);});expect(Math.max(...radii)).toBeLessThan(1);expect(Math.max(...radii)-Math.min(...radii)).toBeGreaterThan(.05);}
 });
 it('keeps tree trunks off the four lake surfaces',()=>{const l=getCityLayout();for(const t of l.trees)for(const lake of l.water.lakes){const dx=t.x-lake.x,dy=t.y-lake.y,c=Math.cos(lake.rotation),s=Math.sin(lake.rotation);expect(((dx*c+dy*s)/lake.rx)**2+((-dx*s+dy*c)/lake.ry)**2).toBeGreaterThanOrEqual(1);}});
 it('plants dense woodland in the long park without covering its windmill',()=>{
  const park=getCityLayout().trees.filter(t=>pointInPolygon(t.x,t.y,[[148,610],[285,536],[652,725],[481,801]]));expect(park.length).toBeGreaterThan(170);expect(park.some(t=>t.size>9)).toBe(true);
 });
});

it('resolves all architectural landmarks to their names rather than overlapping businesses',()=>{const l=getCityLayout();for(const kind of ['coit','pyramid','salesforce','ferry']){const b=l.buildings.find(b=>b.kind===kind)!;const p=project(b.x+b.w/2,b.y+b.d/2,b.h*.55);expect(landmarkAt(l,...p)?.name).toBe(b.name);}for(const [kind,p]of [['palace',[340,288]],['alcatraz',[1070,307]],['park',[230,642]],['bridge',[700,289]]] as const)expect(landmarkAt(l,p[0],p[1])?.kind).toBe(kind);});

it('keeps Alcatraz in open bay water inside the tabletop edge',()=>{const l=getCityLayout(),island=l.landmarks.find(l=>l.kind==='alcatraz')!;for(let i=0;i<48;i++){const a=i/48*Math.PI*2,x=island.x+Math.cos(a)*74,y=island.y+Math.sin(a)*28;expect(((x-720)/650)**2+((y-530)/320)**2).toBeLessThan(1);const coastY=387-(x-956)/3;expect(y).toBeLessThan(coastY);}});
