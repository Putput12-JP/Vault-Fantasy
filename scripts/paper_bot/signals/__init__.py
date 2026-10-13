"""Signal sources. Add one by writing a class with `collect` and listing it in SOURCES."""
from .cfb_ml import CfbMoneylineSource
from .nba_total import NbaTotalSource

SOURCES = {
    'nba_total': NbaTotalSource,
    'cfb_ml': CfbMoneylineSource,
}


def load_sources(cfg, root, get=None):
    from ..config import source_cfg
    out = []
    for name, cls in SOURCES.items():
        sc = source_cfg(cfg, name)
        if not sc['enabled']:
            continue
        out.append(cls(sc, root, get=get))
    return out
