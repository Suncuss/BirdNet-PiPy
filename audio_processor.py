import librosa

def split_audio(path, chuck_lenght, sample_rate=48000):

    print('Reading audio data...', end=' ', flush=True)

    sig, rate = librosa.load(path, sr=sample_rate, mono=True, res_type='kaiser_fast')

    chunks = []
    chunk_size = int(chuck_lenght * rate)

    for i in range(0, len(sig), chunk_size):
        split = sig[i:i + chunk_size]
        chunks.append(split)

    print(f'Done! Read {len(chunks)} chunks.')

    return chunks
