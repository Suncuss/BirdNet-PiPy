import matplotlib.pyplot as plt
from scipy.signal import spectrogram
from scipy.io import wavfile
import numpy as np
import os
import config

# List of color maps to use
color_maps = ['Accent', 'Accent_r', 'Blues', 'Blues_r', 'BrBG', 'BrBG_r', 'BuGn', 'BuGn_r', 'BuPu', 'BuPu_r', 'CMRmap', 'CMRmap_r', 'Dark2', 'Dark2_r', 'GnBu', 'GnBu_r', 'Greens', 'Greens_r', 'Greys', 'Greys_r', 'OrRd', 'OrRd_r', 'Oranges', 'Oranges_r', 'PRGn', 'PRGn_r', 'Paired', 'Paired_r', 'Pastel1', 'Pastel1_r', 'Pastel2', 'Pastel2_r', 'PiYG', 'PiYG_r', 'PuBu', 'PuBuGn', 'PuBuGn_r', 'PuBu_r', 'PuOr', 'PuOr_r', 'PuRd', 'PuRd_r', 'Purples', 'Purples_r', 'RdBu', 'RdBu_r', 'RdGy', 'RdGy_r', 'RdPu', 'RdPu_r', 'RdYlBu', 'RdYlBu_r', 'RdYlGn', 'RdYlGn_r', 'Reds', 'Reds_r', 'Set1', 'Set1_r', 'Set2', 'Set2_r', 'Set3', 'Set3_r', 'Spectral', 'Spectral_r', 'Wistia', 'Wistia_r', 'YlGn', 'YlGnBu', 'YlGnBu_r', 'YlGn_r', 'YlOrBr', 'YlOrBr_r', 'YlOrRd', 'YlOrRd_r', 'afmhot', 'afmhot_r', 'autumn', 'autumn_r', 'binary', 'binary_r', 'bone', 'bone_r', 'brg', 'brg_r', 'bwr', 'bwr_r', 'cividis', 'cividis_r', 'cool', 'cool_r', 'coolwarm', 'coolwarm_r', 'copper', 'copper_r', 'cubehelix', 'cubehelix_r', 'flag', 'flag_r', 'gist_earth', 'gist_earth_r', 'gist_gray', 'gist_gray_r', 'gist_heat', 'gist_heat_r', 'gist_ncar', 'gist_ncar_r', 'gist_rainbow', 'gist_rainbow_r', 'gist_stern', 'gist_stern_r', 'gist_yarg', 'gist_yarg_r', 'gnuplot', 'gnuplot2', 'gnuplot2_r', 'gnuplot_r', 'gray', 'gray_r', 'hot', 'hot_r', 'hsv', 'hsv_r', 'inferno', 'inferno_r', 'jet', 'jet_r', 'magma', 'magma_r', 'nipy_spectral', 'nipy_spectral_r', 'ocean', 'ocean_r', 'pink', 'pink_r', 'plasma', 'plasma_r', 'prism', 'prism_r', 'rainbow', 'rainbow_r', 'seismic', 'seismic_r', 'spring', 'spring_r', 'summer', 'summer_r', 'tab10', 'tab10_r', 'tab20', 'tab20_r', 'tab20b', 'tab20b_r', 'tab20c', 'tab20c_r', 'terrain', 'terrain_r', 'turbo', 'turbo_r', 'twilight', 'twilight_r', 'twilight_shifted', 'twilight_shifted_r', 'viridis', 'viridis_r', 'winter', 'winter_r']

def generate_spectrogram(input_file_path, output_file_path, graph_title, color_map):
    rate, data = wavfile.read(input_file_path)
    if len(data.shape) > 1:
        data = data[:, 0]

    frequencies, times, Sxx = spectrogram(data, rate)

    max_amplitude = np.max(np.abs(data))
    max_power = max_amplitude ** 2
    Sxx_dbfs = 10 * np.log10(Sxx / max_power)

    frequencies = frequencies / 1000

    plt.figure(figsize=(12.8, 7.2), facecolor='lightgrey')
    plt.imshow(Sxx_dbfs, aspect='auto', cmap=color_map, origin='lower',
               extent=[times.min(), times.max(), config.SPECTROGRAM_MIN_FREQ, config.SPECTROGRAM_MAX_FREQ],
               vmin=config.SPECTROGRAM_MIN_DBFS, vmax=config.SPECTROGRAM_MAX_DBFS)

    plt.title(graph_title, fontsize=14)
    plt.ylabel('Frequency [kHz]', fontsize=14)
    plt.xlabel('Time [sec]', fontsize=14)

    cbar = plt.colorbar()
    cbar.set_label('Intensity [dBFS]', fontsize=14)
    cbar.ax.tick_params(labelsize=10)

    plt.xticks(fontsize=10)
    plt.yticks(fontsize=10)

    plt.savefig(output_file_path, dpi=100, bbox_inches='tight')
    plt.close()

def generate_spectrograms_for_color_maps(input_file_path, output_folder):
    for color_map in color_maps:
        output_file_path = os.path.join(output_folder, f'spectrogram_{color_map}.png')
        graph_title = f'Spectrogram - {color_map.capitalize()}'
        generate_spectrogram(input_file_path, output_file_path, graph_title, color_map)

output_audio_path = 'extracted_audio_files/Carolina_Chickadee_99_2023-11-16-birdnet-15:04:10.wav'
# Example usage
generate_spectrograms_for_color_maps(output_audio_path, 'color_maps_preview')
