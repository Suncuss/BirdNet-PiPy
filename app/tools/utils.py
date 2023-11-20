import os
import datetime

import sox
import librosa
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
from scipy.io import wavfile
from scipy.signal import spectrogram

from ..configs import config

def get_week_of_year():
    today = datetime.datetime.today()
    return today.isocalendar()[1]


def split_audio(path, chuck_lenght, sample_rate):
    print('Reading audio data...', end=' ', flush=True)
    sig, rate = librosa.load(path, sr=sample_rate, mono=True, res_type='kaiser_fast')
    chunks = []
    chunk_size = int(chuck_lenght * rate)
    for i in range(0, len(sig), chunk_size):
        split = sig[i:i + chunk_size]
        
        # pad the split array with zeros if it's not the correct length
        # should not need if we are using the same sample rate for all audio
        if len(split) < chunk_size:
            print("PADDING AUDIO")
            padded_split = np.zeros(chunk_size)
            padded_split[:len(split)] = split
            split = padded_split

        chunks.append(split)

    print(f'Done! Read {len(chunks)} chunks.')
    return chunks

def calulate_padded_start_and_end(start, end, total_length):
    # This section sets the SPACER that will be used to pad the audio clip with
    # context. If EXTRACTION_LENGTH is 10, for instance, 3 seconds are removed
    # from that value and divided by 2, so that the 3 seconds of the call are
    # within 3.5 seconds of audio context before and after.
    # Calculate the start and end time

    padding = (total_length - (end - start)) / 2
    start = max(start - padding, 0)
    end = min(end + padding, total_length)

    return start, end

def trim_audio(source_file_path, output_audio_path, start, end):

    start, end = calulate_padded_start_and_end(start, end, config.RECORDING_LENGTH)
    tfm = sox.Transformer()
    tfm.trim(start, end)
    tfm.build(source_file_path, output_audio_path)

def generate_spectrogram(input_file_path, output_file_path, graph_title):

    rate, data = wavfile.read(input_file_path)
    # Check if the audio is stereo or mono and take one channel if it's stereo
    if len(data.shape) > 1:
        data = data[:, 0]

    # Generate the spectrogram
    frequencies, times, Sxx = spectrogram(data, rate)

    # Convert the spectrogram to dBFS
    max_amplitude = np.max(np.abs(data))
    max_power = max_amplitude ** 2
    Sxx_dbfs = 10 * np.log10(Sxx / max_power)

    # Convert frequencies to kHz
    frequencies = frequencies / 1000

    # Plot the spectrogram
    plt.figure(figsize=(12.8, 7.2),facecolor='lightgrey')
    plt.imshow(Sxx_dbfs, aspect='auto', cmap='Greens_r', origin='lower',
                extent=[times.min(), times.max(), frequencies.min(), frequencies.max()],
                vmin=config.SPECTROGRAM_MIN_DBFS, vmax=config.SPECTROGRAM_MAX_DBFS)
    
    
    plt.title(graph_title, fontsize=14)
    plt.ylabel('Frequency [kHz]', fontsize=14)
    plt.xlabel('Time [sec]', fontsize=14)

    cbar = plt.colorbar()
    cbar.set_label('Intensity [dBFS]', fontsize=14)

    cbar.ax.tick_params(labelsize=10)  # Adjust to suitable size

    plt.xticks(fontsize=10)
    plt.yticks(fontsize=10)

    # Save the plot
    plt.savefig(output_file_path, dpi=100, bbox_inches='tight')
    plt.close()


# source_file_path = 'processed_audio_files/20231116_150407.wav'
# output_audio_path = 'extracted_audio_files/Carolina_Chickadee_99_2023-11-16-birdnet-15:04:10.wav'
# song_bird_file_name = 'Carolina_Chickadee_99_2023-11-16-birdnet-15:04:10.wav'
# output_spectrogram_path = 'extracted_audio_files/Carolina_Chickadee_99_2023-11-16-birdnet-15:04:10.png'

# generate_spectrogram(output_audio_path, output_spectrogram_path, "Carolina Chickadee 12/16/2023 15:04:10")

# File utils
def save_recording_file(file_data, file_name):
    file_path = os.path.join(config.AUDIO_FILES_DIRECTORY, file_name)
    with open(file_path, 'wb') as file:
        file.write(file_data)
    return file_path

def get_audio_file_path(file_name):
    return os.path.join(config.AUDIO_FILES_DIRECTORY, file_name)