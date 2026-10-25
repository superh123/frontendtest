// Backend type signature only. Frontend reads committed fixture branches.
import type {World} from './engine';
import type {Scenario} from '../data/types';
export declare function fork(world:World,scenario:Scenario):World;
