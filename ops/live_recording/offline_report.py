"""One-operation LOCAL completion bridge; never connects to production.

Reuses the preserved finalizer, package transfer, restore and independent reader.
Input must be an already stopped recorder directory. This does not stop a live
recorder, retrieve Railway files, or qualify a live campaign.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import time
import zipfile
from xml.sax.saxutils import escape

MiB = 1024 ** 2
MAX_INPUT = 512 * MiB
MAX_WORK = 4096 * MiB
CHECKPOINT = 'f56b2b41f03b9d2f6377a2746fde22eb2b88af43'


def digest(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as f:
        for b in iter(lambda: f.read(MiB), b''):
            h.update(b)
    return h.hexdigest()


def write_json(path, value):
    Path(path).write_text(json.dumps(value, sort_keys=True, indent=2) + '\n')


def no_network(*a, **kw):
    raise RuntimeError('OFFLINE_BRIDGE_NETWORK_FORBIDDEN')


def render_pdf(path, quality, receipt):
    """Presentation of existing reader findings; no replacement verification."""
    from reportlab.lib import colors
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.lib.units import inch
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
    import reportlab
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    fonts = Path(reportlab.__file__).parent/'fonts'
    pdfmetrics.registerFont(TTFont('BTC15Vera', str(fonts/'Vera.ttf')))
    pdfmetrics.registerFont(TTFont('BTC15VeraBold', str(fonts/'VeraBd.ttf')))
    styles = getSampleStyleSheet()
    for style in styles.byName.values():
        style.fontName = 'BTC15VeraBold' if style.name in ('Title','Heading1','Heading2','Heading3') else 'BTC15Vera'
    styles['BodyText'].fontSize = 9
    styles['BodyText'].leading = 13
    story = []
    def para(s, style='BodyText'):
        story.append(Paragraph(escape(str(s)), styles[style]))
        story.append(Spacer(1, 6))
    para(receipt.get('title','BTC15 | Evidence findings'), 'Title')
    campaign=receipt.get('scope')=='CAMPAIGN'
    para(receipt.get('subtitle','SEALED CAMPAIGN FINDINGS' if campaign else 'LOCAL COMPLETION ONLY - LIVE READINESS NOT ESTABLISHED'), 'Heading2')
    para('Result: ' + receipt['status'])
    para(('Private live retrieval demonstrated: '+str(receipt.get('live_retrieval',False))+'. Original application clocks are retained; displayed depth is not a fill. No orders or model evaluation are performed by this reporting operation.') if campaign else ('No live source, strategy, model, deployment or trading order was run. '
         'This report presents the unchanged independent reader output. '
         'A completed PDF is not proof of production retrieval.'))
    para('Evidence scope', 'Heading2')
    for key in ('fixture_only', 'fixture_complete', 'complete_evidence', 'cost_verified',
                'recording_readiness', 'economic_evidence_readiness', 'production_approval'):
        para(key + ': ' + str(quality.get(key, 'UNAVAILABLE')))
    if receipt.get('failure'):
        para('Failure: ' + receipt['failure'])
    para('Observed coverage', 'Heading2')
    for asset, value in quality.get('coverage', {}).items():
        para(asset + ': ' + json.dumps(value, sort_keys=True))
    para('Record counts: ' + json.dumps(quality.get('counts', {}), sort_keys=True))
    if campaign:
        para('Emitted lifecycle labels: '+json.dumps(quality.get('lifecycle_emitted',{}),sort_keys=True))
        para('Pending outcomes: '+json.dumps(quality.get('pending_outcomes',{}),sort_keys=True))
        para('Absent-event basis: '+str(quality.get('absent_lifecycle_basis','UNKNOWN')))
        para('Contract boundaries: '+json.dumps(quality.get('contract_boundaries',{}),sort_keys=True))
        para('Origin/terminal links outside the recorded interval: '+str(quality.get('unresolved_origin_or_terminal_links',0))+'. Historical cache rows without an original upstream receipt: '+str(quality.get('upstream_candle_receipts_not_captured',0))+'. These are not backdated or invented.')
        para('Recording health and resource gates', 'Heading2')
        for role,h in quality.get('health',{}).items():
            para(role+': '+json.dumps({k:h.get(k) for k in ('failure','raw_bytes','compressed_bytes','records','elapsed','hooks','writer')},sort_keys=True))
        projection=quality.get('24h_projection')
        if projection:para('24-hour projection within fixed profile: '+str(projection['within_profile'])+'. Live timing, transfer and resource measurements remain required. Raw projection and role receipts are included.')
    for note in quality.get('notes',[]):para(note)
    para('Evidence requirements', 'Heading2')
    rows = [[Paragraph(x, styles['BodyText']) for x in ('Category', 'Status', 'Count')]]
    for row in quality.get('matrix', []):
        rows.append([Paragraph(escape(str(row.get(k, ''))), styles['BodyText'])
                     for k in ('requirement', 'status', 'records')])
    table = Table(rows, colWidths=[3.6*inch, 1.25*inch, .65*inch], repeatRows=1)
    table.setStyle(TableStyle([('BACKGROUND', (0,0), (-1,0), colors.HexColor('#e8eef5')),
                               ('VALIGN', (0,0), (-1,-1), 'TOP'),
                               ('GRID', (0,0), (-1,-1), .25, colors.HexColor('#ccd5df')),
                               ('TOPPADDING', (0,0), (-1,-1), 5),
                               ('BOTTOMPADDING', (0,0), (-1,-1), 5)]))
    story.append(table)
    para('Missing or unresolved evidence', 'Heading2')
    gaps = quality.get('gaps', [])
    para('Reader gap/error entries: ' + str(len(gaps)))
    for gap in gaps[:40]:
        para(json.dumps(gap, sort_keys=True)[:1600])
    if len(gaps) > 40:
        para('Remaining entries are preserved in gaps.json; this PDF displays the first 40.')
    for text in receipt['live_blockers']:
        para(text)
    para('Integrity and recovery', 'Heading2')
    para('Source inventory SHA256: ' + receipt.get('source_inventory_sha256', 'UNAVAILABLE'))
    para('Package manifest SHA256: ' + receipt.get('package_sha256', 'UNAVAILABLE'))
    para('Raw files, source hashes, reader ledgers, completion receipt and this PDF '
         'are retained in recovery.zip. Nothing is deleted from the input.')
    def footer(canvas, doc):
        canvas.setFont('BTC15Vera', 8)
        canvas.drawString(44, 28, 'BTC15 | Signal-only | No automatic orders')
        canvas.drawRightString(568, 28, str(doc.page))
    SimpleDocTemplate(str(path), pagesize=(612,792), leftMargin=44, rightMargin=44,
                      topMargin=40, bottomMargin=42).build(story, onFirstPage=footer, onLaterPages=footer)


def run(recorder, sealed_root, output):
    recorder = Path(recorder).resolve()
    sys.path.insert(0, str(recorder))
    from ops.recording_workflow.policy import local_root
    from ops.recording_workflow.operator import finalize
    from ops.recording_workflow.transfer import package
    root, output = local_root(sealed_root), local_root(output)
    if root == output or root in output.parents or output in root.parents:
        raise ValueError('OUTPUT_MUST_BE_SEPARATE')
    if output.exists():
        raise ValueError('NEW_OUTPUT_REQUIRED')
    head = subprocess.check_output(['git','rev-parse','HEAD'], cwd=recorder, text=True).strip()
    if head != CHECKPOINT:
        raise ValueError('PRESERVED_CHECKPOINT_REQUIRED')
    entries = []
    for p in sorted(root.rglob('*')):
        if p.is_symlink():
            raise ValueError('SOURCE_SYMLINK')
        if p.is_file():
            entries.append(dict(path=str(p.relative_to(root)), size=p.stat().st_size, sha256=digest(p)))
    if not entries or sum(e['size'] for e in entries) > MAX_INPUT:
        raise ValueError('LOCAL_INPUT_BUDGET')
    if not (root/'terminal-status.json').is_file():
        raise ValueError('STOP_RECEIPT_REQUIRED')
    health = json.loads((root/'terminal-status.json').read_bytes())
    if health.get('status') not in ('CLOSED', 'INCOMPLETE'):
        raise ValueError('STOPPED_INPUT_REQUIRED')
    os.umask(0o077)
    output.mkdir(parents=True)
    write_json(output/'SOURCE_INVENTORY.json', entries)
    receipt = dict(status='INCOMPLETE', complete_evidence=False, live_retrieval=False,
        checkpoint=CHECKPOINT, source_inventory_sha256=digest(output/'SOURCE_INVENTORY.json'),
        live_blockers=[
          'The preserved bootstrap rejects live mode and has no deployed stop/seal supervisor.',
          'SCALP, Admin, settlement/closeout and original completed-candle provenance need live-profile integration.',
          'Actual private Railway transfer, running dependencies, timing overhead and full-day capacity remain unqualified.',
          'No accuracy, fills, profitability or complete live-evidence verdict is established.'])
    quality = {}
    socket.socket.connect = no_network
    socket.create_connection = no_network
    try:
        # Existing components do every verification, association and raw transfer.
        finalized = finalize(root, output/'producer', health=health)
        result = package(root, output/'producer/index', output/'private-store', quota=512*MiB,
                         identity=json.loads((root/'identity.json').read_bytes()),
                         report=output/'producer/report/quality.json')
        receipt['package_sha256'] = result['sha256']
        # A fresh process restores the package and reruns the existing reader.
        script = """import json,socket,sys
def deny(*a,**k): raise RuntimeError('NETWORK_FORBIDDEN')
socket.socket.connect=deny; socket.create_connection=deny
sys.path.insert(0,sys.argv[1])
from ops.recording_workflow.transfer import restore
from ops.recording_workflow.operator import finalize
from pathlib import Path
r=restore(sys.argv[2],sys.argv[4],expected_sha256=sys.argv[3])
Path(sys.argv[6]).write_text(json.dumps(r,sort_keys=True)+'\\n')
finalize(sys.argv[4],sys.argv[5],health=json.loads(sys.argv[7]))
"""
        with (output/'independent-reader.log').open('wb') as log:
            subprocess.run([sys.executable,'-B','-c',script,str(recorder),result['manifest'],
                result['sha256'],str(output/'reader'),str(output/'reader-finalized'),
                str(output/'restore-receipt.json'),json.dumps(health)],
                cwd=output, stdout=log, stderr=subprocess.STDOUT, timeout=420, check=True)
        quality = json.loads((output/'reader-finalized/report/quality.json').read_bytes())
        receipt['status'] = 'LOCAL_FIXTURE_COMPLETED' if quality.get('fixture_complete') else 'INCOMPLETE'
    except Exception as exc:
        receipt['failure'] = type(exc).__name__ + ': ' + str(exc)[:500]
    # Do not silently accept concurrent modification or a failed transfer.
    for e in entries:
        if not (root/e['path']).is_file() or digest(root/e['path']) != e['sha256']:
            receipt.update(status='INCOMPLETE', failure='INPUT_CHANGED_DURING_REVIEW')
    write_json(output/'completion-receipt.json', receipt)
    render_pdf(output/'BTC15_Findings.pdf', quality, receipt)
    receipts = [dict(path=str(p.relative_to(output)),size=p.stat().st_size,sha256=digest(p))
                for p in sorted(output.rglob('*')) if p.is_file()]
    if sum(e['size'] for e in receipts) + sum(e['size'] for e in entries) > MAX_WORK // 2:
        raise ValueError('ALL_COPY_WORK_BUDGET')
    write_json(output/'OUTPUT_HASHES.json', receipts)
    # Includes immutable raw input even if a later reader stage failed.
    with zipfile.ZipFile(output/'recovery.zip','x',compression=zipfile.ZIP_DEFLATED) as z:
        for e in entries:
            z.write(root/e['path'], 'original-input/'+e['path'])
        for p in sorted(output.rglob('*')):
            if p.is_file() and p.name != 'recovery.zip':
                z.write(p,'completion/'+str(p.relative_to(output)))
    write_json(output/'DELIVERY.json',dict(pdf='BTC15_Findings.pdf',pdf_sha256=digest(output/'BTC15_Findings.pdf'),
        recovery='recovery.zip',recovery_sha256=digest(output/'recovery.zip'),status=receipt['status']))
    return receipt


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--recorder',required=True)
    p.add_argument('--sealed-root',required=True)
    p.add_argument('--output',required=True)
    a = p.parse_args()
    result = run(a.recorder,a.sealed_root,a.output)
    print(json.dumps(result,sort_keys=True))
    sys.exit(0 if result['status']=='LOCAL_FIXTURE_COMPLETED' else 2)
