import requests
import json
from typing import Dict, List, Union, Optional, Tuple
import os
from pathlib import Path
import numpy as np

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
    
    def get_mesh_voxels(self,
                      file_path: str,
                      cell_size: tuple = (40, 40, 40),
                      min_skin_thickness: float = 0.01,
                      sampling_res: tuple = (1, 1, 1),
                      force_dir: tuple = (0, 0, 1)) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
        """
        Get voxels data from a mesh file using the specified parameters.
        
        Args:
            file_path: Path to the input STL file
            cell_size: Size of the cells in mm (tuple of x,y,z values)
            min_skin_thickness: Minimum skin thickness in mm
            sampling_res: Sampling resolution in xyz directions
            force_dir: Force direction vector for unit cell orientation
            
        Returns:
            Tuple containing (location_table, offsets, cell_centers)
        """
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"File not found: {file_path}")
        
        if not file_path.lower().endswith('.stl'):
            raise ValueError("Only STL files are supported")
        
        with open(file_path, 'rb') as f:
            files = {'file': (os.path.basename(file_path), f, 'application/octet-stream')}
            
            data = {
                'cell_size': f"{cell_size[0]},{cell_size[1]},{cell_size[2]}",
                'min_skin_thickness': str(min_skin_thickness),
                'sampling_res': f"{sampling_res[0]},{sampling_res[1]},{sampling_res[2]}",
                'force_dir': f"{force_dir[0]},{force_dir[1]},{force_dir[2]}"
            }
            
            response = self._make_request('POST', 'get-mesh-voxels', files=files, data=data)
            
            if response.get('success'):
                result = response['result']
                return (
                    np.array(result['location_table']),
                    np.array(result['offsets']),
                    np.array(result['cell_centers'])
                )
            raise ValueError(response.get('error', 'Unknown error occurred'))

    def voxelize_mesh(self, 
                     file_path: str,
                     network_path: str,
                     cell_type: str = "fcc",
                     cell_size: tuple = (40, 40, 40),
                     beam_diameter: float = 2.0,
                     offsets: np.ndarray = None,
                     force_dir: tuple = (0, 0, 1),
                     min_skin_thickness: float = 0.01,
                     invert_cells: bool = True,
                     cell_centers: np.ndarray = None,
                     zero_thickness_dir: str = 'x') -> str:
        """
        Voxelize a mesh file using the specified parameters.
        
        Args:
            file_path: Path to the input STL file
            network_path: Path where the network mesh will be saved
            cell_type: Type of cell ("fcc", "bcc", or "flourite")
            cell_size: Size of the cells in mm (tuple of x,y,z values)
            beam_diameter: Diameter of the beams in mm
            offsets: Offsets data from get_mesh_voxels
            force_dir: Force direction vector for unit cell orientation
            min_skin_thickness: Minimum skin thickness in mm
            invert_cells: Whether to generate the inverse space of the unit cell
            cell_centers: Center positions of all cells within the skin
            zero_thickness_dir: Direction to remove portions of the skin for manufacturability
            
        Returns:
            str: Path to the network mesh file
        """
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"File not found: {file_path}")
        
        if not file_path.lower().endswith('.stl'):
            raise ValueError("Only STL files are supported")
        
        with open(file_path, 'rb') as f:
            files = {'file': (os.path.basename(file_path), f, 'application/octet-stream')}
            
            data = {
                'cell_type': cell_type,
                'cell_size': f"{cell_size[0]},{cell_size[1]},{cell_size[2]}",
                'beam_diameter': str(beam_diameter),
                'force_dir': f"{force_dir[0]},{force_dir[1]},{force_dir[2]}",
                'min_skin_thickness': str(min_skin_thickness),
                'offsets': json.dumps(offsets.tolist()) if offsets is not None else None,
                'cell_centers': json.dumps(cell_centers.tolist()) if cell_centers is not None else None
            }
            
            response = self._make_request('POST', 'voxelize', files=files, data=data)
            
            if response.get('success'):
                result = response['result']
                output_dir = os.path.dirname(network_path)
                output_path = os.path.join(output_dir, result['filename'])
                with open(output_path, 'wb') as f:
                    f.write(bytes.fromhex(result['file_content']))
                return output_path
            raise ValueError(response.get('error', 'Unknown error occurred'))

    def integrate_network(self,
                        skin_path: str,
                        network_path: str,
                        out_path: str = None) -> str:
        """
        Integrate a network mesh into a skin mesh.
        
        Args:
            skin_path: Path to the input skin STL file
            network_path: Path to the input network STL file
            out_path: Optional path for the output file
            
        Returns:
            str: Path to the final integrated mesh file
        """
        if not os.path.exists(skin_path):
            raise FileNotFoundError(f"Skin file not found: {skin_path}")
        
        if not os.path.exists(network_path):
            raise FileNotFoundError(f"Network file not found: {network_path}")
        
        if not skin_path.lower().endswith('.stl') or not network_path.lower().endswith('.stl'):
            raise ValueError("Only STL files are supported")
        
        with open(skin_path, 'rb') as skin_f, open(network_path, 'rb') as network_f:
            files = {
                'skin_file': (os.path.basename(skin_path), skin_f, 'application/octet-stream'),
                'network_file': (os.path.basename(network_path), network_f, 'application/octet-stream')
            }
            
            response = self._make_request('POST', 'integrate-network', files=files)
            
            if response.get('success'):
                result = response['result']
                output_dir = os.path.dirname(out_path) if out_path else os.path.dirname(skin_path)
                output_path = out_path if out_path else os.path.join(output_dir, result['filename'])
                with open(output_path, 'wb') as f:
                    f.write(bytes.fromhex(result['file_content']))
                return output_path
            raise ValueError(response.get('error', 'Unknown error occurred'))
    
    def read_mesh(self, file_path: str) -> np.ndarray:
        """
        Read a mesh file and return its center point.
        
        Args:
            file_path: Path to the input STL file
            
        Returns:
            numpy.ndarray: The center point of the mesh
        """
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"File not found: {file_path}")
        
        if not file_path.lower().endswith('.stl'):
            raise ValueError("Only STL files are supported")
        
        with open(file_path, 'rb') as f:
            files = {'file': (os.path.basename(file_path), f, 'application/octet-stream')}
            response = self._make_request('POST', 'read-mesh', files=files)
            
            if response.get('success'):
                return np.array(response['result']['center'])
            raise ValueError(response.get('error', 'Unknown error occurred'))

    def get_voxel_centers(self,
                        cell_centers: np.ndarray,
                        force_dir: tuple = (0, 0, 1),
                        rotation_point: np.ndarray = None) -> Tuple[np.ndarray, float]:
        """
        Calculate voxel centers for visualization.
        
        Args:
            cell_centers: Center positions of all cells within the skin
            force_dir: Force direction vector for unit cell orientation
            rotation_point: Optional rotation point for the centers
            
        Returns:
            Tuple containing (centers, angle) where:
                - centers: numpy array of center positions for visualization
                - angle: float rotation angle in degrees
        """
        data = {
            'cell_centers': cell_centers.tolist() if hasattr(cell_centers, 'tolist') else cell_centers,
            'force_dir': list(force_dir),
            'rotation_point': rotation_point.tolist() if rotation_point is not None and hasattr(rotation_point, 'tolist') else rotation_point
        }
        
        response = self._make_request('POST', 'get-voxel-centers', json=data)
        
        if response.get('success'):
            result = response['result']
            return (
                np.array(result['centers']),
                float(result['angle'])
            )
        raise ValueError(response.get('error', 'Unknown error occurred'))

    def generate_shader(self, cell_type: str, cell_size: Tuple[float, float, float], beam_diameter: float,
                       cell_centers: np.ndarray, shader_path: str, rotation_point: Optional[np.ndarray] = None,
                       view_normals: bool = False, aa_passes: int = 0, angle: float = 0.0) -> None:
        """
        Generate a shader file for visualization.

        Args:
            cell_type (str): Type of cell to use ('fcc' or 'bcc')
            cell_size (tuple): Size of cells in x, y, z directions
            beam_diameter (float): Diameter of the beam
            cell_centers (np.ndarray): Array of cell center coordinates
            shader_path (str): Path where to save the shader file
            rotation_point (np.ndarray, optional): Point to rotate around
            view_normals (bool): Whether to view normals
            aa_passes (int): Number of anti-aliasing passes
            angle (float): Rotation angle

        Returns:
            None
        """
        # Prepare request data
        data = {
            'cell_type': cell_type,
            'cell_size': cell_size,
            'beam_diameter': beam_diameter,
            'cell_centers': cell_centers.tolist(),
            'view_normals': view_normals,
            'aa_passes': aa_passes,
            'angle': angle
        }
        if rotation_point is not None:
            data['rotation_point'] = rotation_point.tolist()

        # Create directory if it doesn't exist
        shader_dir = os.path.dirname(shader_path)
        if shader_dir:
            os.makedirs(shader_dir, exist_ok=True)

        # Make request
        response = self._make_request('POST', 'generate-shader', json=data)

        # Save shader content to file
        with open(shader_path, 'w') as f:
            f.write(response['shader_content'])
    
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