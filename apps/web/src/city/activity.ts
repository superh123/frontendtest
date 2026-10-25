import type {Snapshot} from '../data/types';
export type DistrictActivity={employment:number;retail:number;leisure:number;open:number;defaults:number;queueCapacity:number;dimShops:boolean;shutters:boolean;bankStress:boolean};
export function readDistrictActivity(snapshot:Snapshot,baseline:Snapshot,district:string):DistrictActivity{
 const a=snapshot.districts[district]??snapshot.districts['Mission District'],b=baseline.districts[district]??baseline.districts['Mission District'];
 const retail=Math.max(0,a.retailDemandIndex/100),employment=Math.max(0,a.employmentRate/Math.max(1,b.employmentRate)),open=Math.max(0,a.firmOpenRate/100);
 return {employment,retail,leisure:Math.max(0,a.disposableIncomeIndex/100),open,defaults:a.defaultRate,queueCapacity:Math.max(0,Math.floor(6*retail*open)),dimShops:retail<=.9,shutters:retail<=.75,bankStress:a.defaultRate>5};
}
export type Destination='work'|'shop'|'leisure'|'home';
export function destinationFor(period:number,index:number,park:boolean):Destination{if(park)return 'leisure';if(period<20)return index%5?'work':'shop';if(period<40)return index%5?'shop':'work';if(period<55)return index%3?'leisure':'home';return 'home';}
export function movementAmplitude(a:DistrictActivity,destination:Destination,car:boolean,period:number){const amplitude=destination==='work'?a.employment:destination==='shop'?a.retail*a.open:destination==='leisure'?a.leisure:1;return Math.min(1.25,amplitude)*(period>=55?(car?.25:.2):1);}
