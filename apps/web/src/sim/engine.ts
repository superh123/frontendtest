// Backend contract only. No economy engine is implemented in this frontend.
import type {Household,Firm,Bank,LedgerEntry} from './agents';
import type {Scenario} from '../data/types';
export type World={tick:number;layoutSeed:number;simulationSeed:number;households:Household[];firms:Firm[];banks:Bank[];government:{cash:number;budget:number};ledger:LedgerEntry[];scenario:Scenario|null};
export declare function tick(world:World):World;
