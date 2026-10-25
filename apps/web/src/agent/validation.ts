// Frontend validation of proposal shape only. Settlement remains the backend's job.
export function validateProposal(p:Record<string,unknown>,budget:number,actorIds:string[]=[]){
 const errors:string[]=[];const policy=['rent_relief','wage_subsidy','credit_support','tax_relief','transfer_boost'];const contract=['extend_payment_terms','restructure_loan','supplier_credit','rent_deferral'];
 if(!policy.includes(String(p.type))&&!contract.includes(String(p.type)))errors.push('Unknown proposal type');
 if(policy.includes(String(p.type))){if(typeof p.magnitude!=='number'||p.magnitude<0||p.magnitude>50)errors.push('Magnitude must be 0–50');if(typeof p.estimatedCost!=='number'||p.estimatedCost>budget)errors.push('Government budget exceeded');if(typeof p.durationMonths!=='number'||p.durationMonths<1||p.durationMonths>24)errors.push('Duration must be 1–24 months');}
 if(contract.includes(String(p.type))){if(!actorIds.includes(String(p.fromId))||!actorIds.includes(String(p.toId)))errors.push('Counterparty does not exist');}
 return errors;
}
