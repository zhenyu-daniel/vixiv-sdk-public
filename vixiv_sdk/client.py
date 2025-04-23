import requests
import json
from typing import Dict, List, Union, Optional, Tuple
import os
from pathlib import Path
import numpy as np
import tempfile
import shutil

class VoxelizeClient:
    """Python client for the Voxelize API."""
    
    def __init__(self, api_key=None, api_url=None, base_url=None, deployment_mode='local'):
        """Initialize the client with API key and URL.
        
        Args:
            api_key (str, optional): API key for authentication. If not provided, will look for VIXIV_API_KEY environment variable
            api_url (str, optional): Base URL of the API. If not provided, will look for VIXIV_API_URL environment variable
            base_url (str, optional): Alias for api_url, maintained for backward compatibility
            deployment_mode (str, optional): 'local' or 'gcp'. Determines how files are handled. Defaults to 'local'
        """
        self.api_key = api_key or os.getenv('VIXIV_API_KEY')
        if not self.api_key:
            raise ValueError("API key must be provided either directly or through VIXIV_API_KEY environment variable")
        
        # Handle both api_url and base_url for backward compatibility
        self.api_url = api_url or base_url or os.getenv('VIXIV_API_URL', 'https://vixiv-flask-api-gcp-523287772169.us-central1.run.app')
        self.session = requests.Session()
        self.session.headers.update({'X-API-Key': self.api_key})
        self.deployment_mode = deployment_mode

    def _handle_file_response(self, response, output_path=None):
        """Handle file response based on deployment mode."""
        if response.get('success'):
            result = response['result']
            if self.deployment_mode == 'gcp':
                # For GCP mode, download using the authenticated URL
                download_url = result['download_url']
                return self._download_file(download_url, output_path)
            else:
                # For local mode, decode the file content from hex
                output_dir = os.path.dirname(output_path) if output_path else tempfile.gettempdir()
                output_path = output_path if output_path else os.path.join(output_dir, result['filename'])
                with open(output_path, 'wb') as f:
                    f.write(bytes.fromhex(result['file_content']))
                return output_path
        raise ValueError(response.get('error', 'Unknown error occurred'))

    def _download_file(self, url_or_path, output_path=None):
        """Download a file from a URL or copy from local path."""
        try:
            # If it's a local path, just copy the file
            if os.path.exists(url_or_path):
                if output_path:
                    shutil.copy2(url_or_path, output_path)
                    return output_path
                else:
                    # Create a temporary file with .stl extension
                    temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.stl')
                    output_path = temp_file.name
                    temp_file.close()
                    shutil.copy2(url_or_path, output_path)
                    return output_path

            # Otherwise, download from URL
            headers = {'X-API-Key': self.api_key}
            response = requests.get(url_or_path, stream=True, headers=headers)
            response.raise_for_status()

            if output_path is None:
                # Create a temporary file with .stl extension
                temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.stl')
                output_path = temp_file.name
                temp_file.close()

            with open(output_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)

            return output_path

        except requests.exceptions.RequestException as e:
            print(f"Error downloading file: {str(e)}")
            raise

    def _upload_file(self, file_path: str, upload_url: str, content_type: str = 'application/octet-stream'):
        """Upload a file using a signed URL."""
        try:
            with open(file_path, 'rb') as f:
                headers = {'Content-Type': content_type}
                response = requests.put(upload_url, data=f, headers=headers)
                response.raise_for_status()
        except requests.exceptions.RequestException as e:
            print(f"Error uploading file: {str(e)}")
            raise
    
    def _make_request(self, method: str, endpoint: str, **kwargs) -> Dict:
        """Make a request to the API."""
        url = f"{self.api_url}/{endpoint.lstrip('/')}"
        print(f"Making request to: {url}")
        print(f"Method: {method}")
        print(f"Headers: {self.session.headers}")
        if 'data' in kwargs:
            print(f"Form data: {kwargs['data']}")
        if 'files' in kwargs:
            print(f"Files: {[f for f in kwargs['files'].keys()]}")
        
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
        
        try:
            response.raise_for_status()
            return response.json()
        except requests.exceptions.HTTPError as e:
            print(f"Response status code: {response.status_code}")
            print(f"Response content: {response.text}")
            raise

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
        """Voxelize a mesh file and save the result."""
        try:
            if not os.path.exists(file_path):
                raise FileNotFoundError(f"File not found: {file_path}")
            
            if not file_path.lower().endswith('.stl'):
                raise ValueError("Only STL files are supported")

            # Prepare form data
            data = {
                'cell_type': cell_type,
                'cell_size': f"{cell_size[0]},{cell_size[1]},{cell_size[2]}",
                'beam_diameter': str(beam_diameter),
                'force_dir': f"{force_dir[0]},{force_dir[1]},{force_dir[2]}",
                'min_skin_thickness': str(min_skin_thickness),
                'offsets': json.dumps(offsets.tolist() if hasattr(offsets, 'tolist') else offsets),
                'cell_centers': json.dumps(cell_centers.tolist() if hasattr(cell_centers, 'tolist') else cell_centers)
            }

            # Upload and process the file
            with open(file_path, 'rb') as f:
                files = {'file': (os.path.basename(file_path), f, 'application/octet-stream')}
                response = self._make_request('POST', 'voxelize', files=files, data=data)
            
            return self._handle_file_response(response, network_path)

        except Exception as e:
            print(f"Error during voxelization: {str(e)}")
            raise

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
            return self._handle_file_response(response, out_path)
    
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

    def FCC(self, beam_radius: float, bounding_box: tuple = (40, 40, 40)):
        """Create an FCC unit cell and save it as STL.
        
        Args:
            beam_radius (float): Radius of the beams
            bounding_box (tuple): Size of the bounding box (x, y, z)
            
        Returns:
            str: Path to the generated STL file
        """
        data = {
            'beam_radius': beam_radius,
            'cell_size': bounding_box
        }
        response = self._make_request('POST', 'fcc', json=data)
        if response.get('success'):
            return response['file_path']
        raise ValueError(response.get('error', 'Unknown error occurred'))

    def BCC(self, beam_radius: float, bounding_box: tuple = (40, 40, 40)):
        """Create a BCC unit cell and save it as STL.
        
        Args:
            beam_radius (float): Radius of the beams
            bounding_box (tuple): Size of the bounding box (x, y, z)
            
        Returns:
            str: Path to the generated STL file
        """
        data = {
            'beam_radius': beam_radius,
            'cell_size': bounding_box
        }
        response = self._make_request('POST', 'bcc', json=data)
        if response.get('success'):
            return response['file_path']
        raise ValueError(response.get('error', 'Unknown error occurred'))

    def Flourite(self, beam_radius: float, bounding_box: tuple = (40, 40, 40)):
        """Create a Flourite unit cell and save it as STL.
        
        Args:
            beam_radius (float): Radius of the beams
            bounding_box (tuple): Size of the bounding box (x, y, z)
            
        Returns:
            str: Path to the generated STL file
        """
        data = {
            'beam_radius': beam_radius,
            'cell_size': bounding_box
        }
        response = self._make_request('POST', 'flourite', json=data)
        if response.get('success'):
            return response['file_path']
        raise ValueError(response.get('error', 'Unknown error occurred'))

    def volume(self, file_path: str) -> float:
        """Calculate the volume of a mesh file.
        
        Args:
            file_path (str): Path to the STL file
            
        Returns:
            float: Volume of the mesh
        """
        response = self._make_request('GET', 'volume', params={'file_path': file_path})
        if response.get('success'):
            return float(response['volume'])
        raise ValueError(response.get('error', 'Unknown error occurred')) 