import requests
import os
from typing import Dict, Optional

class VoxelizeClient:
    def __init__(self, api_key: Optional[str] = None, base_url: str = "https://api.vixiv.com/api/v1"):
        self.base_url = base_url.rstrip('/')
        self.api_key = api_key or os.environ.get('VOXELIZE_API_KEY')
        if not self.api_key:
            raise ValueError("API key must be provided either through constructor or VOXELIZE_API_KEY environment variable")
        
        self.session = requests.Session()
        self.session.headers.update({
            'X-API-Key': self.api_key,
            'Content-Type': 'application/json'
        })

    def get_status(self) -> Dict:
        """Get the current status of the API."""
        return self._make_request('GET', 'status')

    def get_state(self) -> Dict:
        """Get the current processing state."""
        return self._make_request('GET', 'state')

    def voxelize_mesh(self, file_path: str, **kwargs) -> Dict:
        """Voxelize a mesh file."""
        with open(file_path, 'rb') as f:
            files = {'file': (os.path.basename(file_path), f, 'application/sla')}
            return self._make_request('POST', 'voxelize', files=files, data=kwargs)

    def generate_shader(self, cell_type: str, positions: list, **kwargs) -> Dict:
        """Generate a shader for visualization."""
        data = {
            'cell_type': cell_type,
            'positions': positions,
            **kwargs
        }
        return self._make_request('POST', 'generate-shader', json=data)

    def calculate_voxel_centers(self, cell_type: str, cell_size: float, **kwargs) -> Dict:
        """Calculate voxel centers."""
        data = {
            'cell_type': cell_type,
            'cell_size': cell_size,
            **kwargs
        }
        return self._make_request('POST', 'voxel-centers', json=data)

    def _make_request(self, method: str, endpoint: str, **kwargs) -> Dict:
        """Make a request to the API."""
        url = f"{self.base_url}/{endpoint.lstrip('/')}"
        response = self.session.request(method, url, **kwargs)
        response.raise_for_status()
        return response.json()