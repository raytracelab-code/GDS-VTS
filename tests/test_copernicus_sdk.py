"""SDK contract and actual xarray normalization, without authentication or network."""
import inspect
import math
from datetime import datetime, timezone

import pytest

from app.nav.maritime.adapters.base import SourceConfig
from app.nav.maritime.adapters.copernicus import CopernicusAdapter
from app.nav.maritime.area_controller import OperatingArea


def test_toolbox_fetch_matches_installed_sdk_and_closes_dataset(monkeypatch):
    sdk=pytest.importorskip('copernicusmarine',reason='Optional provider SDK')
    xr=pytest.importorskip('xarray')
    np=pytest.importorskip('numpy')
    from app.nav.maritime.adapters import copernicus as module
    now=datetime(2026,11,1,12,tzinfo=timezone.utc)
    monkeypatch.setattr(module,'utcnow',lambda:now)
    signature=inspect.signature(sdk.open_dataset)
    ds=xr.Dataset({'wave':(('time','latitude','longitude'),np.array([[[150.,float('nan')]]]),
        {'standard_name':'sea_surface_wave_significant_height','units':'cm'})},
        coords={'time':[np.datetime64('2026-11-01T12:00:00')],'latitude':[22.],'longitude':[91.,91.01]})
    closed=[];ds.set_close(lambda:closed.append(True));calls=[]
    def open_local(**kwargs):
        signature.bind(**kwargs)  # Actual installed Toolbox signature, no real remote call.
        calls.append(kwargs)
        return ds
    monkeypatch.setattr(sdk,'open_dataset',open_local)
    adapter=CopernicusAdapter(SourceConfig('copernicus_wave','https://example.invalid'),
        'wave','local-contract-fixture','fixture-user','fixture-password')
    result=adapter.fetch(OperatingArea(22,91,5))
    assert len(result)==1 and result[0].properties['wave_height_m']==1.5
    assert result[0].observed_at==now and result[0].properties['units']['wave_height_m']=='m'
    assert result[0].geometry['coordinates']==[91,22]
    assert closed==[True] and len(calls)==1


def test_real_current_grid_preserves_cell_values_time_and_units():
    xr=pytest.importorskip('xarray');np=pytest.importorskip('numpy')
    ds=xr.Dataset({
        'u':(('time','depth','latitude','longitude'),np.array([[[[100.,0.]]]]),
             {'standard_name':'eastward_sea_water_velocity','units':'cm/s'}),
        'v':(('time','depth','latitude','longitude'),np.array([[[[0.,100.]]]]),
             {'standard_name':'northward_sea_water_velocity','units':'cm/s'})},
        coords={'time':[np.datetime64('2026-11-01T12:00:00')],'depth':[0.],
                'latitude':[22.],'longitude':[91.,91.01]})
    adapter=CopernicusAdapter(SourceConfig('copernicus_current','https://example.invalid'),'current','local-grid','','')
    result=adapter.normalize(ds,OperatingArea(22,91,5),datetime(2026,11,1,12,tzinfo=timezone.utc))
    assert len(result)==2
    assert [o.properties['heading'] for o in result]==[90.,0.]
    assert all(math.isclose(o.properties['current_knots'],1.94384449) for o in result)
    assert all(o.properties['source_tier']=='MODEL' for o in result)
