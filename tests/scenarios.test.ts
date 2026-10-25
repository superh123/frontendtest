import {describe,it,expect} from 'vitest';
import {parseScenario} from '../apps/web/src/sim/scenarios';
describe('scenario parser',()=>{
 it.each([
 ['How will heightened interest rates affect demand and supply in San Francisco?','interest_rate','up',2,24],
 ['What happens if rents rise 20% for a year?','rent','up',20,12],
 ['What if interest rates fall 1.5 percentage points?','interest_rate','down',1.5,24],
 ] as const)('parses %s',(promptText,shockType,direction,magnitude,durationMonths)=>expect(parseScenario(promptText)).toEqual({shockType,direction,magnitude,durationMonths,targetSector:null,promptText}));
 it.each([['mortgage','interest_rate'],['landlord','rent'],['salary','wages'],['loan','credit'],['tax','tax'],['inflation','prices']] as const)('maps %s',(word,type)=>expect(parseScenario(word).shockType).toBe(type));
 it('uses documented missing-number defaults',()=>{expect(parseScenario('rent').magnitude).toBe(20);expect(parseScenario('interest').magnitude).toBe(2);expect(parseScenario('unknown')).toMatchObject({shockType:'interest_rate',direction:'up',durationMonths:24});});
 it('keeps the prompt verbatim and maps a target sector',()=>expect(parseScenario('  Credit down for cafes  ')).toMatchObject({targetSector:'hospitality',promptText:'  Credit down for cafes  '}));
 it('clamps duration',()=>expect(parseScenario('rents up 20% for 100 months').durationMonths).toBe(60));
});
