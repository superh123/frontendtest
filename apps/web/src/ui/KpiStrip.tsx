import {getSnapshot} from '../data/fixtures';
import {useStore} from '../state/store';
type Row={label:string;value:string;diff:number;good:boolean;unit:'points'|'firms'|'cash'};
export default function KpiStrip(){
 const {tick,branch}=useStore();const s=getSnapshot(tick,branch).kpis,p=getSnapshot(Math.max(0,tick-1),branch).kpis;
 const rows:Row[]=[
 {label:'Employment',value:`${s.employment.toFixed(1)}%`,diff:s.employment-p.employment,good:true,unit:'points'},
 {label:'Household Cash',value:`$${(s.householdCash/1e6).toFixed(2)}m`,diff:s.householdCash-p.householdCash,good:true,unit:'cash'},
 {label:'Business Defaults',value:String(s.businessDefaults),diff:s.businessDefaults-p.businessDefaults,good:false,unit:'firms'},
 {label:'Bank Stress',value:`${s.bankStress}%`,diff:s.bankStress-p.bankStress,good:false,unit:'points'},
 {label:'Public Intervention Cost',value:s.publicInterventionCost?'$'+(s.publicInterventionCost/1e6).toFixed(2)+'m':'$0',diff:s.publicInterventionCost-p.publicInterventionCost,good:false,unit:'cash'}
 ];
 return <div className="kpi-strip">{rows.map(r=>{const change=r.unit==='cash'?`$${(Math.abs(r.diff)/1000).toFixed(0)}k`:r.unit==='firms'?`${Math.abs(r.diff)} firms`:`${Math.abs(r.diff).toFixed(1)} points`;const good=(r.diff>0)===r.good;return <div className="kpi" key={r.label}><span>{r.label}</span><strong>{r.value}</strong><small className={!r.diff?'neutral':good?'positive':'negative'}>{!r.diff?'— stable':`${r.diff>0?'▲':'▼'} ${change} ${r.diff>0?'up':'down'}`} <em>· M{tick}</em></small></div>;})}</div>;
}
