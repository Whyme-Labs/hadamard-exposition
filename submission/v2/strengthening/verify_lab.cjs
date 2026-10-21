'use strict';
const fs = require('fs');
const vm = require('vm');
const assert = require('assert/strict');
const htmlPath = process.argv[2];
if (!htmlPath) throw new Error('Pass the actual standalone article path');
const html = fs.readFileSync(htmlPath, 'utf8');
const matches = [...html.matchAll(/<script id="family-calculator">([\s\S]*?)<\/script>/g)];
assert.equal(matches.length, 1);
const elements = Object.fromEntries(['family-bits','family-n','family-signs','family-fraction','family-error','family-peak','family-ratio'].map(id => [id, {value: id==='family-n'?'4':id==='family-bits'?'4':'0', textContent:'', handlers:{}, addEventListener(k,f){ this.handlers[k]=f; }}]));
const context = {module:{exports:{}}, document:{getElementById(id){ assert.ok(elements[id]); return elements[id]; }}};
vm.runInNewContext(matches[0][1],context,{timeout:1000});
assert.equal(elements['family-fraction'].textContent,'11/3332');
const {calculate,roundEven}=context.module.exports;
assert.equal(roundEven(5n,2n),2n); assert.equal(roundEven(7n,2n),4n);
assert.equal(roundEven(-5n,2n),-2n); assert.equal(roundEven(-7n,2n),-4n);
const evidence = JSON.parse(fs.readFileSync(require('path').join(__dirname,'../family-checks.json'),'utf8'));
let checks=0;
for (const e of evidence.examples) {
 for(let mask=0;mask<8;mask++) {
  const observed=calculate(e.bits,e.n,mask);
  assert.equal(observed.fraction,e.relative_squared_error);
  assert.ok(observed.errorPercent>0 && observed.peakRatio<1); checks++;
 }
}
for (const [id,val] of [['family-bits','5'],['family-n','1024'],['family-signs','7']]) {
 elements[id].value=val; elements[id].handlers.change();
}
assert.equal(elements['family-fraction'].textContent,calculate(5,1024,7).fraction);
for(const args of [[2,4,0],[4,12,0],[4,4,8],[4,8192,0]]) assert.throws(()=>calculate(...args));
console.log(JSON.stringify({status:'passed',actual_bundled_javascript_executed:true,exact_python_witness_matches:checks,change_events_checked:true,rounding_ties_checked:true},null,2));
