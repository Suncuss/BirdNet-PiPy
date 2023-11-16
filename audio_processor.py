import librosa
import numpy as np

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
