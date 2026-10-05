"""Production surface allowlist. Every dynamic field belongs to the V2 panel."""
import re


def complete_page(html):
    def card(css):
        found=re.findall(r'<article class="card '+css+r'"[^>]*>.*?</article>',html,re.S)
        if len(found)!=1:raise ValueError('PINNED_PRODUCT_CARD:'+css)
        return found[0]
    final,early,scalp=card('final-card'),card('early-card'),card('scalp-card')
    # Remove the permanently disconnected second legacy ladder in its entirety.
    scalp=scalp[:scalp.index('<div class="opposite-scalp">')]+'''<div class="opposite-scalp">
      <span id="oppositeArrow">—</span><strong id="oppositeTitle">SERIAL REVERSAL / RE-ENTRY</strong>
      <p id="oppositeEntry">Fresh same-contract setup required</p><span id="oppositeState">WAIT</span>
      </div></article>'''
    final=final.replace('Buy / Add zone','EARLY link').replace('Hold zone','FINAL support').replace('Watch zone','Change in support').replace('Exit now','Exit guidance')
    body='''<body><main class="app-shell">
    <header class="topbar"><div class="brand"><div class="btc-dot">₿</div><div><div class="brand-title">BTC 15-Minute</div>
    <div class="brand-sub">Kalshi · Signal only · Manual execution</div></div></div><div class="live-pill" id="liveStatus">UNAVAILABLE</div></header>
    <div class="current-contract-strip"><strong id="currentContract">IDENTITY UNAVAILABLE</strong></div>
    <section class="product-context" aria-label="Official contract and model context">
      <div>Official target <strong id="v2Target">Unavailable</strong></div>
      <div>Time remaining <strong id="v2Remaining">Unavailable</strong></div>
      <div>Contract closes <strong id="v2Close">Unavailable</strong></div>
      <div>Model flip risk <strong id="flipRisk">Unavailable</strong><div id="flipRiskSub">Fresh model inputs required</div></div>
      <p id="contextBanner">Native action inputs unavailable</p>
    </section>
    <section class="product-grid" aria-label="Current signal guidance">'''+final+early+scalp+'''</section>
    <p id="v2QuoteClock" role="status">Current executable quotes unavailable</p>
    <footer class="footer">SIGNAL ONLY · MANUAL EXECUTION ONLY · NO ORDERS</footer>
    </main><script src="/ladders/panel.js"></script></body>'''
    css='''<style id="v2-complete-product">
      .app-shell{width:100%;max-width:1600px;margin:0 auto;box-sizing:border-box}
      .product-context{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:12px;padding:14px 0;color:var(--muted,#aab4c8)}
      .product-context strong{display:block;color:var(--text,#eef4ff);font-size:1.1rem}
      #contextBanner{grid-column:1/-1;margin:0}
      .product-grid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:12px;align-items:start}
      .product-grid>*{min-width:0;grid-column:auto;grid-row:auto}
      .product-grid .early-card{margin:0}
      .product-grid .flow-list strong,.product-grid .pos strong{overflow-wrap:anywhere;min-width:0}
      .product-grid .early-head,.product-grid .scalp-active{flex-wrap:wrap;gap:8px}
      .product-grid .state-pill{max-width:100%;overflow-wrap:anywhere;white-space:normal}
      .product-grid .scalp-card{display:block}
      .product-grid .card-label{font-size:13px}
      .product-grid .ladder-row{font-size:12px;padding:7px 5px;gap:8px}
      .product-grid .ladder-row strong{font-size:13px}
      .product-grid .flow-list{font-size:13px}
      .product-grid .flow-status{font-size:12px;line-height:1.4;padding:9px}
      .product-grid .pos span,.product-grid .muted,.product-grid .action-sub,.product-grid .reason-line{font-size:12px;line-height:1.4}
      .product-grid .pos strong{font-size:14px;line-height:1.3}
      .product-grid .state-pill{font-size:12px}
      .product-grid .odds-grid{grid-template-columns:minmax(0,1fr)}
      .product-grid .odds strong{font-size:28px}
      .product-grid .opposite-scalp{margin-top:12px;font-size:13px;line-height:1.4}
      .product-grid .scalp-side strong{font-size:16px}
      .product-grid .scalp-side span{font-size:12px}
      .topbar .brand{flex-shrink:0}.topbar{flex-wrap:wrap;gap:12px}
      .current-contract-strip{font-size:11px;white-space:normal;overflow-wrap:anywhere}
      #v2QuoteClock{padding:10px 0;font-size:12px}
      .footer{font-size:11px}
      .app-shell .product-grid .trade-ladder .ladder-row>span{font-size:12px}
      .app-shell .product-grid .flow-list span,.app-shell .product-grid .flow-list strong{font-size:12px}
      .app-shell .product-grid .odds>span{font-size:11px}
      .app-shell .product-grid .section-title{font-size:12px}
      .app-shell .product-grid .confidence-label,.app-shell .product-grid .action-title{font-size:11px}
      .app-shell .current-contract-strip strong{font-size:11px}
      .app-shell .brand-sub{font-size:12px}
      @media(max-width:1100px){.product-grid{grid-template-columns:repeat(2,minmax(0,1fr))}.product-grid .scalp-card{grid-column:1/-1}}
      @media(max-width:700px){.product-grid,.product-context{grid-template-columns:minmax(0,1fr)}.product-grid .scalp-card{grid-column:auto}.topbar{flex-wrap:wrap;gap:12px}}
    </style>'''
    html=re.sub(r'<body>.*?</body>',lambda _:body,html,flags=re.S)
    return html.replace('</head>',css+'\n</head>')


SOURCES={
    'official_contract_target_and_timer':'/ladders or /ladders/quotes official_identity; conservative monotonic deadline',
    'final_early_flip_risk_context':'/ladders; native event authority; frozen-gate read-only confirmation lease <= original BRTI/BTC/quote limits; model numbers labelled native',
    'scalp_serial_reentry':'V8.1 /ladders; independent source expiry and same official identity',
    'executable_bid_ask_and_source_clock':'/ladders/quotes; accepted same-provider timestamp/epoch/sequence; <=6 seconds',
    'safety_footer_and_strategy_rule_labels':'Static signal-only product policy and frozen rule descriptions',
}
