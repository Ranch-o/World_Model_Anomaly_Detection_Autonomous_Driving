import torch
import torch.nn.functional as F
import timm
import torchvision.transforms as transforms
from PIL import Image
import matplotlib.pyplot as plt
import numpy as np
import os

# Directories containing the frames
input_dir = '/disk/vanishing_data/du541/RGB_in_anovox_832_320_images'
synthesized_dir = '/disk/vanishing_data/du541/RGB_out_anovox_832_320_images'

# Directory to save perceptual difference images
save_dir = '/disk/vanishing_data/du541/anomaly_scores/perceptual_difference'
# os.makedirs(save_dir, exist_ok=True)

# Iterate through each pair of frames
for frame_number in range(1, 1851):
    input_image_path = os.path.join(input_dir, f'frame_{frame_number}.png')
    synthesized_image_path = os.path.join(synthesized_dir, f'frame_{frame_number}.png')

    # Load images
    input_image = Image.open(input_image_path).convert('RGB')
    synthesized_image = Image.open(synthesized_image_path).convert('RGB')

    # Preprocess images and other existing steps to calculate perceptual difference...


    # Get original image dimensions
    original_height, original_width = input_image.size[::-1]

    # Preprocess images
    transform = transforms.Compose([
        transforms.Resize((224, 224)),  # Adjust size if necessary
        transforms.ToTensor(),
        transforms.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225]),  # Imagenet stats
    ])
    input_image_tensor = transform(input_image).unsqueeze(0)
    synthesized_image_tensor = transform(synthesized_image).unsqueeze(0)

    # Determine device and move tensors to device
    device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
    input_image_tensor = input_image_tensor.to(device)
    synthesized_image_tensor = synthesized_image_tensor.to(device)

    # Load pre-trained ResNet-18
    resnet18 = timm.create_model('resnet18', pretrained=True, features_only=True).eval()
    resnet18 = resnet18.to(device)  # Move model to device

    # Get feature maps
    feature_maps_input = resnet18(input_image_tensor)
    feature_maps_synthesized = resnet18(synthesized_image_tensor)


    def plot_all_feature_maps(feature_maps, title, folder):
        for layer_index, feature_map_layer in enumerate(feature_maps):
            # Get the number of feature maps (channels)
            num_feature_maps = feature_map_layer.size(1)
            print(f'Layer {layer_index}: {num_feature_maps} feature maps')

            # Prepare the grid
            rows = int(num_feature_maps ** 0.5)
            cols = int(num_feature_maps / rows)
            fig, axs = plt.subplots(rows, cols, figsize=(15, 15))

            for i, ax in enumerate(axs.flat):
                # Only plot the feature maps with an index less than num_feature_maps
                if i < num_feature_maps:
                    ax.imshow(feature_map_layer[0, i].cpu().detach().numpy(), cmap='viridis')
                ax.axis('off')

            # plt.suptitle(f'{title} - Layer {layer_index}')
            # plt.show()
            
            # Create folder if it doesn't exist
            save_folder = os.path.join(folder, title, f'Layer_{layer_index}')
            os.makedirs(save_folder, exist_ok=True)
            
            # Save the figure
            save_path = os.path.join(save_folder, f'feature_maps_layer_{layer_index}.png')
            plt.suptitle(f'{title} - Layer {layer_index}')
            plt.savefig(save_path)
            plt.close(fig)  # Close the figure to free up memory

    # Define the folders to save the feature maps
    input_folder = 'feature_maps_original'
    synthesized_folder = 'feature_maps_synthesized'


    # # Plot and save the feature maps
    # plot_all_feature_maps(feature_maps_input, title='Feature Maps Input', folder=input_folder)
    # plot_all_feature_maps(feature_maps_synthesized, title='Feature Maps Synthesized', folder=synthesized_folder)



    # Get spatial dimensions from the first set of feature maps
    height, width = feature_maps_input[0].shape[2:4]

    # Initialize tensor to store per-pixel perceptual difference
    perceptual_difference_per_pixel = torch.zeros((height, width))

    # Calculate perceptual difference per pixel
    for h in range(height):
        for w in range(width):
            perceptual_difference = 0
            for fm_input, fm_synthesized in zip(feature_maps_input, feature_maps_synthesized):
                # Resize feature maps to match the spatial dimensions of the first set of feature maps
                fm_input_resized = F.interpolate(fm_input, size=(height, width), mode='bilinear', align_corners=False)
                fm_synthesized_resized = F.interpolate(fm_synthesized, size=(height, width), mode='bilinear', align_corners=False)
                num_elements = fm_input_resized.size(1)  # Number of channels (Mi elements)
                # print(num_elements)
                pixel_difference = F.l1_loss(fm_input_resized[0, :, h, w], fm_synthesized_resized[0, :, h, w], reduction='sum') / num_elements
                perceptual_difference += pixel_difference.item()
            perceptual_difference_per_pixel[h, w] = perceptual_difference


    # Visualization and saving part
    perceptual_difference_resized = F.interpolate(perceptual_difference_per_pixel.unsqueeze(0).unsqueeze(0),
                                                  size=(input_image.height, input_image.width),
                                                  mode='bilinear', align_corners=False).squeeze()


    # Desired output size in pixels
    output_width, output_height = 832, 320

    # Choose a DPI for the output image
    # DPI (Dots Per Inch) defines how many pixels will be placed in one inch of the image.
    # For example, if you want to print the image without scaling, a common DPI for printers is 300.
    dpi = 100  # This is an example; you can adjust this value based on your requirements

    # Calculate figure size in inches for the desired output resolution
    fig_width = output_width / dpi
    fig_height = output_height / dpi

    # Create a figure with the desired size and DPI
    fig = plt.figure(figsize=(fig_width, fig_height), dpi=dpi)

    # Plot the heatmap
    plt.imshow(perceptual_difference_resized.cpu().numpy(), cmap='hot', aspect='auto')

    # Remove axes and padding
    plt.axis('off')
    plt.subplots_adjust(top=1, bottom=0, right=1, left=0, hspace=0, wspace=0)
    plt.margins(0,0)
    plt.gca().xaxis.set_major_locator(plt.NullLocator())
    plt.gca().yaxis.set_major_locator(plt.NullLocator())

    # Save the figure to a file
    # plt.savefig('perceptual_difference_depth.png', bbox_inches='tight', pad_inches=0, dpi=dpi)
    plt.savefig(os.path.join(save_dir, f'perceptual_difference_{frame_number}.png'), bbox_inches='tight', pad_inches=0, dpi=dpi)
    plt.close(fig)  # Close the figure to free up memory
