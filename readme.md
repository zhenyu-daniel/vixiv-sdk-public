# Voxelize SDK

A Python SDK for interacting with the Voxelize API for mesh processing and voxelization.
Subscription Price starts @ 10k/year.

## Installation

You can install the package directly from GitHub:

```bash
pip install git+https://github.com/zhenyu-daniel/vixiv-sdk-public.git
```

## Usage

Here's a comprehensive example of how to use the Voxelize SDK:

```python
import os
from vixiv_sdk import VoxelizeClient
import logging

# Enable debug logging if needed
logging.basicConfig(level=logging.DEBUG)

# Initialize the client
client = VoxelizeClient(
    api_key="your-api-key-here",
    base_url="http://127.0.0.1:5000/api/v1"  # Optional: specify custom API endpoint
)

# Define parameters
skin_path = "mesh/your_mesh.stl"
network_path = "mesh/network.stl"

# Cell parameters
cell_type = "bcc"
cell_size = (40, 40, 40)  # in mm, xyz direction relative to force direction
min_skin_thickness = 0.01  # in mm
beam_diameter = 2  # in mm

# Voxelization parameters
sampling_res = (1, 1, 1)  # number of steps in xyz direction
force_dir = (0, 0, 1)  # vector for unit cell orientation

# Step 1: Get mesh voxels
location_table, offsets, cell_centers = client.get_mesh_voxels(
    file_path=skin_path,
    cell_size=cell_size,
    min_skin_thickness=min_skin_thickness,
    sampling_res=sampling_res,
    force_dir=force_dir
)

# Step 2: Voxelize the mesh
network_path = client.voxelize_mesh(
    file_path=skin_path,
    network_path=network_path,
    cell_type=cell_type,
    cell_size=cell_size,
    beam_diameter=beam_diameter,
    offsets=offsets,
    force_dir=force_dir,
    min_skin_thickness=min_skin_thickness,
    invert_cells=True,
    cell_centers=cell_centers,
    zero_thickness_dir='x'
)

# Step 3: Integrate network into skin
final_path = client.integrate_network(
    skin_path=skin_path,
    network_path=network_path,
    out_path="final_result.stl"
)

# GLSL Shader Generation
# Get mesh center point
rotation_point = client.read_mesh(skin_path)

# Calculate voxel centers for visualization
vis_centers, angle = client.get_voxel_centers(
    cell_centers=cell_centers,
    force_dir=force_dir,
    rotation_point=rotation_point
)

# Generate shader
client.generate_shader(
    cell_type=cell_type,
    cell_size=cell_size,
    beam_diameter=beam_diameter,
    cell_centers=vis_centers,
    shader_path="out.glsl",
    rotation_point=rotation_point,
    view_normals=False,
    aa_passes=0,
    angle=angle
)
```

## API Reference

### VoxelizeClient

The main class for interacting with the Voxelize API.

#### Methods:

- `get_mesh_voxels(file_path, cell_size, min_skin_thickness, sampling_res, force_dir)`
- `voxelize_mesh(file_path, network_path, cell_type, cell_size, beam_diameter, offsets, force_dir, min_skin_thickness, invert_cells, cell_centers, zero_thickness_dir)`
- `integrate_network(skin_path, network_path, out_path)`
- `read_mesh(file_path)`
- `get_voxel_centers(cell_centers, force_dir, rotation_point)`
- `generate_shader(cell_type, cell_size, beam_diameter, cell_centers, shader_path, rotation_point, view_normals, aa_passes, angle)`
- `get_status()`

## Environment Variables

- `VOXELIZE_API_KEY`: Your API key for authentication
- `FLASK_ENV`: Set to 'development' or 'production'
- `PORT`: API server port (default: 5000)

## Contributing

Please feel free to submit issues and pull requests.

## License

Business License. Please PAY!
