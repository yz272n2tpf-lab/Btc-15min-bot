'use strict';
// Deterministic demo tape for UI review only. NEVER strategy evidence.
const DEMO=[
 {t:0,state:'PASS',text:'No qualified edge — wait',up:.51,ask:.49,flip:34},
 {t:8,state:'EARLY',text:'EARLY UP qualified · entry 34¢',up:.64,ask:.34,flip:25},
 {t:16,state:'SCALP',text:'SCALP UP · buy 31¢ → target 45¢',up:.67,ask:.31,flip:22},
 {t:24,state:'UP',text:'FINAL UP qualified · Strong',up:.91,ask:.63,flip:12},
 {t:32,state:'5M_CAUTION',text:'5M CAUTION · stronger evidence required',up:.89,ask:.78,flip:16},
 {t:40,state:'3M_GUARD',text:'3M GUARD · no new marginal entry',up:.87,ask:.84,flip:20},
 {t:48,state:'LOCK_PROFIT',text:'LOCK PROFIT · protect 80–90% zone',up:.94,ask:.90,flip:8},
 {t:56,state:'DATA_STALE',text:'DATA STALE · DO NOT USE',up:null,ask:null,flip:null},
 {t:64,state:'PASS',text:'Fresh next contract · PASS',up:.52,ask:.50,flip:31},
 {t:72,state:'DOWN',text:'FINAL DOWN qualified · Strong',up:.18,ask:.27,flip:11},
 {t:80,state:'REVERSAL',text:'REVERSAL DOWN · buy 33¢ → target 48¢',up:.39,ask:.33,flip:28},
 {t:88,state:'5M_CAUTION',text:'5M CAUTION · watch flip risk',up:.31,ask:.58,flip:36},
 {t:96,state:'3M_GUARD',text:'3M GUARD · no new marginal entry',up:.24,ask:.73,flip:21},
 {t:104,state:'LOCK_PROFIT',text:'LOCK PROFIT · protect DOWN gains',up:.08,ask:.88,flip:7}
];
function demoAt(seconds){let x=DEMO[0];for(const r of DEMO)if(seconds>=r.t)x=r;return Object.freeze({...x});}
if(typeof module!=='undefined')module.exports={DEMO,demoAt};
