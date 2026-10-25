import {it,expect} from 'vitest';
import {getCityLayout,getSnapshot} from '../apps/web/src/data/fixtures';
it('replays serialized layout and state identically',()=>{const hash=JSON.stringify({layout:getCityLayout(),snapshot:getSnapshot(24,'shock')});expect(JSON.stringify({layout:getCityLayout(),snapshot:getSnapshot(24,'shock')})).toBe(hash);});
