"""Keep legacy cyclic collection of Qt wrappers on their owning GUI thread."""
import gc
import threading
from .QtCore import QObject,QTimer,Slot


class GuiGarbageCollector(QObject):
    def __init__(self,parent):
        super().__init__(parent)
        self.owner=threading.get_ident()
        self.enabled_before=gc.isenabled()
        self.thresholds=gc.get_threshold()
        gc.disable()
        self.timer=QTimer(self);self.timer.setInterval(1000)
        self.timer.timeout.connect(self.collect);self.timer.start()

    @Slot()
    def collect(self):
        if threading.get_ident()!=self.owner:
            raise RuntimeError('Qt wrapper collection must run on the GUI thread')
        counts=gc.get_count()
        for generation in range(3):
            if counts[generation]>self.thresholds[generation]:gc.collect(generation)

    def finish(self):
        """Call only after workers and native Qt objects have been released."""
        self.timer.stop()
        if threading.get_ident()!=self.owner:
            raise RuntimeError('Qt wrapper collection must finish on the GUI thread')
        gc.collect()
        if self.enabled_before:gc.enable()
