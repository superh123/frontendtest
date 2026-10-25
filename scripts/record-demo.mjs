import {chromium,expect} from '@playwright/test';
import fs from 'node:fs';
const browser=await chromium.launch({channel:'chrome',headless:true,args:['--enable-unsafe-swiftshader']});
const context=await browser.newContext({viewport:{width:1512,height:982},deviceScaleFactor:1,recordVideo:{dir:'artifacts/demo',size:{width:1512,height:982}}});
const page=await context.newPage(),errors=[];page.on('pageerror',e=>errors.push(e.message));const started=Date.now();const marks=[];
const mark=s=>{marks.push({seconds:Math.round((Date.now()-started)/1000),step:s});console.log(s);};
const at=async seconds=>{const remaining=seconds*1000-(Date.now()-started);if(remaining>0)await page.waitForTimeout(remaining);};
const click=(name,exact=true)=>page.getByRole('button',{name,exact}).click();
const shot=(name)=>page.screenshot({path:`artifacts/${name}.png`,timeout:60000});
try{
 await page.goto('http://127.0.0.1:5173');await page.waitForTimeout(3000);await shot('01-earth');mark('Earth in space');
 await at(10);await page.mouse.move(729,464);await at(16);await click('Start in the United States',false);await at(23);await shot('02-country');mark('United States selected, pins visible');
 await at(30);await click('San Francisco',false);await page.waitForTimeout(400);await shot('03-prompt');mark('San Francisco and scenario prompt');
 await at(43);await click('Explore this question');await at(53);await click('Run this scenario');await page.waitForTimeout(850);await shot('04-transition');await expect(page.getByRole('button',{name:'Create World'})).toBeVisible({timeout:15000});mark('Globe to miniature transition');
 await at(62);await click('Create World');await click('Play');await expect(page.locator('.month-label')).toContainText('06',{timeout:18000});await click('Pause');await shot('05-city');mark('Six baseline months, healthy city');
 await at(90);await click('Trigger Crisis',false);await at(99);await click('Apply bank shock');await at(105);await shot('06-crisis');mark('Bank 2 40% commercial loan asset shock');
 await page.getByRole('button').filter({hasText:'Café 14 cannot refinance'}).click();await at(116);await shot('08-inspector');mark('Café 14 cash, debt, obligations and missed payroll');
 await at(123);await click('Back to live events');await click('Test a rescue policy',false);await expect(page.getByText('Keep credit flowing.')).toBeVisible();await page.locator('.proposal summary').click();await shot('09-agent');await at(132);await click('Accept · new branch');mark('Inline Mock agent checks three sources; policy accepted');
 await at(138);await click('Fork Reality');await page.waitForTimeout(400);await shot('07-futures');mark('Three futures from the shared crisis snapshot');
 await at(150);await click('Back to city');await click('Network');await page.locator('.network-node').filter({hasText:'Bank 2'}).click();await shot('10-network');mark('Bank 2 counterparties in financial network');
 await at(159);await page.locator('.network-node').filter({hasText:'Café 14'}).click();await click('Agentic payment activity',false);await page.locator('.payment-steps').scrollIntoViewIfNeeded();await shot('08-inspector-payment');mark('Six payment steps and future supplier obligation');
 await at(170);await click('Back to live events');await click('Fork Reality');await page.locator('.branch-results').scrollIntoViewIfNeeded();mark('Final synchronized outcomes and tradeoffs');await at(181);
}catch(e){errors.push(String(e));throw e;}finally{const video=page.video();await context.close();const videoPath=await video.path();fs.copyFileSync(videoPath,'artifacts/economy-god-mode-demo.webm');fs.writeFileSync('artifacts/demo-report.json',JSON.stringify({durationSeconds:Math.round((Date.now()-started)/1000),marks,errors},null,2));await browser.close();}
