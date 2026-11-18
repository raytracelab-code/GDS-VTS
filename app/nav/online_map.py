"""Lightweight NAV defaults; offline infrastructure remains opt-in."""
ONLINE_STYLE = 'https://tiles.openfreemap.org/styles/liberty'
PRIMARY_REGION = ('Bangladesh', 'Myanmar', 'Thailand', 'Laos', 'Cambodia',
                  'Vietnam', 'Malaysia', 'Singapore', 'Brunei', 'Indonesia', 'Philippines')


def online_config():
    from app.nav.offline_maps.render_config import render_config
    config = render_config(None)
    background = config['style']['layers'][0]
    background['paint']['background-color'] = '#cddfe3'
    background['metadata']['gds:role'] = 'WATER'
    config.update(preferred_source='online', online_style_url=ONLINE_STYLE,
                  status='MAP · ONLINE · CONNECTING', primary_region=list(PRIMARY_REGION))
    return config
