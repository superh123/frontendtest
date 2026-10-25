import {chromium,expect} from '@playwright/test';
import fs from 'node:fs';
fs.mkdirSync('artifacts/city-detail',{recursive:true});
const browser=await chromium.launch({channel:'chrome',headless:true,args:['--enable-unsafe-swiftshader']});
const page=await browser.newPage({viewport:{width:1512,height:982},deviceScaleFactor:1});
const layout=JSON.parse(fs.readFileSync('apps/web/src/data/fixtures/sfCityLayout.json','utf8'));const identityChecks=[];
const errors=[];page.on('pageerror',e=>errors.push(e.message));
await page.route('**/*',r=>/^https?:/.test(r.request().url())&&!r.request().url().startsWith('http://127.0.0.1:5173')?r.abort():r.continue());
const canvas=page.locator('.city-scene canvas'),button=name=>page.getByRole('button',{name,exact:true}),wait=()=>page.waitForTimeout(600);
async function focus(x,y,zoom){
 if(await button('Back to whole city').count()){await button('Back to whole city').click();await wait();}
 const box=await canvas.boundingBox();
 if(x===340){await button('Palace of Fine Arts').click();await wait();}
 else {const p=await canvas.evaluate(c=>({x:+c.dataset.cameraX,y:+c.dataset.cameraY,z:+c.dataset.cameraZoom,s:+c.dataset.baseScale}));const wx=x===710?700:x,wy=x===710?289:y;await page.mouse.dblclick(box.x+box.width/2+(wx-p.x)*p.z*p.s,box.y+box.height/2+(wy-p.y)*p.z*p.s);await wait();}
 const current=+(await canvas.getAttribute('data-camera-zoom'));await page.mouse.move(box.x+box.width/2,box.y+box.height/2);await page.mouse.wheel(0,-Math.log(zoom/current)/.0018);await wait();
 // Short gestures stay inside the canvas and avoid toolbar overlays at its edges.
 for(let i=0;i<12;i++){
  const p=await canvas.evaluate(c=>({x:+c.dataset.cameraX,y:+c.dataset.cameraY,z:+c.dataset.cameraZoom,s:+c.dataset.baseScale}));
  const dx=Math.max(-box.width*.18,Math.min(box.width*.18,(p.x-x)*p.z*p.s)),dy=Math.max(-box.height*.18,Math.min(box.height*.18,(p.y-y)*p.z*p.s));
  if(Math.abs(p.x-x)+Math.abs(p.y-y)<.5)break;
  await page.mouse.move(box.x+box.width/2,box.y+box.height/2);await page.mouse.down();await page.mouse.move(box.x+box.width/2+dx,box.y+box.height/2+dy,{steps:8});await page.mouse.up();await wait();
 }
 await page.mouse.move(30,70);await wait();const p=await canvas.evaluate(c=>({x:+c.dataset.cameraX,y:+c.dataset.cameraY}));expect(Math.hypot(p.x-x,p.y-y)).toBeLessThan(2);
}

try{
 await page.goto('http://127.0.0.1:5173');await page.getByRole('button',{name:'Start in the United States',exact:false}).click();await page.getByRole('button',{name:'San Francisco',exact:false}).click();await button('Explore this question').click();await button('Run this scenario').click();await expect(canvas).toHaveAttribute('data-lod','0');await wait();
 const initial=await canvas.getAttribute('data-mount-id');
 for(const landmark of layout.landmarks){
  if(await button('Back to whole city').count()){await button('Back to whole city').click();await wait();}
  if(await button('Back to live events').count())await button('Back to live events').click();
  const b=layout.buildings.find(b=>b.id===landmark.id);const world=b?[700+(b.x+b.w/2-b.y-b.d/2)*32,195+(b.x+b.w/2+b.y+b.d/2)*16-b.h*.55]:landmark.kind==='palace'?[340,288]:landmark.kind==='park'?[230,630]:landmark.kind==='bridge'?[700,289]:[landmark.x,landmark.y];
  const r=await canvas.boundingBox(),p=await canvas.evaluate(c=>({x:+c.dataset.cameraX,y:+c.dataset.cameraY,z:+c.dataset.cameraZoom,s:+c.dataset.baseScale}));const sx=r.x+r.width/2+(world[0]-p.x)*p.z*p.s,sy=r.y+r.height/2+(world[1]-p.y)*p.z*p.s;
  console.log('TARGET',landmark.name,sx,sy,p);await page.mouse.move(sx,sy);await page.waitForTimeout(350);await expect(page.locator('.landmark-tooltip')).toContainText(landmark.name);await page.mouse.click(sx,sy);await wait();console.log('AFTER',await canvas.getAttribute('data-camera-zoom'),await page.locator('.inspector h2').allTextContents());await expect(page.locator('.inspector h2')).toHaveText(landmark.district);await expect(page.locator('.district-landmark-name')).toHaveText(landmark.name);expect(await canvas.getAttribute('data-mount-id')).toBe(initial);identityChecks.push(landmark.name);console.log('PASS hover and district inspector:',landmark.name);
  if(landmark.kind==='alcatraz'){await page.mouse.move(30,70);await page.screenshot({path:'artifacts/city-detail/11-alcatraz-district.png',animations:'disabled'});}
 }

 for(const [file,x,y,z,lod]of [['08-bridge-district',710,273,2.1,'1'],['09-palace-street',340,345,3.6,'2'],['10-east-waterfront',1130,650,2.55,'1'],['12-downtown-landmarks',1030,400,2.55,'1']]){
  await focus(x,y,z);await expect(canvas).toHaveAttribute('data-lod',lod);expect(await canvas.getAttribute('data-mount-id')).toBe(initial);await page.screenshot({path:`artifacts/city-detail/${file}.png`,animations:'disabled'});console.log('CAPTURE',file);
 }
 expect(errors).toEqual([]);console.log('PASS landmark close-ups, same canvas and no runtime errors');
}catch(e){await page.screenshot({path:'artifacts/city-detail/landmark-qa-failure.png'});throw e;}finally{fs.writeFileSync('artifacts/city-detail/landmark-qa-report.json',JSON.stringify({identityChecks,errors},null,2));await browser.close();}
