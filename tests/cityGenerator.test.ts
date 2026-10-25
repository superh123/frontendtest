import {describe,it,expect} from 'vitest';
import {getCityLayout} from '../apps/web/src/data/fixtures';
import {generateCityLayout,hashLayout} from '../apps/web/src/city/cityGenerator';
import {cityTemplate} from '../apps/web/src/data/cityTemplates';
describe('committed detailed city layout',()=>{
 it('preserves a stable deterministic layout hash for the fixed seed',()=>{const l=getCityLayout();expect(l.layoutSeed).toBe(4242);expect(l.layoutHash).toBe('sf-f6319404');expect(hashLayout(l)).toBe(l.layoutHash);expect(generateCityLayout(4242)).toEqual(l);expect(generateCityLayout(4242).layoutHash).toBe(l.layoutHash);});
 it('uses the separate layout seed for repeatable scenery',()=>{const a=generateCityLayout(4243),b=generateCityLayout(4243);expect(a).toEqual(b);expect(a.layoutHash).not.toBe(getCityLayout().layoutHash);expect(a.simulationSeed).toBe(getCityLayout().simulationSeed);});
 it('contains precisely the original six and the two requested landmarks',()=>{const l=getCityLayout();expect(l.landmarks.map(l=>l.name).sort()).toEqual([...cityTemplate.landmarks].sort());expect(l.landmarks).toHaveLength(8);expect(l.landmarks.find(l=>l.kind==='palace')?.district).toBe('Marina');expect(l.landmarks.find(l=>l.kind==='park')?.district).toBe('Richmond');expect(new Set(l.buildings.map(b=>b.id)).size).toBe(l.buildings.length);});
 it('commits separate road and footpath routes plus lake and park geometry',()=>{const l=getCityLayout();expect(l.paths.some(p=>p.kind==='road')).toBe(true);expect(l.paths.some(p=>p.kind==='park'&&p.district==='Richmond')).toBe(true);expect(l.paths.find(p=>p.id==='approach-cafe-14')?.kind).toBe('footpath');expect(l.water.lakes.length).toBeGreaterThanOrEqual(4);expect(l.trees.length).toBeGreaterThan(150);});
});

it('keeps baked park path samples outside all lake surfaces',()=>{const l=getCityLayout();for(const p of l.paths.filter(p=>p.kind==='park'))for(const [x,y]of p.points.flatMap((a,i)=>i===p.points.length-1?[a]:[0,.25,.5,.75].map(t=>[a[0]+(p.points[i+1][0]-a[0])*t,a[1]+(p.points[i+1][1]-a[1])*t])))for(const lake of l.water.lakes){const dx=x-lake.x,dy=y-lake.y,c=Math.cos(lake.rotation),s=Math.sin(lake.rotation);const value=((dx*c+dy*s)/lake.rx)**2+((-dx*s+dy*c)/lake.ry)**2;expect(value,`${p.id} at ${x},${y}`).toBeGreaterThanOrEqual(1);}});
