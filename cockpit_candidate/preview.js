/* Manual offline review. No polling, clock, signal engine, execution, or storage. */
(function(){
  'use strict';
  const samples=window.BTC15_REVIEW_SAMPLES||[];
  const selector=document.getElementById('scenario');
  samples.forEach((sample,index)=>{const option=document.createElement('option');option.value=String(index);option.textContent=sample.label;selector.append(option);});
  function show(index){
    const sample=samples[index];if(!sample)return;
    selector.value=String(index);window.BTC15Cockpit.render(sample);
    document.getElementById('scenario-description').textContent=sample.description;
  }
  selector.addEventListener('change',()=>show(Number(selector.value)));
  window.BTC15Review=Object.freeze({show,count:samples.length});
  show(4);
})();
