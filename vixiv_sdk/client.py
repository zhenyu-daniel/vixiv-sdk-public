import requests
import os
from typing import Dict, Optional, Tuple, Union

class VoxelizeClient:
    def __init__(self, api_key: Optional[str] = None, base_url: str = "http://127.0.0.1:5000/api/v1"):
        self.base_url = base_url.rstrip('/')
        self.api_key = api_key or os.environ.get('VOXELIZE_API_KEY')
        if not self.api_key:
            raise ValueError("API key must be provided either through constructor or VOXELIZE_API_KEY environment variable")
        
        self.session = requests.Session()
        self.session.headers.update({
            'X-API-Key': self.api_key
        })

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
                       positions: list,
                       cell_size: Union[float, Tuple[float, float, float]] = 40.0,
                       beam_diameter: float = 2.0,
                       view_normals: bool = False,
                       aa_passes: int = 0,
                       angle: float = 0.0,
                       rotation_point: Optional[Tuple[float, float, float]] = None) -> Dict:
        """
        Generate a shader for visualization.
        
        Args:
            cell_type: Type of cell
            positions: List of cell center positions
            cell_size: Size of the cells (single float or tuple for xyz)
            beam_diameter: Diameter of the beams
            view_normals: Whether to visualize as shaded or normals
            aa_passes: Number of anti-aliasing passes
            angle: Rotation angle
            rotation_point: Point to rotate around
        """
        if isinstance(cell_size, (int, float)):
            cell_size = (float(cell_size), float(cell_size), float(cell_size))
            
        data = {
            'cell_type': cell_type,
            'positions': positions,
            'cell_size': cell_size,
            'beam_diameter': beam_diameter,
            'view_normals': view_normals,
            'aa_passes': aa_passes,
            'angle': angle
        }
        if rotation_point is not None:
            data['rotation_point'] = rotation_point
            
        return self._make_request('POST', 'generate-shader', json=data)

    def calculate_voxel_centers(self,
                          cell_type: str,
                          cell_size: float,
                          force_dir: Tuple[float, float, float] = (0, 0, 1)) -> Dict:
        """Calculate voxel centers."""
        data = {
        'cell_type': cell_type,
        'cell_size': cell_size,
        'force_dir_x': force_dir[0],
        'force_dir_y': force_dir[1],
        'force_dir_z': force_dir[2]
    }
        return self._make_request('POST', 'voxel-centers', json=data)

    def _make_request(self, method: str, endpoint: str, **kwargs) -> Dict:
        """Make a request to the API."""
        url = f"{self.base_url}/{endpoint.lstrip('/')}"
        
        # Remove Content-Type header for multipart file uploads
        if 'files' in kwargs:
            headers = self.session.headers.copy()
            headers.pop('Content-Type', None)
            kwargs['headers'] = headers
        
        response = self.session.request(method, url, **kwargs)
        response.raise_for_status()
        return response.json()

    def get_status(self) -> Dict:
        """Get the current status of the API."""
        return self._make_request('GET', 'status')

    def get_state(self) -> Dict:
        """Get the current processing state."""
        return self._make_request('GET', 'state')