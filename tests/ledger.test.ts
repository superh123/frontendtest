import {it,expect} from 'vitest';
import {getInspector,getPayment} from '../apps/web/src/data/fixtures';
it('recorded ledger IDs are unique and payment has a matching future obligation',()=>{const entries=['cafe-14','bank-2','household-1'].flatMap(id=>getInspector(id).ledgerEntries);expect(new Set(entries.map(e=>e.eventId+'|'+e.fromId+'|'+e.toId+'|'+e.kind)).size).toBe(entries.length);for(const e of entries){expect(e.amount).toBeGreaterThan(0);expect(e.fromId).not.toBe(e.toId);}const p=getPayment('cafe-14')!;expect(p.settlement.amount).toBe(p.futureObligation.amount);});
