import {it,expect} from 'vitest';
import {validateProposal} from '../apps/web/src/agent/validation';
import {getProposal} from '../apps/web/src/data/fixtures';
const p=getProposal().proposal;
it('rejects magnitude 99',()=>expect(validateProposal({...p,magnitude:99},2e6)).toContain('Magnitude must be 0–50'));
it('rejects unknown types',()=>expect(validateProposal({...p,type:'print_money'},2e6)).toContain('Unknown proposal type'));
it('rejects over-budget policies',()=>expect(validateProposal(p,1000)).toContain('Government budget exceeded'));
it('accepts a valid proposal shape',()=>expect(validateProposal(p,2e6)).toEqual([]));
it('rejects a nonexistent counterparty',()=>expect(validateProposal({type:'supplier_credit',fromId:'cafe-14',toId:'missing'},2e6,['cafe-14'])).toContain('Counterparty does not exist'));
