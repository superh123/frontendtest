import snapshots from './fixtures/sfSnapshots.json';
import feed from './fixtures/sfFeed.json';
import proposal from './fixtures/sfProposal.json';
import inspectors from './fixtures/sfInspector.json';
import layout from './fixtures/sfCityLayout.json';
import fork from './fixtures/sfFork.json';
import network from './fixtures/sfNetwork.json';
import payment from './fixtures/sfPayment.json';
import crisis from './fixtures/sfCrisis.json';
import type {Branch,Snapshot,FeedItem,CityLayout} from './types';
export function getSnapshot(tick:number,branch:Branch):Snapshot{return snapshots.find(s=>s.tick===Math.max(0,Math.min(24,Math.round(tick)))&&s.branch===branch)! as Snapshot;}
export function getFeed(tick:number):FeedItem[]{return feed.filter(f=>f.tick<=tick).sort((a,b)=>b.tick-a.tick||b.id.localeCompare(a.id)).slice(0,30) as FeedItem[];}
export function getProposal(){return proposal;}
export function getInspector(actorId:string){return inspectors.find(a=>a.id===actorId)??{...inspectors[0],id:actorId,name:layout.districts.some(d=>d.name===actorId)?actorId:'Local business',type:layout.districts.some(d=>d.name===actorId)?'District':'Business'};}
export function getCityLayout():CityLayout{return layout as CityLayout;}
export function getFork(){return fork;}
export function getNetwork(){return network;}
export function getPayment(actorId:string){return actorId===payment.actorId?payment:null;}
export function getCrisisOptions(){return crisis;}
