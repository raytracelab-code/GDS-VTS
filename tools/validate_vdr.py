"""Deterministic native/reference renders and PDF QA; never touches production data."""
import argparse
import json
from pathlib import Path
import runpy
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from PySide6.QtCore import QEventLoop, QSize, QTimer, QUrl
from PySide6.QtWidgets import QApplication
from app.ui.pages.vdr_page import VdrPage
from app.vdr.store import ReportStore
from app.vdr.pdf import export_pdf, import_pdf


def wait(ms=120):
    loop = QEventLoop(); QTimer.singleShot(ms, loop.quit); loop.exec()


def main():
    args = argparse.ArgumentParser()
    args.add_argument('--reference')
    args.add_argument('--interactive', action='store_true')
    args.add_argument('--shell', action='store_true', help='Open the real shell with an isolated VDR fixture')
    options = args.parse_args()
    output = ROOT/'docs/diagnostics/vdr'
    output.mkdir(parents=True, exist_ok=True)
    app = QApplication([])
    fixture = runpy.run_path(str(ROOT/'tests/test_vdr.py'))['fixture_report']()
    store = ReportStore(ROOT/'build/vdr-validation/reports.json', today='2026-11-18')
    store.reports[store.current] = fixture
    store.layout = 'scroll'
    page = VdrPage(store); page.setWindowTitle('GDS VTS · VDR acceptance fixture'); page.resize(1440, 800); page.show(); wait(350)
    page.grab().save(str(output/'scroll-desktop.png'))
    # Full report surface, not just the visible viewport.
    page.scroll.widget().grab().save(str(output/'scroll-full-report.png'))
    for index, name in enumerate(('report-hse', 'weather', 'activity', 'running-hours', 'bulk', 'crew', 'contractors')):
        page.set_mode('steps'); page.go_section(index); wait(140)
        page.grab().save(str(output/f'steps-{name}.png'))
    page.go_section(4); page.toggle_details(0); wait(150); page.grab().save(str(output/'bulk-details.png'))
    page.go_section(0); page.finalize(); wait(100); page.grab().save(str(output/'finalized.png'))
    report_pdf = output/'fixture-report.pdf'; export_pdf(page.report, report_pdf)
    assert import_pdf(report_pdf) == page.report
    from PySide6.QtPdf import QPdfDocument
    doc = QPdfDocument(); doc.load(str(report_pdf))
    for i in range(doc.pageCount()):
        size = doc.pagePointSize(i)
        doc.render(i, QSize(int(size.width()*1.5), int(size.height()*1.5))).save(str(output/f'pdf-page-{i+1}.png'))
    # Optional independent renderer avoids a QtPdf repeated-page chrome rendering bug.
    try:
        import pymupdf
        independent = pymupdf.open(report_pdf)
        for i, pdf_page in enumerate(independent):
            pdf_page.get_pixmap(matrix=pymupdf.Matrix(1.5, 1.5), alpha=False).save(str(output/f'pdf-page-{i+1}.png'))
    except ImportError:
        pass
    page.resize(1000, 750); page.go_section(2); wait(150); page.grab().save(str(output/'narrow-activity.png'))
    metrics = dict(sections=len(page.sections), pdfPages=doc.pageCount(), pdfRoundTrip=True,
                   fonts={str(p):w.font().family() for p,w in page.editors.items() if p in [('meta','captain'),('eq',0,'fm0')]})
    metrics['native'] = dict(topbarHeight=page.topbar_scroll.height(), sidebarWidth=page.sidebar.width(),
                             sidebarHeight=page.sidebar.height(), viewport='1440 x 800 desktop / 1000 x 750 narrow')
    if options.reference:
        from PySide6.QtWebEngineCore import QWebEnginePage, QWebEngineProfile, QWebEngineScript
        from PySide6.QtWebEngineWidgets import QWebEngineView
        profile = QWebEngineProfile(app)
        web = QWebEngineView(); web.setPage(QWebEnginePage(profile, web)); web.resize(1440, 800)
        fixed_clock = QWebEngineScript(); fixed_clock.setInjectionPoint(QWebEngineScript.InjectionPoint.DocumentCreation)
        fixed_clock.setWorldId(QWebEngineScript.ScriptWorldId.MainWorld)
        fixed_clock.setSourceCode('const RealDate=Date;window.Date=class extends RealDate {constructor(...args){super(...(args.length?args:["2026-11-18T12:00:00"]))}static now(){return new RealDate("2026-11-18T12:00:00").valueOf()}};')
        web.page().scripts().insert(fixed_clock)
        web.load(QUrl.fromLocalFile(str(Path(options.reference).resolve()))); web.show(); wait(1800)
        # Initialize only the isolated, off-the-record reference browser profile.
        web.page().runJavaScript('localStorage.setItem("vdr-aman-juara-v2", '+json.dumps(json.dumps(dict(reports={fixture['meta']['date']:fixture}, layout='scroll')))+'); location.reload()')
        wait(900); web.grab().save(str(output/'reference-scroll.png'))
        web.page().runJavaScript('JSON.stringify({topbar:document.querySelector(".vdr-topbar").getBoundingClientRect().toJSON(),sidebar:document.querySelector(".vdr-sidebar").getBoundingClientRect().toJSON(),sections:Array.from(document.querySelectorAll(".vdr-sec")).map(e=>e.getBoundingClientRect().toJSON())})', lambda v: metrics.update(reference=json.loads(v) if v else None))
        wait(100)
        web.page().runJavaScript('document.querySelector("[data-l=steps]").click()'); wait(160)
        web.grab().save(str(output/'reference-steps.png')); web.close(); web.deleteLater(); wait(30)
    (output/'runtime.json').write_text(json.dumps(metrics, indent=2), encoding='utf-8')
    page.resize(1440, 800); page.go_section(0)
    if options.shell:
        from app.nav.web_scheme import register_gds_scheme
        register_gds_scheme()
        from app.ui.pages import vdr_page
        vdr_page.page = lambda: page
        from app.ui.main_window import MainWindow
        shell = MainWindow(); shell.resize(1440, 900); shell.show(); shell.navigate('VDR'); wait(600)
        assert not shell.header.isVisible()
        shell.grab().save(str(output/'application-shell-vdr.png'))
        # This selects the real page for inspection; the production telemetry gate stays intact.
        metrics['shellVdrSelected'] = shell.stack.currentWidget() is page
        (output/'runtime.json').write_text(json.dumps(metrics, indent=2), encoding='utf-8')
    print(json.dumps(metrics, indent=2))
    if options.interactive:
        return app.exec()
    if options.shell:
        shell.close()
    page.close(); page.save_timer.stop()
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
