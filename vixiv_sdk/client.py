import requests
import json
from typing import Dict, List, Union, Optional, Tuple
import os
from pathlib import Path

class VoxelizeClient:
    """Python client for the Voxelize API."""
    
    def __init__(self, api_key: Optional[str] = None, base_url: str = "http://localhost:5000/api/v1"):
        """Initialize the Voxelize client.
        
        Args:
            api_key (str, optional): API key for authentication. If not provided, will look for VOXELIZE_API_KEY environment variable
            base_url (str): Base URL of the Voxelize API. Defaults to http://localhost:5000/api/v1
        """
        self.base_url = base_url.rstrip('/')
        print(os.environ.get('VOXELIZE_API_KEY'))
        self.api_key = api_key or os.environ.get('VOXELIZE_API_KEY')
        if not self.api_key:
            raise ValueError("API key must be provided either through constructor or VOXELIZE_API_KEY environment variable")
        
        # Don't set Content-Type header in session - let requests set it automatically for multipart
        self.session = requests.Session()
        self.session.headers.update({
            'X-API-Key': self.api_key
        })
        
    def _make_request(self, method: str, endpoint: str, **kwargs) -> Dict:
        """Make a request to the API.
        
        Args:
            method (str): HTTP method (GET, POST, DELETE)
            endpoint (str): API endpoint
            **kwargs: Additional arguments to pass to requests
            
        Returns:
            Dict: Response from the API
            
        Raises:
            requests.exceptions.RequestException: If the request fails
            ValueError: If the API returns an error
        """
        url = f"{self.base_url}/{endpoint.lstrip('/')}"
        
        # Remove Content-Type header for multipart file uploads
        headers = self.session.headers.copy()
        if 'files' in kwargs:
            headers.pop('Content-Type', None)
            kwargs['headers'] = headers
        
        response = self.session.request(method, url, **kwargs)
        
        if response.status_code == 429:
            raise ValueError("Rate limit exceeded. Please try again later.")
        elif response.status_code == 401:
            raise ValueError("Invalid API key")
        
        response.raise_for_status()
        return response.json()
    
    def voxelize_mesh(self, 
                     file_path: str, 
                     cell_type: str = "fcc",
                     cell_size: float = 40.0,
                     beam_diameter: float = 2.0,
                     min_skin_thickness: float = 0.01,
                     sampling_res: Tuple[int, int, int] = (1, 1, 1),
                     force_dir: Tuple[float, float, float] = (0, 0, 1)) -> Dict:
        """
        Voxelize a mesh file using the specified parameters.
        
        Args:
            file_path: Path to the input STL file
            cell_type: Type of cell ("fcc", "bcc", or "flourite")
            cell_size: Size of the cells in mm
            beam_diameter: Diameter of the beams in mm
            min_skin_thickness: Minimum skin thickness in mm
            sampling_res: Sampling resolution in xyz directions
            force_dir: Force direction vector for unit cell orientation
            
        Returns:
            Dict containing success status and output file path
        """
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"File not found: {file_path}")
        
        if not file_path.lower().endswith('.stl'):
            raise ValueError("Only STL files are supported")
        
        with open(file_path, 'rb') as f:
            files = {'file': (os.path.basename(file_path), f, 'application/octet-stream')}
            
            data = {
                'cell_type': cell_type,
                'cell_size': str(cell_size),
                'beam_diameter': str(beam_diameter),
                'min_skin_thickness': str(min_skin_thickness),
                'sampling_res_x': str(sampling_res[0]),
                'sampling_res_y': str(sampling_res[1]),
                'sampling_res_z': str(sampling_res[2]),
                'force_dir_x': str(force_dir[0]),
                'force_dir_y': str(force_dir[1]),
                'force_dir_z': str(force_dir[2])
            }
            
            response = self._make_request('POST', 'voxelize', files=files, data=data)
            
            if response.get('success'):
                # Save the result file
                result = response['result']
                output_dir = os.path.dirname(file_path)
                output_path = os.path.join(output_dir, f"voxelized_{result['filename']}")
                with open(output_path, 'wb') as f:
                    f.write(bytes.fromhex(result['file_content']))
                return {'success': True, 'output_path': output_path}
            return response
    
    def generate_shader(self,
                   cell_type: str,
                   positions: List[Tuple[float, float, float]],
                   cell_size: float = 40.0,
                   beam_diameter: float = 2.0,
                   view_normals: bool = False,
                   aa_passes: int = 0,
                   angle: float = 0.0) -> Dict:
        """Generate a shader for visualization.
        
        Args:
            cell_type: Type of cell ("fcc", "bcc", or "flourite")
            positions: List of cell center positions
            cell_size: Size of the cells in mm
            beam_diameter: Diameter of the beams in mm
            view_normals: Whether to visualize as shaded or normals
            aa_passes: Number of anti-aliasing passes
            angle: Rotation angle in degrees
            
        Returns:
            Dict containing success status and shader content
        """
        data = {
            'cell_type': cell_type,
            'positions': positions,
            'cell_size': cell_size,
            'beam_diameter': beam_diameter,
            'view_normals': view_normals,
            'aa_passes': aa_passes,
            'angle': angle
        }
        return self._make_request('POST', 'generate-shader', json=data)
    
    def calculate_voxel_centers(self,
                              cell_type: str,
                              cell_size: float,
                              angle: Optional[float] = None) -> Dict:
        """Calculate voxel centers.
        
        Args:
            cell_type (str): Type of cell
            cell_size (float): Size of the cells
            angle (float, optional): Angle for calculation
            
        Returns:
            Dict: Calculated voxel centers and angle
        """
        data = {
            'cell_type': cell_type,
            'cell_size': cell_size
        }
        if angle is not None:
            data['angle'] = angle
            
        return self._make_request('POST', 'voxel-centers', json=data)
    
    def get_state(self) -> Dict:
        """Get the current processing state (only available in stateful mode).
        
        Returns:
            Dict: Current state information
            
        Raises:
            ValueError: If stateful mode is disabled
        """
        return self._make_request('GET', 'state')
    
    def clear_state(self) -> Dict:
        """Clear the current state (only available in stateful mode).
        
        Returns:
            Dict: Confirmation message
            
        Raises:
            ValueError: If stateful mode is disabled
        """
        return self._make_request('DELETE', 'state')
    
    def get_status(self) -> Dict:
        """Get the current status of the API.
        
        Returns:
            Dict: API status information including rate limiting and state management status
        """
        return self._make_request('GET', 'status') 