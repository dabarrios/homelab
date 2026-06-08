SERVERS = [
    {
        'name': 'Vanilla 2025',
        'slug': 'mc1',
        'version': '1.21.11',
        'memory': '6GB',
        'port': 25565,
        'status': 'stopped',
    },
    {
        'name': 'Solo World 2025',
        'slug': 'mc2',
        'version': '1.21.11',
        'memory': '4GB',
        'port': 25566,
        'status': 'stopped',
    },
    {
        'name': 'Cobbleverse 2026',
        'slug': 'mc3',
        'version': '1.21.11',
        'memory': '8GB',
        'port': 25567,
        'status': 'stopped',
    },
]

def get_server_list():
    return SERVERS

def get_server_details(slug):
    for server in SERVERS:
        if server['slug'] == slug:
            return server
    
    return None