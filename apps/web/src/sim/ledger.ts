// Backend type signature only. No settlement or validation engine in the UI.
import type {LedgerEntry} from './agents';
export declare function validateLedger(entries:LedgerEntry[]):{balanced:boolean;duplicateSettlementCount:number;errors:string[]};
