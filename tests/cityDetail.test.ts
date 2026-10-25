import {describe,it,expect} from 'vitest';
import {CityCamera,levelOfDetail} from '../apps/web/src/city/CityCamera';
import {getCityLayout,getSnapshot} from '../apps/web/src/data/fixtures';
import {readDistrictActivity} from '../apps/web/src/city/activity';
import {createMoverPool,updateMovers} from '../apps/web/src/city/movers';
import type {DistrictActivity} from '../apps/web/src/city/activity';
describe('city navigation',()=>{
 it('keeps the world point under an off-centre cursor when zooming',()=>{const c=new CityCamera();c.resize(1000,600);const before=c.screenToWorld(315,265);c.zoomAt(315,265,3,0);c.update(300);const after=c.screenToWorld(315,265);expect(after[0]).toBeCloseTo(before[0],7);expect(after[1]).toBeCloseTo(before[1],7);});
 it('eases, pans at zoom, and returns to the exact overview pose',()=>{const c=new CityCamera();c.resize(1000,600);const initial={...c.pose};c.focus(340,382,2.55,false,0);c.update(150);expect(c.pose.zoom).toBeGreaterThan(1);expect(c.pose.zoom).toBeLessThan(2.55);c.update(300);const p={...c.pose};c.pan(50,-20);expect(c.pose.x).toBeLessThan(p.x);expect(c.pose.y).toBeGreaterThan(p.y);c.home(400);c.update(700);expect(c.pose).toEqual(initial);});
 it('reveals the four required levels and only calls a focused building LOD 3',()=>{expect([levelOfDetail(1),levelOfDetail(2.55),levelOfDetail(4.6),levelOfDetail(6.8,true)]).toEqual([0,1,2,3]);expect(levelOfDetail(6.8,false)).toBe(2);});
});
describe('activity-driven pooled movers',()=>{
 const layout=getCityLayout(),baseline=getSnapshot(0,'baseline'),view={x:0,y:0,width:1440,height:940};
 function activity(tick:number,branch:'baseline'|'shock'){const s=getSnapshot(tick,branch);return {s,values:new Map(layout.districts.map(d=>[d.name,readDistrictActivity(s,baseline,d.name)])) as Map<string,DistrictActivity>,firms:new Map(s.firms.map(f=>[f.id,f.open]))};}
 it('keeps exactly the same 400 identities and correct path types through a shock',()=>{const pool=createMoverPool(layout),identities=[...pool],healthy=activity(6,'baseline'),shock=activity(24,'shock');expect(pool).toHaveLength(400);expect(pool.filter(m=>m.car).every(m=>m.path.kind==='road')).toBe(true);expect(pool.filter(m=>!m.car).every(m=>m.path.kind!=='road')).toBe(true);const a=updateMovers(pool,0,10,healthy.values,healthy.firms,view);const b=updateMovers(pool,0,10,shock.values,shock.firms,view);expect(pool.every((m,i)=>m===identities[i])).toBe(true);expect(b.active).toBeLessThan(a.active);expect(b.queued).toBeLessThan(a.queued);expect(pool.filter(m=>m.targetId==='cafe-14').every(m=>!m.active)).toBe(true);});
 it('derives visible distress from the recorded district activity',()=>{const a=activity(24,'shock').values.get('Mission District')!;expect(a.shutters).toBe(true);expect(a.bankStress).toBe(true);expect(a.queueCapacity).toBeLessThan(6);});
});
