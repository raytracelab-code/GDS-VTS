"""Diagnostic-only switches; never imported by the shipped application."""
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
mode=sys.argv.pop(1)
import main
from app.qt.QtWidgets import QApplication
original=main.MainWindow.__init__
def initialize(self,*args,**kwargs):
    original(self,*args,**kwargs)
    if mode=='without-filter':QApplication.instance().removeEventFilter(self.nav)
    elif mode=='without-channel':self.nav.web.page().setWebChannel(None)
    elif mode=='without-timers':self.timer.stop();self.event_timer.stop()
main.MainWindow.__init__=initialize
raise SystemExit(main.main())
