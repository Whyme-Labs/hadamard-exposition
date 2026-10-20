// Execute the actual bundled calculator without requiring a browser binary.
// This verifies calculations and event updates, not visual rendering.
const fs = require('node:fs');
const vm = require('node:vm');
const assert = require('node:assert/strict');
const path = require('node:path');
const args = process.argv.slice(2);
assert(args.every(arg => !arg.startsWith('--') || arg === '--write-report'), 'Unknown argument');
const paths = args.filter(arg => arg !== '--write-report');
assert(paths.length <= 1, 'Supply at most one HTML path');
const htmlPath = paths[0] || path.join(__dirname, 'exposition.html');
const html = fs.readFileSync(htmlPath, 'utf8');
const script = [...html.matchAll(/<script\b[^>]*>([\s\S]*?)<\/script>/g)].map(m=>m[1]).join('\n');
assert(script.includes('quantizer-lab'));
assert(!/<script[^>]+src=/i.test(html));
assert(!/<img[^>]+src="(?!data:)/i.test(html));
assert(!/<link[^>]+rel="stylesheet"/i.test(html));

class Element {
  constructor(value=''){this.value=value;this.innerHTML='';this.textContent='';this.events={};}
  setAttribute(){}
  addEventListener(name,handler){this.events[name]=handler;}
  querySelectorAll(selector){assert.equal(selector,'input');return [0,1,2,3].map(i=>elements[`lab-x-${i}`]);}
}
const elements = Object.fromEntries([
  'quantizer-lab','lab-example','lab-bits','lab-original','lab-rotated','lab-summary','lab-table','lab-scales',
  ...[0,1,2,3].map(i=>`lab-x-${i}`),
].map(id=>[id,new Element()]));
[7,1,1,0].forEach((v,i)=>elements[`lab-x-${i}`].value=String(v));
elements['lab-example'].value='counter';
elements['lab-bits'].value='4';
vm.runInNewContext(script,{document:{getElementById:id=>elements[id]},console});
const cases=[];
function capture(label){cases.push({case:label,original:elements['lab-original'].textContent,rotated:elements['lab-rotated'].textContent,summary:elements['lab-summary'].textContent});}
assert.equal(elements['lab-original'].textContent,'0.0000%');
assert.equal(elements['lab-rotated'].textContent,(1100/3332).toFixed(4)+'%');
capture('exact_rational_counterexample');
elements['lab-example'].events.change({target:{value:'help'}});
assert(parseFloat(elements['lab-rotated'].textContent)<parseFloat(elements['lab-original'].textContent));
capture('outlier_example');
elements['lab-example'].events.change({target:{value:'equal'}});
assert.equal(elements['lab-original'].textContent,'0.0000%');
assert.equal(elements['lab-rotated'].textContent,'0.0000%');
capture('equal_coordinates');
for(let i=0;i<4;i++) elements[`lab-x-${i}`].value='0';
elements['lab-x-0'].events.input();
assert.equal(elements['lab-original'].textContent,'Undefined');
assert.equal(elements['lab-rotated'].textContent,'Undefined');
capture('zero_vector');
elements['lab-example'].events.change({target:{value:'counter'}});
elements['lab-bits'].value='8';
elements['lab-bits'].events.change();
assert(Number.isFinite(parseFloat(elements['lab-rotated'].textContent)));
capture('bit_count_control');

const report={
  actual_bundled_javascript_executed:true,
  update_events_checked:true,
  exact_counterexample_matches_rational_result:true,
  all_assets_embedded:true,
  mathml_equations:(html.match(/<math\b/g)||[]).length,
  embedded_images:(html.match(/<img[^>]+src="data:/g)||[]).length,
  screenshot_verification:false,
  screenshot_limitation:'This check executes the bundled JavaScript with a DOM stub. It does not perform browser screenshot verification.',
  cases,
};
if (args.includes('--write-report')) {
  fs.writeFileSync(path.join(__dirname,'calculator-verification.json'),JSON.stringify(report,null,2)+'\n');
}
console.log(JSON.stringify(report,null,2));
