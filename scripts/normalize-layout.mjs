import fs from 'node:fs';
const file='apps/web/src/data/fixtures/sfCityLayout.json';const l=JSON.parse(fs.readFileSync(file,'utf8'));
const coast=[[0,9],[3,9],[4,7],[6,8],[8,6],[8,3],[10,2],[11,-3],[22,-2],[22,18],[-4,19],[-4,12]];
function inside(x,y){let hit=false;for(let i=0,j=coast.length-1;i<coast.length;j=i++){const a=coast[i],b=coast[j];if((a[1]>y)!==(b[1]>y)&&x<(b[0]-a[0])*(y-a[1])/(b[1]-a[1])+a[0])hit=!hit;}return hit;}
for(const b of l.buildings){if(b.id==='cafe-14'){b.x=7;b.y=10;b.district='Mission District';b.kind='house';b.h=18;}if(b.id==='coit'){b.x=11;b.y=1;}}
l.buildings=l.buildings.filter(b=>['cafe-14','coit'].includes(b.id)||inside(b.x+b.w/2,b.y+b.d/2)).sort((a,b)=>(a.x+a.y)-(b.x+b.y));
fs.writeFileSync(file,JSON.stringify(l));console.log('Shoreline-conforming buildings',l.buildings.length);
