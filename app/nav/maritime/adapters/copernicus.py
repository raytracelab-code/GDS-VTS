"""Official Toolbox, configured dataset IDs only, bounded surface/time subsets."""
from datetime import timedelta,timezone
import math
from .base import SourceAdapter,intersects_area
from .provider_common import bbox_parts,canonical_feature,ProviderUnavailable
from ..models import utcnow,MaritimeDataError

STANDARD_NAMES={
 'sea_surface_wave_significant_height':'wave_height_m','sea_surface_wave_from_direction':'wave_direction_deg',
 'eastward_sea_water_velocity':'eastward_current_ms','northward_sea_water_velocity':'northward_current_ms',
 'sea_surface_temperature':'sst',
 'sea_surface_height_above_geoid':'sea_level_m','sea_surface_height_above_sea_level':'sea_level_m',
}


def canonical_value(field,value,unit):
    u=unit.strip().lower()
    if field in ('wave_height_m','sea_level_m'):
        factor={'m':1,'metre':1,'meter':1,'cm':.01,'mm':.001}.get(u)
        if factor is None:raise MaritimeDataError('unsupported model height unit')
        return value*factor,'m'
    if field=='wave_direction_deg':
        if u in ('degree','degrees','degrees_true'):return value,'degrees'
        if u in ('rad','radian','radians'):return math.degrees(value),'degrees'
        raise MaritimeDataError('unsupported model direction unit')
    if field.endswith('_current_ms'):
        factor={'m/s':1,'m s-1':1,'m s**-1':1,'cm/s':.01,'cm s-1':.01}.get(u)
        if factor is None:raise MaritimeDataError('unsupported model current unit')
        return value*factor,'m/s'
    return value,unit  # SST retains the dataset's explicit temperature unit.


class CopernicusAdapter(SourceAdapter):
    def __init__(self,config,product,dataset_id,username,password):
        self.config=config;self.product=product;self.dataset_id=dataset_id;self._username=username;self._password=password
    def fetch(self,area):
        if not self.dataset_id or not self._username or not self._password:raise ProviderUnavailable('NOT_CONFIGURED')
        import copernicusmarine
        objects=[];now=utcnow()
        for w,s,e,n in bbox_parts(area):
            ds=copernicusmarine.open_dataset(dataset_id=self.dataset_id,username=self._username,password=self._password,
                minimum_longitude=w,maximum_longitude=e,minimum_latitude=s,maximum_latitude=n,
                minimum_depth=0,maximum_depth=1,start_datetime=now-timedelta(hours=1),end_datetime=now+timedelta(hours=1))
            try:
                objects.extend(self.normalize(ds,area,now))
            finally:ds.close()
        return objects
    def normalize(self,ds,area,now=None):
        now=now or utcnow()
        lat=next((c for c in ('latitude','lat') if c in ds.coords),None)
        lon=next((c for c in ('longitude','lon') if c in ds.coords),None)
        if not lat or not lon or ds[lat].ndim!=1 or ds[lon].ndim!=1:raise MaritimeDataError('unsupported Copernicus coordinate grid')
        variables={k:STANDARD_NAMES[v.attrs.get('standard_name')] for k,v in ds.data_vars.items() if v.attrs.get('standard_name') in STANDARD_NAMES}
        if not variables:raise MaritimeDataError('dataset has no recognized CF maritime variables')
        data=ds[list(variables)]
        if 'time' not in data.coords or not data.sizes.get('time'):raise MaritimeDataError('dataset time missing')
        data=data.sel(time=now.replace(tzinfo=None),method='nearest')
        if 'depth' in data.dims:data=data.isel(depth=0)
        extra=set(data.dims)-{lat,lon}
        if extra:raise MaritimeDataError('unsupported additional model dimensions')
        # Sample actual grid cells, never synthesize/interpolate a new field.
        data=data.isel({lat:slice(None,None,max(1,math.ceil(data.sizes[lat]/16))),lon:slice(None,None,max(1,math.ceil(data.sizes[lon]/16)))}).load()
        observed=str(data.coords['time'].values)
        if observed.endswith('Z'):observed=observed[:-1]
        observed=observed[:26]+'+00:00'
        units={field:str(data[k].attrs.get('units','unknown')) for k,field in variables.items()}
        result=[]
        for iy,latitude in enumerate(data[lat].values):
            for ix,longitude in enumerate(data[lon].values):
                latitude,longitude=float(latitude),(float(longitude)+180)%360-180
                props={'dataset_version':self.dataset_id,'attribution':'E.U. Copernicus Marine Service Information','units':units}
                for k,field in variables.items():
                    value=float(data[k].isel({lat:iy,lon:ix}).values)
                    if math.isfinite(value):props[field],props['units'][field]=canonical_value(field,value,str(data[k].attrs.get('units','unknown')))
                if not any(field in props for field in variables.values()):continue
                first=next(field for field in variables.values() if field in props)
                props['value']=props[first];props['unit']=props['units'][first]
                props['name']=f'{self.product.upper()} {props[first]:.2f} {props["unit"]}'
                if 'eastward_current_ms' in props and 'northward_current_ms' in props:
                    props['current_knots']=math.hypot(props['eastward_current_ms'],props['northward_current_ms'])*1.94384449
                    props['heading']=math.degrees(math.atan2(props['eastward_current_ms'],props['northward_current_ms']))%360
                obj=canonical_feature(self.config.name,f'{self.dataset_id}/{latitude:.7f}/{longitude:.7f}','metocean',self.product,
                    {'type':'Point','coordinates':[longitude,latitude]},props,'MODEL',observed_at=observed)
                if intersects_area(obj.geometry,area):result.append(obj)
        return result
