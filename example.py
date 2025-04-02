import os
from vixiv_sdk import VoxelizeClient
import logging

# Add debug logging
logging.basicConfig(level=logging.DEBUG)

def main():
    # Initialize the client
    api_key = "1234567890"
    client = VoxelizeClient(api_key=api_key, base_url="http://98.123.166.42:5000/api/v1")
    
    try:
        skin_path = os.path.join("mesh", "Test16.stl")
        network_path = os.path.join("mesh", "network.stl")
        
        # cell parameters
        cell_type = "bcc"
        cell_size = (40, 40, 40)  # in mm, xyz direction relative to force direction
        min_skin_thickness = 0.01  # in mm
        beam_diameter = 2  # in mm

        # voxelization parameters
        sampling_res = (1, 1, 1)  # number of steps to take in xyz direction
        force_dir = (0, 0, 1)  # vector representing -z direction for unit cell orientation
        
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
            file_path = skin_path,
            network_path = network_path,
            cell_type = cell_type,
            cell_size = cell_size,
            beam_diameter = beam_diameter,
            offsets = offsets,
            force_dir = force_dir,
            min_skin_thickness = min_skin_thickness,
            invert_cells = True,
            cell_centers = cell_centers,
            zero_thickness_dir = 'x'
        )

        # Step 3: Integrate network into skin
        final_path = client.integrate_network(
            skin_path=skin_path,
            network_path=network_path,
            out_path="final_result.stl"
        )

        #################
        # GLSL Shader
        # Get the mesh center point using read_mesh
        rotation_point = client.read_mesh(skin_path)

        # Calculate voxel centers for visualization
        vis_centers, angle = client.get_voxel_centers(
            cell_centers=cell_centers,
            force_dir=force_dir,
            rotation_point=rotation_point
        )
        
        ## print(angle, vis_centers)

        # Generate the shader
        shader_path = "out.glsl"
        client.generate_shader(
            cell_type = cell_type,
            cell_size = cell_size,
            beam_diameter = beam_diameter,
            cell_centers = vis_centers,
            shader_path = shader_path,
            rotation_point = rotation_point,
            view_normals = False,
            aa_passes = 0,
            angle = angle
        )
        


    
    except Exception as e:
        print(f"An error occurred: {e}")

if __name__ == "__main__":
    main()