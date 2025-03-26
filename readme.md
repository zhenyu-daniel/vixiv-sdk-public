# Voxelize SDK

A Python SDK for interacting with the Voxelize API for mesh processing and voxelization.
Subscription Price starts @ 10k/year.

## Installation

You can install the package directly from GitHub:

```bash
pip install git+https://github.com/zhenyu-daniel/vixiv-sdk-public.git
```

## Usage

Here's a simple example of how to use the Voxelize SDK:

```python
from flask_sdk.client import VoxelizeClient

# Initialize the client
client = VoxelizeClient(api_key="your-api-key-here")  # Or set VOXELIZE_API_KEY environment variable

# Example: Voxelize a mesh
result = client.voxelize_mesh(
    file_path="path/to/your/mesh.stl",
    cell_type="FCC",
    cell_size=40.0,
    beam_diameter=2.0
)

# Example: Generate a shader
shader_result = client.generate_shader(
    cell_type="FCC",
    positions=[(0, 0, 0), (40, 0, 0), (0, 40, 0)],
    scale_factor=1.0
)

# Example: Calculate voxel centers
centers_result = client.calculate_voxel_centers(
    cell_type="FCC",
    cell_size=40.0,
    angle=45.0
)

# Check API status
status = client.get_status()
print(status)
```

## API Reference

### VoxelizeClient

The main class for interacting with the Voxelize API.

#### Methods:

- `voxelize_mesh(file_path, cell_type=None, cell_size=None, beam_diameter=None, scale_factor=None)`
- `generate_shader(cell_type, positions, scale_factor=None)`
- `calculate_voxel_centers(cell_type, cell_size, angle=None)`
- `get_state()`
- `clear_state()`
- `get_status()`

## Environment Variables

- `VOXELIZE_API_KEY`: Your API key for authentication
- `FLASK_ENV`: Set to 'development' or 'production'
- `PORT`: API server port (default: 5000)

## Contributing

Please feel free to submit issues and pull requests.

## License

Business License. Please PAY!
