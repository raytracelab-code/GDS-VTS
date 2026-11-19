"""Qt5 WebChannel transport adapter; the canonical MapBridge stays unchanged.

Avoid passing Python dictionaries through Qt5 WebChannel's native QVariantMap
conversion. JSON travels as QString, then the browser restores the existing API.
"""
import json
from app.qt.QtCore import QObject,Signal,Slot

JSON_SIGNALS=('offlineConfigChanged','paletteChanged','maritimeStateChanged','telemetryChanged',
              'renderStateChanged','spatialStateChanged','eventStateChanged','selectedSpatialFeatureChanged')
JSON_GETTERS=('getSatelliteMapConfig','getOfflineMapConfig','getPalette','getMaritimeState','getEventState')
CONTROL_SLOTS={
 'reportBasemapState':(str,str,str),'reportMapStatus':(str,),'reportOfflineRegions':(str,str),
 'reportMapCenter':(float,float),'setMapView':(str,),'reportReferenceError':(str,),
 'selectMaritimeObject':(str,),'clearMaritimeSelection':(),'setMaritimeVisibility':(str,bool),
 'reportMaritimeViewport':(float,float,float,float),'selectEvent':(str,),'clearEventSelection':(),
 'mapReady':(),'mapInteraction':(str,),'selectSpatialFeature':(str,str),
 'clearSpatialFeature':(),'reportSpatialView':(bool,)}


def encode(value):return json.dumps(value,ensure_ascii=False,allow_nan=False,separators=(',',':'))


def getter(name):
    def call(self):return encode(getattr(self.bridge,name)())
    call.__name__=name
    return Slot(result=str)(call)


def control(name,types):
    def call(self,*args):return getattr(self.bridge,name)(*args)
    call.__name__=name
    return Slot(*types)(call)


def initialize(self,bridge,parent=None):
    QObject.__init__(self,parent);self.bridge=bridge;self._forwarders=[]
    for name in JSON_SIGNALS:
        def forward(value,target=getattr(self,name)):target.emit(encode(value))
        self._forwarders.append(forward);getattr(bridge,name).connect(forward)


members={'__module__':__name__,'__init__':initialize}
members.update({name:Signal(str) for name in JSON_SIGNALS})
members.update({name:getter(name) for name in JSON_GETTERS})
members.update({name:control(name,types) for name,types in CONTROL_SLOTS.items()})
LegacyWebBridge=type('LegacyWebBridge',(QObject,),members)


def browser_adapter():
    """Only legacy qwebchannel.js is extended; NAV's JS API is unchanged."""
    return ('''\n;(function(){
const NativeChannel=QWebChannel;
window.QWebChannel=function(transport,ready,converters){
 return new NativeChannel(transport,channel=>{
  const wire=channel.objects.bridge;
  if(wire){
   const bridge=Object.create(wire);
   for(const name of GETTERS)bridge[name]=callback=>wire[name](value=>callback(JSON.parse(value)));
   for(const name of SIGNALS){
    const callbacks=new Map();
    bridge[name]={connect:callback=>{const decoded=value=>callback(JSON.parse(value));callbacks.set(callback,decoded);wire[name].connect(decoded)},
                  disconnect:callback=>{const decoded=callbacks.get(callback);if(decoded){wire[name].disconnect(decoded);callbacks.delete(callback)}}};
   }
   channel.objects.bridge=bridge;
  }
  ready(channel);
 },converters);
};
window.QWebChannel.prototype=NativeChannel.prototype;
})();\n'''.replace('GETTERS',json.dumps(JSON_GETTERS)).replace('SIGNALS',json.dumps(JSON_SIGNALS))).encode('utf-8')
