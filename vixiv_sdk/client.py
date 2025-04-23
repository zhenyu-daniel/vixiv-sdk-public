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
    
    def __init__(self, api_key=None, api_url=None, base_url=None):
        """Initialize the client with API key and URL.
        
        Args:
            api_key (str, optional): API key for authentication. If not provided, will look for VIXIV_API_KEY environment variable
            api_url (str, optional): Base URL of the API. If not provided, will look for VIXIV_API_URL environment variable
            base_url (str, optional): Alias for api_url, maintained for backward compatibility
        """
        self.api_key = api_key or os.getenv('VIXIV_API_KEY')
        if not self.api_key:
            raise ValueError("API key must be provided either directly or through VIXIV_API_KEY environment variable")
        
        # Handle both api_url and base_url for backward compatibility
        self.api_url = api_url or base_url or os.getenv('VIXIV_API_URL', 'https://vixiv-flask-api-gcp-523287772169.us-central1.run.app')
        self.session = requests.Session()
        self.session.headers.update({'X-API-Key': self.api_key})

    def _is_gcs_url(self, url: str) -> bool:
        """Check if a URL is a Google Cloud Storage URL."""
        return url.startswith('https://storage.googleapis.com/') or url.startswith('gs://')

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

            # If no output path specified, create a temporary file
            if output_path is None:
                temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.stl')
                output_path = temp_file.name
                temp_file.close()

            # Download from URL
            headers = {'X-API-Key': self.api_key} if not self._is_gcs_url(url_or_path) else {}
            response = requests.get(url_or_path, stream=True, headers=headers)
            response.raise_for_status()

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
            
            if response.get('success'):
                # Download using the authenticated URL
                download_url = response['result']['download_url']
                return self._download_file(download_url, network_path)
            raise ValueError(response.get('error', 'Unknown error occurred'))

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
        
        # Check file sizes
        skin_size = os.path.getsize(skin_path)
        network_size = os.path.getsize(network_path)
        
        # Use direct upload for large files (> 20MB)
        skin_url = self._upload_file_to_gcs(skin_path, skin_size > 20 * 1024 * 1024)
        network_url = self._upload_file_to_gcs(network_path, network_size > 20 * 1024 * 1024)
        
        # Now send the GCS URLs to the integrate-network endpoint
        data = {
            'skin_url': skin_url,
            'network_url': network_url
        }
        
        response = self._make_request('POST', 'integrate-network', json=data)
        
        if response.get('success'):
            # Download using the public URL
            download_url = response['result']['download_url']
            return self._download_file(download_url, out_path)
        raise ValueError(response.get('error', 'Unknown error occurred'))
        
    def _upload_file_to_gcs(self, file_path: str, use_direct_upload: bool = False) -> str:
        """
        Upload a file to GCS using the appropriate method based on file size.
        
        Args:
            file_path: Path to the file to upload
            use_direct_upload: Whether to use direct upload to GCS
            
        Returns:
            str: The download URL for the uploaded file
        """
        filename = os.path.basename(file_path)
        
        if use_direct_upload:
            # For large files, get information for direct upload
            print(f"File {filename} is large, using direct upload to GCS")
            response = self._make_request('POST', 'split-upload', json={'filename': filename})
            if not response.get('success'):
                raise ValueError(response.get('error', 'Failed to get upload information'))
            
            # Use curl command to upload directly to GCS
            blob_name = response['result']['blob_name']
            bucket = response['result']['bucket']
            url = f"https://storage.googleapis.com/{bucket}/{blob_name}"
            
            curl_command = ['curl', '-X', 'PUT', '-T', file_path, 
                           '-H', 'Content-Type: application/octet-stream', 
                           url]
            
            import subprocess
            try:
                print(f"Executing: {' '.join(curl_command)}")
                result = subprocess.run(curl_command, capture_output=True, text=True, check=True)
                print(f"Upload result: {result.stdout}")
                return response['result']['download_url']
            except subprocess.CalledProcessError as e:
                print(f"Upload error: {e.stderr}")
                raise ValueError(f"Failed to upload file: {e.stderr}")
            except FileNotFoundError:
                # If curl is not available, try with requests in chunks
                print("curl not found, trying with requests")
                return self._upload_with_requests(file_path, url)
        else:
            # For smaller files, use the regular upload endpoint
            with open(file_path, 'rb') as f:
                files = {'file': (filename, f, 'application/octet-stream')}
                response = self._make_request('POST', 'upload-to-gcs', files=files)
                if not response.get('success'):
                    raise ValueError(response.get('error', 'Failed to upload file'))
                return response['result']['download_url']
                
    def _upload_with_requests(self, file_path: str, url: str) -> str:
        """Upload a file with requests library."""
        with open(file_path, 'rb') as f:
            response = requests.put(url, data=f, headers={'Content-Type': 'application/octet-stream'})
            response.raise_for_status()
        return url
    
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
            str: Path to the downloaded STL file
        """
        data = {
            'beam_radius': beam_radius,
            'cell_size': bounding_box
        }
        response = self._make_request('POST', 'fcc', json=data)
        if response.get('success'):
            # Download the file from GCS URL
            download_url = response['result']['download_url']
            temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.stl')
            output_path = temp_file.name
            temp_file.close()
            return self._download_file(download_url, output_path)
        raise ValueError(response.get('error', 'Unknown error occurred'))

    def BCC(self, beam_radius: float, bounding_box: tuple = (40, 40, 40)):
        """Create a BCC unit cell and save it as STL.
        
        Args:
            beam_radius (float): Radius of the beams
            bounding_box (tuple): Size of the bounding box (x, y, z)
            
        Returns:
            str: Path to the downloaded STL file
        """
        data = {
            'beam_radius': beam_radius,
            'cell_size': bounding_box
        }
        response = self._make_request('POST', 'bcc', json=data)
        if response.get('success'):
            # Download the file from GCS URL
            download_url = response['result']['download_url']
            temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.stl')
            output_path = temp_file.name
            temp_file.close()
            return self._download_file(download_url, output_path)
        raise ValueError(response.get('error', 'Unknown error occurred'))

    def Flourite(self, beam_radius: float, bounding_box: tuple = (40, 40, 40)):
        """Create a Flourite unit cell and save it as STL.
        
        Args:
            beam_radius (float): Radius of the beams
            bounding_box (tuple): Size of the bounding box (x, y, z)
            
        Returns:
            str: Path to the downloaded STL file
        """
        data = {
            'beam_radius': beam_radius,
            'cell_size': bounding_box
        }
        response = self._make_request('POST', 'flourite', json=data)
        if response.get('success'):
            # Download the file from GCS URL
            download_url = response['result']['download_url']
            temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.stl')
            output_path = temp_file.name
            temp_file.close()
            return self._download_file(download_url, output_path)
        raise ValueError(response.get('error', 'Unknown error occurred'))

    def volume(self, file_path: str) -> float:
        """Calculate the volume of a mesh file.
        
        Args:
            file_path (str): Path to the STL file or GCS URL from another function
            
        Returns:
            float: Volume of the mesh
        """
        # Check if the path is a GCS URL
        is_gcs_url = self._is_gcs_url(file_path)
        blob_name = None
        
        if not is_gcs_url:
            # Regular local file that needs to be uploaded
            if not os.path.exists(file_path):
                raise FileNotFoundError(f"File not found: {file_path}")
            
            if not file_path.lower().endswith('.stl'):
                raise ValueError("Only STL files are supported")
                
            # Check file size
            file_size = os.path.getsize(file_path)
            
            # Upload the file to GCS using appropriate method based on size
            file_url = self._upload_file_to_gcs(file_path, file_size > 20 * 1024 * 1024)
            
            # Extract the blob name from the URL for cleanup later
            blob_name = file_url.split('/')[-2] + '/' + file_url.split('/')[-1]
        else:
            # Already a GCS URL from another function
            file_url = file_path
            # Extract the blob name from the URL for cleanup later
            blob_name = '/'.join(file_url.split('/')[4:]) if 'storage.googleapis.com' in file_url else file_url
        
        try:
            # Get the volume from the server using the URL
            response = self._make_request('GET', 'volume', params={'file_url': file_url})
            if response.get('success'):
                return float(response['volume'])
            raise ValueError(response.get('error', 'Unknown error occurred'))
        finally:
            # Clean up the GCS file
            if blob_name:
                try:
                    self._make_request('DELETE', f'delete-from-gcs/{blob_name}')
                except Exception as e:
                    print(f"Warning: Failed to clean up GCS file: {e}")
                    # Continue even if cleanup fails