// Build-time layout generation only. CityCanvas reads the committed JSON fixture.
import type {Building, CityLayout, Landmark, ScenePath, ScenePoint, Tree} from '../data/types';
import {cityTemplate} from '../data/cityTemplates';
import {onLand, project, pointInPolygon, COAST, smoothPath} from './cityGeometry';
export function hashLayout(layout: Omit<CityLayout,'layoutHash'> | CityLayout) {
  const {layoutHash: _ignored, ...content} = layout as CityLayout;
  const text=JSON.stringify(content);let h=2166136261;
  for(let i=0;i<text.length;i++){h^=text.charCodeAt(i);h=Math.imul(h,16777619);}
  return 'sf-'+(h>>>0).toString(16).padStart(8,'0');
}
export function generateCityLayout(layoutSeed=4242, actors:{id:string;district:string}[]=[]):CityLayout {
  let seed=layoutSeed>>>0;const random=()=>{seed+=0x6D2B79F5;let t=seed;t=Math.imul(t^(t>>>15),t|1);t^=t+Math.imul(t^(t>>>7),t|61);return ((t^(t>>>14))>>>0)/4294967296;};
  const districts=[{name:'Financial District',x:14,y:6},{name:'SoMa',x:11,y:11},{name:'Mission District',x:7,y:11},{name:'Chinatown',x:10,y:7},{name:'Hayes Valley',x:5,y:14},{name:'Marina',x:0,y:11},{name:'Richmond',x:8,y:20},{name:'Sunset',x:13,y:19},{name:'Castro',x:10,y:15}];
  const districtAt=(x:number,y:number)=>districts.reduce((a,b)=>Math.hypot(x-a.x,y-a.y)<Math.hypot(x-b.x,y-b.y)?a:b).name;
  const actorList=actors.length?actors:Array.from({length:240},(_,i)=>({id:i===14?'cafe-14':i<4?'bank-'+(i+1):'firm-'+i,district:cityTemplate.districts[i%9]}));
  const buildings:Building[]=[];
  const special:Building[]=[
    {id:'bank-1',x:12.55,y:8.55,w:.78,d:.78,h:61,color:'#c7ceca',district:'Financial District',kind:'bank',name:'Bank 1'},
    {id:'bank-2',x:8.55,y:10.55,w:.8,d:.78,h:54,color:'#bdc5bc',district:'SoMa',kind:'bank',name:'Bank 2'},
    {id:'bank-3',x:14.55,y:6.55,w:.78,d:.8,h:72,color:'#b7c6cb',district:'Financial District',kind:'bank',name:'Bank 3'},
    {id:'bank-4',x:16.55,y:8.55,w:.78,d:.78,h:58,color:'#d8cbbb',district:'Financial District',kind:'bank',name:'Bank 4'},
    {id:'cafe-14',x:6.55,y:10.55,w:.82,d:.8,h:24,color:'#e4c5b0',district:'Mission District',kind:'shop',name:'Café 14',awning:'#c98f7e'},
  ];
  const reserved=(x:number,y:number)=>special.some(b=>Math.abs(x-b.x)<1.1&&Math.abs(y-b.y)<1.1)||x<3.8&&y>8&&y<14.5||x>4&&x<15&&y>17||x>18.4&&y>4.8&&y<10.5;
  let actorIndex=0;
  for(let y=1;y<20;y+=2)for(let x=1;x<21;x+=2)for(let kit=0;kit<2;kit++){
    const bx=x-.58+kit*.84,by=y-.42;
    if(!onLand(bx+.3,by+.4)||reserved(bx,by))continue;
    while(actorIndex<actorList.length&&special.some(s=>s.id===actorList[actorIndex].id))actorIndex++;
    if(actorIndex>=actorList.length)break;
    const actor=actorList[actorIndex++],district=districtAt(bx,by);const downtown=bx>11&&by<10;const shop=!downtown&&(district==='Mission District'||district==='Hayes Valley'||actorIndex%6===0);
    buildings.push({id:actor.id,x:bx,y:by,w:.59,d:.88,h:downtown?45+random()*100:15+random()*15,color:cityTemplate.palette[Math.floor(random()*6)],district,kind:downtown?'tower':shop?'shop':'house',name:downtown?'Downtown business '+actor.id.replace('firm-',''):shop?'Neighbourhood shop '+actor.id.replace('firm-',''):'Pastel row house',kit:Math.floor(random()*5),elevation:!downtown?Math.max(0,Math.sin(bx*.55+by*.23))*9:0,...(shop?{awning:['#b98c7c','#9daf9b','#c9b982','#92b1bd'][actorIndex%4]}:{})});
  }
  buildings.push(...special,
    {id:'pyramid',x:12.65,y:4.6,w:.9,d:.9,h:145,color:'#eee6d9',district:'Financial District',kind:'pyramid',name:'Transamerica Pyramid'},
    {id:'salesforce',x:14.65,y:4.6,w:1.05,d:1.05,h:248,color:'#abc2c9',district:'Financial District',kind:'salesforce',name:'Salesforce Tower'},
    {id:'coit',x:8.65,y:3.1,w:.6,d:.6,h:94,color:'#ece3cc',district:'Marina',kind:'coit',name:'Coit Tower'},
    {id:'ferry',x:20.9,y:5.4,w:1.1,d:4.3,h:32,color:'#dfd7c8',district:'Financial District',kind:'ferry',name:'Ferry Building'},
  );
  buildings.sort((a,b)=>(a.x+a.y)-(b.x+b.y));
  const landmarks:Landmark[]=[
    {id:'golden-gate-bridge',name:'Golden Gate Bridge',kind:'bridge',district:'Marina',x:667,y:280,bounds:{x:380,y:135,width:610,height:240}},
    ...buildings.filter(b=>['pyramid','salesforce','ferry','coit'].includes(b.kind)).map(b=>{const p=project(b.x,b.y);return {id:b.id,name:b.name,kind:b.kind as Landmark['kind'],district:b.district,x:p[0],y:p[1]-b.h/2,bounds:{x:p[0]-20,y:p[1]-b.h-65,width:65,height:b.h+85}};}),
    {id:'alcatraz',name:'Alcatraz',kind:'alcatraz',district:'Marina',x:1070,y:307,bounds:{x:988,y:256,width:165,height:91}},
    {id:'palace-of-fine-arts',name:'Palace of Fine Arts',kind:'palace',district:'Marina',x:340,y:382,bounds:{x:213,y:228,width:262,height:252}},
    {id:'golden-gate-park',name:'Golden Gate Park',kind:'park',district:'Richmond',x:363,y:671,bounds:{x:148,y:530,width:500,height:265}},
  ];
  const paths:ScenePath[]=[];let pathId=0;
  // Clip each road/sidewalk to the same land polygon used by the miniature.
  for(let n=0;n<=20;n+=2)for(let axis=0;axis<2;axis++)for(const lane of [0,-.26,.26]){
    let segment:ScenePoint[]=[];
    const flush=()=>{if(segment.length>2){const mid=segment[Math.floor(segment.length/2)];const gx=(mid[0]-700)/64+(mid[1]-195)/32,gy=(mid[1]-195)/32-(mid[0]-700)/64;paths.push({id:'path-'+pathId++,kind:lane===0?'road':'footpath',district:districtAt(gx,gy),points:segment,width:lane===0?(n%4===0?10:7):5});}segment=[];};
    for(let t=0;t<=23;t+=.25){const x=axis?n+lane:t,y=axis?t:n+lane;const inReservedPark=x>4&&x<15&&y>17;const palaceReserve=x<3.7&&y>8.4&&y<14.5;if(onLand(x,y)&&!inReservedPark&&!palaceReserve)segment.push(project(x,y));else flush();}flush();
  }
  const lakes=[{x:340,y:424,rx:101,ry:42,rotation:0},{x:266,y:619,rx:43,ry:20,rotation:.3},{x:398,y:690,rx:55,ry:23,rotation:.3},{x:490,y:738,rx:34,ry:16,rotation:.3}];
  // Template paths follow the shoreline, with room for the entire painted footpath.
  const lakeNorm=(p:ScenePoint,l:typeof lakes[number],margin=0)=>{const dx=p[0]-l.x,dy=p[1]-l.y,c=Math.cos(l.rotation),s=Math.sin(l.rotation);return ((dx*c+dy*s)/(l.rx+margin))**2+((-dx*s+dy*c)/(l.ry+margin))**2;};
  const shorePoint=(p:ScenePoint):ScenePoint=>{let result:ScenePoint=[...p];for(const l of lakes){if(lakeNorm(result,l,8)>=1)continue;const dx=result[0]-l.x,dy=result[1]-l.y,c=Math.cos(l.rotation),s=Math.sin(l.rotation);let u=(dx*c+dy*s)/(l.rx+8),v=(-dx*s+dy*c)/(l.ry+8),n=Math.hypot(u,v);if(n<.0001){u=0;v=-1;n=1;}u=u/n*(l.rx+8);v=v/n*(l.ry+8);result=[l.x+u*c-v*s,l.y+u*s+v*c];}return result;};
  const dryPath=(input:ScenePoint[])=>{let points=input.map(shorePoint);for(let pass=0;pass<6;pass++){let changed=false;const next:ScenePoint[]=[points[0]];for(let i=1;i<points.length;i++){const a=points[i-1],b=points[i],m:ScenePoint=[(a[0]+b[0])/2,(a[1]+b[1])/2];if(lakes.some(l=>lakeNorm(m,l,4)<1)){next.push(shorePoint(m));changed=true;}next.push(b);}points=next;if(!changed)break;}return points;};
  const parkPaths:ScenePoint[][]=[[[190,620],[260,592],[330,610],[360,650],[464,645],[480,690],[545,715],[577,747]],[[191,646],[265,684],[332,695],[390,729],[470,754]],[[270,585],[326,585],[328,645],[276,669],[332,695],[363,746]],[[430,624],[471,649],[468,691],[450,723],[450,766],[470,780]],[[221,658],[281,642],[350,650],[414,650],[478,668]],[[225,405],[222,430],[240,457],[280,476],[340,484],[399,476],[440,456],[457,430],[453,407]],[[210,417],[201,380],[220,346],[252,325],[283,315]],[[400,334],[434,350],[461,381],[470,420],[464,454],[427,482]]];
  parkPaths.forEach((points,i)=>paths.push({id:'park-path-'+i,kind:'park',district:i<5?'Richmond':'Marina',points:dryPath(smoothPath(points)),width:i<5?8:7}));
  // Shop approaches are part of the footpath graph, including the queue apron.
  for(const b of buildings.filter(b=>b.kind==='shop'))paths.push({id:'approach-'+b.id,kind:'footpath',district:b.district,points:[project(b.x+b.w/2,b.y+b.d+.05),project(b.x+b.w/2,Math.floor(b.y/2)*2+1.74),project(Math.floor(b.x/2)*2+1.74,Math.floor(b.y/2)*2+1.74)],width:4});
  const trees:Tree[]=[];
  for(let i=0;i<330;i++){
    const park=i<150,x=park?150+random()*490:150+random()*1120,y=park?540+random()*230:285+random()*535;
    const gx=(x-700)/64+(y-195)/32,gy=(y-195)/32-(x-700)/64;
    const inPark=pointInPolygon(x,y,[[148,610],[285,536],[652,725],[481,801]]);
    if(!pointInPolygon(gx,gy,COAST)||((x-720)/650)**2+((y-530)/320)**2>.91||park&&!inPark)continue;
    if(buildings.some(b=>{const p=project(b.x,b.y);return Math.abs(x-p[0])<22&&Math.abs(y-p[1])<15;})||Math.hypot((x-340)/1.5,y-418)<75)continue;
    if(lakes.some(l=>lakeNorm([x,y],l,8)<1))continue;
    trees.push({x,y,size:5+random()*5,shade:Math.floor(random()*4),kind:Math.floor(random()*3)});
  }
  // A planted promenade makes the Marina read as a garden even at overview scale.
  for(let i=0;i<28;i++){const a=i/28*Math.PI*2;trees.push({x:340+Math.cos(a)*123,y:409+Math.sin(a)*65,size:6+random()*3,shade:i%4,kind:i%3});}
  // Clustered woodland covers the park while preserving the exact baked walking graph.
  const parkRoutes=paths.filter(p=>p.kind==='park'&&p.district==='Richmond');
  const distanceToSegment=(x:number,y:number,a:ScenePoint,b:ScenePoint)=>{const dx=b[0]-a[0],dy=b[1]-a[1],t=Math.max(0,Math.min(1,((x-a[0])*dx+(y-a[1])*dy)/(dx*dx+dy*dy||1)));return Math.hypot(x-a[0]-t*dx,y-a[1]-t*dy);};
  for(let v=0;v<21;v++)for(let u=0;u<7;u++)for(let k=0;k<6;k++){
    const along=(v+.3+random()*.4)/21,across=(u+.2+random()*.6)/7;
    const x=148+137*across+367*along+(k-2.5)*3.5,y=610-74*across+189*along;
    if(lakes.some(l=>lakeNorm([x,y],l,10)<1)||parkRoutes.some(p=>p.points.some((a,i)=>i>0&&distanceToSegment(x,y,p.points[i-1],a)<7)))continue;
    if(Math.hypot(x-230,y-642)<25)continue;
    trees.push({x,y,size:5.5+random()*4.5,shade:Math.floor(random()*4),kind:random()<.22?1:0});
  }
  for(const road of paths.filter(p=>p.kind==='road'))for(const t of [.16,.35,.55,.75,.9]){
    const index=Math.min(road.points.length-2,Math.floor(t*(road.points.length-1))),a=road.points[index],b=road.points[index+1],length=Math.hypot(b[0]-a[0],b[1]-a[1])||1;
    const side=index%2?1:-1,x=a[0]-(b[1]-a[1])/length*15*side,y=a[1]+(b[0]-a[0])/length*15*side;
    const gx=(x-700)/64+(y-195)/32,gy=(y-195)/32-(x-700)/64;
    if(!onLand(gx,gy)||lakes.some(l=>lakeNorm([x,y],l,9)<1)||x<500&&y<495||pointInPolygon(x,y,[[148,610],[285,536],[652,725],[481,801]]))continue;
    if(buildings.some(b=>{const p=project(b.x+b.w/2,b.y+b.d/2);return Math.abs(x-p[0])<25&&Math.abs(y-p[1])<19;}))continue;
    trees.push({x,y,size:4.2+random()*1.8,shade:Math.floor(random()*3),kind:0});
  }
  const layout:CityLayout={layoutSeed,simulationSeed:42,layoutHash:'',version:2,districts,buildings,roads:Array.from({length:11},(_,i)=>i*2),water:{name:'San Francisco Bay',lakes},parks:[{x:6,y:18,w:7,d:4,name:'Golden Gate Park',district:'Richmond'},{x:-1,y:10,w:4,d:4,name:'Palace gardens',district:'Marina'}],landmarks,paths,trees,boats:[{x:1273,y:667,angle:.2,sail:true},{x:1195,y:732,angle:-.2,sail:true},{x:1095,y:790,angle:0,sail:true},{x:1040,y:810,angle:.2,sail:false}],piers:[{x:1198,y:650,length:55},{x:1138,y:680,length:55},{x:1078,y:710,length:55},{x:1018,y:740,length:55}]};
  layout.layoutHash=hashLayout(layout);return layout;
}
