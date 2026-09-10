"""Shared standard-based BLE discovery; names are only discovery hints."""
from bleak.uuids import normalize_uuid_str

FTMS = '00001826-0000-1000-8000-00805f9b34fb'
HEART_RATE = '0000180d-0000-1000-8000-00805f9b34fb'
TRAINER_NAMES = ('wahoo', 'kickr', 'elite', 'direto', 'suito', 'justo', 'avanti', 'tacx', 'neo', 'flux', 'vortex',
                 'jetblack', 'jet black', 'victory', 'volt', 'zwift hub', 'saris', 'h3', 'h4', 'hammer',
                 'magene', 'thinkrider', 'think rider', 'van rysel', 'd100', 'd500', 'd900', 'wattbike', 'stages', 'sb20', 'zycle', 'trainer')
HR_NAMES = ('garmin', 'forerunner', 'fenix', 'venu', 'vivoactive', 'enduro', 'instinct', 'epix',
            'polar', 'tickr', 'trackr', 'coospo', 'magene', 'coros', 'suunto', 'wahoo', 'heart', 'hrm', 'hr sensor', 'h10', 'h9', 'verity', 'oh1')


def advertisement_info(device, advertisement):
    name = getattr(advertisement, 'local_name', None) or device.name or 'Bluetooth-Gerät'
    uuids = set()
    for value in getattr(advertisement, 'service_uuids', None) or []:
        try:
            uuids.add(normalize_uuid_str(value))
        except (ValueError, AttributeError):
            pass
    return name, uuids, getattr(advertisement, 'rssi', None)
