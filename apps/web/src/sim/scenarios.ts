import type {Scenario,ShockType} from '../data/types';
export function parseScenario(promptText:string):Scenario{
 const p=promptText.toLowerCase();
 const mapping:[ShockType,RegExp][]=[['interest_rate',/interest|rate|mortgage/],['rent',/rent|landlord/],['wages',/wage|salary|\bpay\b/],['credit',/credit|loan|lending|bank/],['tax',/tax/],['prices',/price|inflation|cost of living/]];
 const shockType=mapping.find(([,r])=>r.test(p))?.[0]??'interest_rate';
 const duration=p.match(/(\d+)\s*(month|year)/);const number=p.replace(/\d+\s*(months?|years?)/g,'').match(/\d+(?:\.\d+)?/);
 return {shockType,direction:/fall|lower|decrease|cut|down/.test(p)?'down':'up',magnitude:number?Number(number[0]):shockType==='interest_rate'?2:20,durationMonths:Math.min(60,Math.max(6,duration?Number(duration[1])*(duration[2]==='year'?12:1):/a year|one year/.test(p)?12:24)),targetSector:/cafes|restaurants/.test(p)?'hospitality':['hospitality','retail','construction','finance','tech','services'].find(s=>p.includes(s))??null,promptText};
}
