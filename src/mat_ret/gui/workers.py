"""
Async Workers for Database Fetching

Provides QThread-based workers for non-blocking database queries.
"""

from typing import Dict, List, Optional
from PyQt6.QtCore import QThread, pyqtSignal, QObject

from ..search import SearchFilters


class FetchWorker(QThread):
    """Worker thread for fetching materials from databases."""
    
    # Signals
    progress = pyqtSignal(str, int)  # (database_name, count)
    database_complete = pyqtSignal(str, list)  # (database_name, results)
    finished_all = pyqtSignal(dict)  # all results
    error = pyqtSignal(str, str)  # (database_name, error_message)
    status_update = pyqtSignal(str)  # status message
    
    def __init__(self, 
                 formula: str,
                 databases: List[str],
                 limit: int = 10,
                 mp_api_key: Optional[str] = None,
                 mpds_api_key: Optional[str] = None,
                 optimade_providers: Optional[List[Dict[str, str]]] = None,
                 query_mode: str = "formula",
                 elements: Optional[List[str]] = None,
                 filters: Optional[SearchFilters] = None,
                 parent=None):
        super().__init__(parent)
        self.formula = formula
        self.query_mode = query_mode
        self.elements = elements or []
        self.databases = databases
        self.limit = limit
        self.mp_api_key = mp_api_key
        self.mpds_api_key = mpds_api_key
        self.optimade_providers = optimade_providers or []
        self.filters = filters
        self._is_cancelled = False
    
    def cancel(self):
        """Cancel the fetch operation."""
        self._is_cancelled = True
    
    def run(self):
        """Execute the fetch operation."""
        results = {}
        
        # Import the fetch functions
        try:
            from mat_ret.api import (
                fetch_materials_project,
                fetch_jarvis,
                fetch_aflow,
                fetch_alexandria,
                fetch_materials_cloud,
                fetch_oqmd,
                fetch_mpds,
                fetch_optimade,
            )
        except ImportError as e:
            self.error.emit("Import", f"Failed to import mat_ret: {e}")
            self.finished_all.emit({})
            return
        
        # Database fetch configuration
        fetch_config = {
            'materials_project': {
                'func': fetch_materials_project,
                'requires_key': True,
                'key_param': 'api_key',
                'key_value': self.mp_api_key,
                'display_name': 'Materials Project',
                'supports_elements': True,
            },
            'jarvis': {
                'func': fetch_jarvis,
                'requires_key': False,
                'display_name': 'JARVIS',
                'supports_elements': True,
            },
            'aflow': {
                'func': fetch_aflow,
                'requires_key': False,
                'display_name': 'AFLOW',
                'supports_elements': True,
            },
            'alexandria': {
                'func': fetch_alexandria,
                'requires_key': False,
                'display_name': 'Alexandria',
                'supports_elements': True,
            },
            'materials_cloud': {
                'func': fetch_materials_cloud,
                'requires_key': False,
                'extra_params': {'mp_api_key': self.mp_api_key} if self.mp_api_key else {},
                'display_name': 'Materials Cloud',
                'supports_elements': True,
            },
            'oqmd': {
                'func': fetch_oqmd,
                'requires_key': False,
                'display_name': 'OQMD',
                'supports_elements': False,
            },
            'mpds': {
                'func': fetch_mpds,
                'requires_key': True,
                'key_param': 'api_key',
                'key_value': self.mpds_api_key,
                'display_name': 'MPDS',
                'supports_elements': True,
            },
            'optimade': {
                'func': fetch_optimade,
                'requires_key': False,
                'display_name': 'OPTIMADE',
                'supports_elements': True,
                'extra_params': {'providers': self.optimade_providers} if self.optimade_providers else {}
            }
        }
        
        total_dbs = len(self.databases)
        
        for i, db_id in enumerate(self.databases):
            if self._is_cancelled:
                self.status_update.emit("Fetch cancelled")
                break
            
            if db_id not in fetch_config:
                self.error.emit(db_id, f"Unknown database: {db_id}")
                continue
            
            config = fetch_config[db_id]
            display_name = config['display_name']

            if self.query_mode == "elements_all" and not config.get("supports_elements", False):
                self.status_update.emit(
                    f"{display_name} skipped for element-set search (no reliable native filter)."
                )
                results[db_id] = []
                self.progress.emit(db_id, 0)
                self.database_complete.emit(db_id, [])
                continue
            
            self.status_update.emit(f"Fetching from {display_name}... ({i+1}/{total_dbs})")
            
            try:
                # Build kwargs
                kwargs = {'limit': self.limit}
                if self.query_mode == "elements_all" and self.elements:
                    kwargs["elements"] = list(self.elements)
                
                # Add search filters
                if self.filters is not None and self.filters.has_any_filter():
                    kwargs['filters'] = self.filters
                
                # Add API key if required
                if config.get('requires_key'):
                    key_value = config.get('key_value', '')
                    if not key_value:
                        self.error.emit(db_id, f"{display_name} requires an API key")
                        results[db_id] = []
                        continue
                    kwargs[config['key_param']] = key_value
                
                # Add extra parameters
                if 'extra_params' in config:
                    kwargs.update(config['extra_params'])
                
                # Execute fetch
                db_results = config['func'](self.formula, **kwargs)
                
                if db_results is None:
                    db_results = []
                
                results[db_id] = db_results
                
                self.progress.emit(db_id, len(db_results))
                self.database_complete.emit(db_id, db_results)
                self.status_update.emit(f"Found {len(db_results)} materials from {display_name}")
                
            except Exception as e:
                error_msg = str(e)
                self.error.emit(db_id, error_msg)
                results[db_id] = []
                self.status_update.emit(f"Error fetching from {display_name}: {error_msg[:50]}...")
        
        if not self._is_cancelled:
            total_count = sum(len(v) for v in results.values())
            self.status_update.emit(f"Fetch complete: {total_count} materials from {len(results)} databases")
        
        self.finished_all.emit(results)


class SingleFetchWorker(QThread):
    """Worker for fetching from a single database."""
    
    finished = pyqtSignal(str, list)  # (database_name, results)
    error = pyqtSignal(str, str)  # (database_name, error_message)
    status_update = pyqtSignal(str)
    
    def __init__(self,
                 database: str,
                 formula: str,
                 limit: int = 10,
                 api_key: Optional[str] = None,
                 parent=None):
        super().__init__(parent)
        self.database = database
        self.formula = formula
        self.limit = limit
        self.api_key = api_key
    
    def run(self):
        """Execute the single database fetch."""
        try:
            from mat_ret.databases import (
                MaterialsProjectClient,
                JARVISClient,
                AFLOWClient,
                AlexandriaClient,
                MaterialsCloudClient,
                OQMDClient,
                MPDSClient
            )
            
            client_map = {
                'materials_project': (MaterialsProjectClient, True),
                'jarvis': (JARVISClient, False),
                'aflow': (AFLOWClient, False),
                'alexandria': (AlexandriaClient, False),
                'materials_cloud': (MaterialsCloudClient, False),
                'oqmd': (OQMDClient, False),
                'mpds': (MPDSClient, True),
            }
            
            if self.database not in client_map:
                self.error.emit(self.database, f"Unknown database: {self.database}")
                return
            
            client_class, requires_key = client_map[self.database]
            
            if requires_key:
                if not self.api_key:
                    self.error.emit(self.database, "API key required")
                    return
                client = client_class(self.api_key)
            else:
                client = client_class()
            
            self.status_update.emit(f"Fetching from {self.database}...")
            
            results = client.get_structures(self.formula, limit=self.limit)
            
            self.finished.emit(self.database, results or [])
            
        except Exception as e:
            self.error.emit(self.database, str(e))
