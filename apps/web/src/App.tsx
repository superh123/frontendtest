import {useEffect,useMemo} from 'react';
import {Orbit,ArrowLeft,ArrowUpRight,ArrowRight,MousePointer2,Move,Globe2,MapPin,ChevronRight} from 'lucide-react';
import Globe from './globe/Globe';
import CityCanvas from './city/CityCanvas';
import PromptPanel from './ui/PromptPanel';
import TopControls from './ui/TopControls';
import KpiStrip from './ui/KpiStrip';
import Timeline from './ui/Timeline';
import BranchCompare from './ui/BranchCompare';
import NetworkView from './ui/NetworkView';
import {useStore} from './state/store';
import cities from './data/cities.json';
export default function App(){const s=useStore();const hasPanel=['PIN_SELECTED','TRANSITION','CITY'].includes(s.stage);const city=s.stage==='CITY';const country=s.stage==='PIN_SELECTED'?s.country:s.hoverCountry||s.country;const us=/United States/.test(s.country);const stars=useMemo(()=>Array.from({length:2200},(_,i)=>({left:(((Math.sin(i*127.1+311.7)*43758.5453)%1+1)%1*100)+'%',top:(((Math.sin(i*269.5+183.3)*23421.631)%1+1)%1*100)+'%',opacity:.12+(i%9)/20,width:i%17===0?2:1,height:i%17===0?2:1})),[]);
 useEffect(()=>{if(s.stage!=='TRANSITION')return;const timer=setTimeout(()=>s.set({stage:'CITY',tick:0,maxTick:0}),2000);return()=>clearTimeout(timer);},[s.stage]);
 useEffect(()=>{if(!city||!s.playing)return;const timer=setInterval(()=>useStore.getState().advance(),1600/s.speed);return()=>clearInterval(timer);},[city,s.playing,s.speed]);
 useEffect(()=>{const key=(e:KeyboardEvent)=>{if((e.target as HTMLElement).matches('input,textarea,select'))return;if(e.key==='Escape'){if(s.selected)s.set({selected:null});else if(s.compare)s.set({compare:false});else s.back();}if(e.code==='Space'&&city){e.preventDefault();s.set({playing:!s.playing});}};addEventListener('keydown',key);return()=>removeEventListener('keydown',key);},[s.stage,s.selected,s.compare,s.playing]);
 return <div className={'app '+(city?'city-mode':'globe-mode')}><div className="starfield" aria-hidden="true">{stars.map((style,i)=><i key={i} style={style}/>)}</div><header className="app-header"><a className="brand" href="#" onClick={e=>{e.preventDefault();s.set({stage:'GLOBE',country:'',playing:false,compare:false,selected:null});}}><span className="brand-mark"><Orbit size={25} strokeWidth={1.3}/></span><span>economy<span className="brand-mode">GOD MODE</span></span></a><div className="header-right"><span className="offline-pill"><span className="tiny-dot"/> INTERACTIVE DEMO</span><span className="header-caption">A small world. A big what if.</span><button className="help-button" title="Select the USA, then San Francisco. Run a scenario, trigger a crisis and compare futures." onClick={()=>s.set({notice:s.notice?'':'Select United States → San Francisco → Explore this question → Run this scenario. Then Play, Trigger Crisis and Fork Reality.'})}>?</button></div></header><main className={'workspace '+(hasPanel?'with-panel':'')}><section className={'world-area '+(s.compare?'comparing':'')}>
 {!city&&<><div className="explore-heading">{s.stage!=='GLOBE'&&<button className="back-button" onClick={s.back}><ArrowLeft size={14}/> Back to {s.stage==='COUNTRY'?'world':'country'}</button>}<p className="eyebrow">{s.stage==='GLOBE'?'01 / A WORLD OF POSSIBILITIES':s.stage==='COUNTRY'?'02 / FIND YOUR CITY':'03 / ASK WHAT IF'}</p><h2>{s.stage==='GLOBE'?<>Every economy<br/>has a story.</>:s.stage==='COUNTRY'?'Choose a starting point.':'Change one thing.'}</h2><p>{s.stage==='GLOBE'?'Choose a place. Change the conditions. Follow the ripple.':s.stage==='COUNTRY'?'A world of connections. Start with San Francisco.':'Watch a whole city respond.'}</p></div><div className="country-label"><span className="eyebrow">{country?'EXPLORING':'YOUR WORLD, IN PERSPECTIVE'}</span><span>{country?.replace(' of America','')||'Earth'}</span></div></>}
 {city&&<><TopControls/><KpiStrip/></>}
 <div className={'visual-stage '+(s.stage==='TRANSITION'?'transitioning':'')}>
 {s.stage!=='CITY'&&<div className="globe-layer"><Globe/></div>}
 {(city||s.stage==='TRANSITION')&&<div className={'city-layer '+(city?'revealed':'')+(s.compare||s.mode==='network'?' hidden-visual':'')}><CityCanvas/></div>}
 {city&&s.mode==='network'&&!s.compare&&<NetworkView/>}
 {city&&s.compare&&<BranchCompare/>}
 </div>
 {!city&&s.stage!=='TRANSITION'&&<div className="globe-bottom">{s.stage==='GLOBE'?<><button className="explore-cta" onClick={()=>s.set({country:'United States of America',stage:'COUNTRY',notice:''})}><span className="tiny-dot"/> Start in the United States <ArrowUpRight size={16}/></button><div className="gesture-hints"><span><Move size={12}/> Drag to rotate</span><span><MousePointer2 size={12}/> Click to explore</span></div></>:us?<div className="city-picker"><div className="city-picker-title"><MapPin size={14}/><span>UNITED STATES</span><small>1 CITY AVAILABLE</small></div><div className="city-list">{cities.map(c=><button key={c.city} className={c.playable?'playable':''} onClick={()=>c.playable?s.set({stage:'PIN_SELECTED',notice:''}):s.set({notice:'Coming soon in this demo — only San Francisco is playable'})}><span className="city-pin-dot"/>{c.city}{c.playable?<ArrowUpRight size={12}/>:<small>soon</small>}</button>)}</div></div>:<div className="unavailable">Demo city not available yet — try United States → San Francisco</div>}</div>}
 {s.notice&&<div className="notice" role="status">{s.notice}<button aria-label="Dismiss notice" onClick={()=>s.set({notice:''})}>×</button></div>}
 {city&&!s.compare&&<Timeline/>}
 <footer className="world-footer"><span>{city?'SAN FRANCISCO · USA':'ECONOMY GOD MODE'}</span><span>{city?'Stylized simulation — not a forecast of a real city.':'A connected world, waiting for your next question.'}</span><span>{city?'LAYOUT 4242':'EST. 2026'} <span className="tiny-dot"/></span></footer>
 </section>{hasPanel&&<PromptPanel/>}</main></div>;
}
